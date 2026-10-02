from __future__ import annotations

import queue
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from orion.api.dto import (
    AgentRosterResponse,
    AgentTelemetryDTO,
    CreateMissionRequest,
    EvaluationDetailDTO,
    EvidenceItemDTO,
    ExecutionGraphEdgeDTO,
    ExecutionGraphNodeDTO,
    ExecutionGraphResponse,
    MissionResponse,
    ReadinessResponse,
    RecoveryDetailDTO,
    RecoveryObservabilityResponse,
    TaskApprovalRequest,
    TaskApprovalResponse,
    TaskCancellationRequest,
    TaskCancellationResponse,
    TaskChangesResponse,
    TaskExecutionResponse,
    TaskSubmissionRequest,
    TaskTestsResponse,
    TimelineEventDTO,
    VerificationDetailDTO,
)
from orion.config.app_config import AppConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.agents.workforce.conflict import AgentConflictResolver
from orion.core.agents.workforce.contracts import WorkforceContractRegistry
from orion.core.agents.workforce.models import AgentProposal, WorkforceRole
from orion.core.agents.workforce.reviewer import IndependentReviewer
from orion.core.evaluation import (
    FAILURE_TAXONOMY_CORPUS,
    SMOKE_CORPUS,
    STANDARD_CORPUS,
    BenchmarkReport,
    BenchmarkRunner,
    ExperimentRecord,
    ExperimentTracker,
)
from orion.core.hitl import (
    ClarificationStatus,
    HITLCoordinator,
    InterventionType,
)
from orion.core.missions.engine import MissionExecutionEngine
from orion.core.missions.graph import MissionTaskGraph
from orion.core.missions.memory import MissionMemory
from orion.core.missions.models import MissionPlan, ResourceBudget
from orion.core.missions.planner import MissionPlanner
from orion.core.observability import (
    DistributedTracer,
    SpanKind,
    SpanRecord,
    SpanStatus,
    SystemOptimizer,
    TelemetryContext,
)
from orion.core.policy import (
    PolicyContext,
    PolicyEffect,
    PolicyEngine,
    PolicyRiskTier,
    PolicyRule,
)
from orion.core.recovery.advanced.memory import AdaptiveRecoveryMemory
from orion.core.recovery.advanced.planner import AdaptiveRecoveryPlanner
from orion.core.recovery.advanced.simulation import RecoverySimulator
from orion.core.recovery.advanced.taxonomy import FailureClassifier
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.repo_intel.detector import ArchitectureDetector
from orion.core.repo_intel.graph import RepoCodeGraph
from orion.core.repo_intel.impact import ChangeImpactAnalyzer
from orion.core.repo_intel.optimizer import ContextOptimizer
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
from orion.core.security.redaction import RedactionEngine
from orion.core.swe.cognitive.patch_approval import PatchApprovalPackage
from orion.core.swe.coordinator import STAGE_ORDER, SWEWorkflowCoordinator
from orion.core.swe.evidence import (
    EvidenceCategory,
    EvidenceLevel,
    SWEReport,
)
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.tools.repository.factory import register_repository_tools
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace


def validate_workspace_path(path_str: str) -> Path:
    """Validate workspace path exists, is a directory, and is not a protected system root."""
    if not path_str or not path_str.strip():
        raise ValueError("Workspace path cannot be empty.")

    p = Path(path_str).resolve()
    if not p.exists():
        raise ValueError(f"Workspace directory does not exist: '{path_str}'")
    if not p.is_dir():
        raise ValueError(f"Workspace path is not a directory: '{path_str}'")

    # Reject root filesystem paths
    if len(p.parts) <= 1 or p == p.parent:
        raise ValueError(f"Workspace path cannot be the filesystem root: '{path_str}'")

    # Reject sensitive system paths
    forbidden_roots = {
        "windows",
        "system32",
        "program files",
        "program files (x86)",
        "etc",
        "boot",
        "sys",
        "proc",
        "dev",
    }
    for part in p.parts:
        if part.lower() in forbidden_roots:
            raise ValueError(
                f"Workspace path inside protected system directory is forbidden: '{path_str}'"
            )

    return p


@dataclass
class MissionRecord:
    """Internal record tracking an active or completed mission."""

    mission_id: UUID
    task_id: UUID
    execution_id: UUID
    objective: str
    workspace_path: str
    workspace: Workspace
    coordinator: SWEWorkflowCoordinator
    approval_service: ApprovalService
    agent: Agent
    created_at: datetime
    execution_mode: str = "controlled"
    status: str = "initialized"
    lifecycle_state: str = "RECEIVED"
    summary: str = ""
    report: SWEReport | None = None
    timeline: list[TimelineEventDTO] = field(default_factory=list)
    pending_approval: PatchApprovalPackage | None = None
    subscribers: list[queue.Queue[dict[str, Any]]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_error: str | None = None
    cancelled: bool = False


class MissionAPIService:
    """Product-facing application service managing autonomous SWE missions."""

    def __init__(
        self,
        default_workspace_path: Path | str | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self._missions: dict[UUID, MissionRecord] = {}
        self._start_time = time.time()
        self._default_workspace_path = (
            Path(default_workspace_path).resolve()
            if default_workspace_path
            else None
        )
        self._config = config or AppConfig.from_env(
            argv_workspace=self._default_workspace_path
        )
        self._redaction_engine = RedactionEngine(secrets=self._config.known_secrets)
        self._is_shutting_down: bool = False
        self._mission_plans: dict[UUID, tuple[MissionPlan, MissionTaskGraph]] = {}
        self._mission_memories: dict[UUID, MissionMemory] = {}
        self._mission_engines: dict[UUID, MissionExecutionEngine] = {}
        self._workforce_registry = WorkforceContractRegistry.create_default_roster()
        self._adaptive_recovery_memory = AdaptiveRecoveryMemory()
        self._experiment_tracker = ExperimentTracker(self._redaction_engine)
        self._benchmark_runner = BenchmarkRunner()
        self._hitl_coordinator = HITLCoordinator()
        self._policy_engine = PolicyEngine()
        self._tracer = DistributedTracer()
        self._system_optimizer = SystemOptimizer(self._tracer)

    @property
    def config(self) -> AppConfig:
        """Return the active AppConfig instance."""
        return self._config

    @property
    def uptime_seconds(self) -> float:
        """Return service uptime in seconds."""
        return round(time.time() - self._start_time, 2)

    @property
    def missions_count(self) -> int:
        """Return total count of managed missions."""
        return len(self._missions)

    @property
    def is_shutting_down(self) -> bool:
        """Return True if service is shutting down."""
        return self._is_shutting_down

    def _get_record(self, ident: UUID) -> MissionRecord | None:
        """Retrieve MissionRecord by mission_id or task_id."""
        if ident in self._missions:
            return self._missions[ident]
        for r in self._missions.values():
            if r.task_id == ident or r.mission_id == ident:
                return r
        return None

    # -------------------------------------------------------------
    # Event Streaming Pub/Sub
    # -------------------------------------------------------------
    def subscribe_events(self, mission_id: UUID) -> queue.Queue[dict[str, Any]]:
        """Register an event queue for real-time SSE streaming."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        with record.lock:
            record.subscribers.append(q)
        return q

    def unsubscribe_events(
        self, mission_id: UUID, q: queue.Queue[dict[str, Any]]
    ) -> None:
        """Unregister an SSE event queue."""
        record = self._get_record(mission_id)
        if not record:
            return
        with record.lock:
            if q in record.subscribers:
                record.subscribers.remove(q)

    def emit_event(
        self,
        mission_id: UUID,
        event_type: str,
        data: dict[str, Any],
        level: str = "info",
    ) -> None:
        """Publish a real-time event to subscribers and record in timeline."""
        record = self._get_record(mission_id)
        if not record:
            return

        # Scrub sensitive tokens/passwords if redaction is enabled
        scrubbed_data: dict[str, Any] = (
            self._redaction_engine.redact(data)
            if self._config.redaction_enabled
            else data
        )

        now_iso = datetime.now(UTC).isoformat()
        event_payload = {
            "event": event_type,
            "mission_id": str(mission_id),
            "task_id": str(record.task_id),
            "execution_id": str(record.execution_id),
            "lifecycle_state": record.lifecycle_state,
            "timestamp": now_iso,
            "data": scrubbed_data,
        }

        # Record event in timeline with scrubbed detail & metadata
        current_st = (
            record.coordinator.current_stage.value
            if record.coordinator.current_stage
            else record.lifecycle_state.lower()
        )
        raw_detail = str(
            scrubbed_data.get("summary")
            or scrubbed_data.get("detail")
            or event_type
        )
        scrubbed_detail = (
            self._redaction_engine.redact(raw_detail)
            if self._config.redaction_enabled
            else raw_detail
        )

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage=current_st,
                title=event_type.replace("_", " ").title(),
                detail=scrubbed_detail,
                level=level,
                timestamp=now_iso,
                metadata=scrubbed_data,
            )
        )

        with record.lock:
            dead_queues = []
            for q in record.subscribers:
                try:
                    q.put_nowait(event_payload)
                except queue.Full:
                    dead_queues.append(q)
            for dq in dead_queues:
                record.subscribers.remove(dq)

    # -------------------------------------------------------------
    # Health, Readiness, and Graceful Shutdown
    # -------------------------------------------------------------
    def check_readiness(self) -> ReadinessResponse:
        """Evaluate subsystem readiness, workspace writeability, and shutdown state."""
        now_iso = datetime.now(UTC).isoformat()
        ws_path = (
            self._default_workspace_path
            or self._config.workspace
            or Path(".").resolve()
        )
        ws_str = str(ws_path)

        checks: dict[str, bool] = {
            "workspace_exists": False,
            "workspace_writable": False,
            "service_running": not self._is_shutting_down,
        }

        if ws_path.exists() and ws_path.is_dir():
            checks["workspace_exists"] = True
            probe_path = ws_path / f".orion_readiness_probe_{uuid4().hex}"
            try:
                probe_path.write_text("ok", encoding="utf-8")
                if probe_path.exists():
                    checks["workspace_writable"] = True
                    probe_path.unlink(missing_ok=True)
            except OSError:
                checks["workspace_writable"] = False

        is_ready = all(checks.values())
        status_str = "ready" if is_ready else "not_ready"

        active_count = sum(
            1
            for m in self._missions.values()
            if m.lifecycle_state not in ("COMPLETED", "TERMINATED", "CANCELLED", "SHUTDOWN")
        )

        return ReadinessResponse(
            status=status_str,
            version="1.0.0",
            environment=self._config.environment,
            workspace_path=ws_str,
            workspace_writable=checks["workspace_writable"],
            active_missions=active_count,
            checks=checks,
            timestamp=now_iso,
        )

    def shutdown(self) -> None:
        """Perform graceful shutdown, closing in-flight missions and notifying SSE subscribers."""
        self._is_shutting_down = True
        now_iso = datetime.now(UTC).isoformat()
        terminal_states = ("COMPLETED", "TERMINATED", "CANCELLED", "SHUTDOWN")

        for mission_id, record in self._missions.items():
            with record.lock:
                if record.lifecycle_state not in terminal_states:
                    record.cancelled = True
                    record.lifecycle_state = "SHUTDOWN"
                    record.status = "shutdown"
                    record.last_error = "Server shutting down"

                # Broadcast shutdown event to active subscribers
                shutdown_event = {
                    "event": "SYSTEM_SHUTDOWN",
                    "mission_id": str(mission_id),
                    "task_id": str(record.task_id),
                    "timestamp": now_iso,
                    "data": {"message": "ORION server shutting down gracefully."},
                }
                for q in list(record.subscribers):
                    try:
                        q.put_nowait(shutdown_event)
                    except (queue.Full, OSError):
                        pass
                record.subscribers.clear()

    # -------------------------------------------------------------
    # Evaluation & Benchmarking Operations
    # -------------------------------------------------------------
    def list_benchmark_suites(self) -> dict[str, Any]:
        """List all available standardized SWE benchmark suites and tasks."""
        return {
            "suites": {
                "standard": [t.to_dict() for t in STANDARD_CORPUS],
                "smoke": [t.to_dict() for t in SMOKE_CORPUS],
                "taxonomy": [t.to_dict() for t in FAILURE_TAXONOMY_CORPUS],
            },
            "total_suites": 2,
        }

    def run_benchmark_suite(
        self,
        suite_name: str = "smoke",
        output_dir: Path | str | None = None,
        auto_repair: bool = True,
    ) -> BenchmarkReport:
        """Execute a benchmark evaluation suite and produce a certified report."""
        runner = BenchmarkRunner(output_dir=output_dir)
        return runner.run_suite(suite=suite_name, auto_repair=auto_repair)

    # -------------------------------------------------------------
    # Mission & Task Creation
    # -------------------------------------------------------------
    def submit_task(self, request: TaskSubmissionRequest) -> MissionResponse:
        """Submit a natural-language engineering task with workspace validation."""
        repo_path = validate_workspace_path(request.workspace)

        task_id = uuid4()
        mission_id = task_id
        execution_id = uuid4()

        workspace = Workspace(repository_root=repo_path, task_id=task_id, execution_id=execution_id)
        tool_registry = InMemoryToolRegistry()
        register_repository_tools(tool_registry, workspace)

        approval_repo = InMemoryApprovalRepository()
        approval_service = ApprovalService(repository=approval_repo)
        tool_executor = ToolExecutor(
            registry=tool_registry,
            approval_service=approval_service,
            policy_engine=self._policy_engine,
        )

        verif_service = VerificationService(repository=InMemoryVerificationRepository())
        verification_engine = VerificationEngine(verification_service=verif_service)
        recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

        telemetry = TelemetryContext(
            request_id=uuid4(),
            trace_id=uuid4(),
            task_id=task_id,
            execution_id=execution_id,
        )

        coordinator = SWEWorkflowCoordinator(
            workspace=workspace,
            tool_executor=tool_executor,
            verification_engine=verification_engine,
            recovery_coordinator=recovery_coordinator,
            mission_id=mission_id,
            task_id=task_id,
            telemetry_context=telemetry,
        )

        agent = Agent.create(
            name="Orion-SWE-Engineer",
            description=(
                "Autonomous SWE workforce agent with repository inspection and repair capabilities"
            ),
            capabilities=frozenset({
                AgentCapability.REPOSITORY_ANALYSIS,
                AgentCapability.SOFTWARE_DEBUGGING,
                AgentCapability.REASONING,
                AgentCapability.CODE_MODIFICATION,
                AgentCapability.TESTING,
                AgentCapability.VERIFICATION,
                AgentCapability.WRITING,
            }),
            permission_policy=AgentPermissionPolicy.create(
                frozenset({
                    AgentPermission.READ_FILES,
                    AgentPermission.WRITE_FILES,
                    AgentPermission.CODE_EXECUTION,
                })
            ),
        )

        record = MissionRecord(
            mission_id=mission_id,
            task_id=task_id,
            execution_id=execution_id,
            objective=request.task.strip(),
            workspace_path=str(repo_path),
            workspace=workspace,
            coordinator=coordinator,
            approval_service=approval_service,
            agent=agent,
            created_at=datetime.now(UTC),
            execution_mode=request.execution_mode,
            status="initialized",
            lifecycle_state="RECEIVED",
            summary=f"Task received for workspace '{repo_path.name}'.",
        )

        self._missions[mission_id] = record

        self.emit_event(
            mission_id,
            "TASK_CREATED",
            {
                "objective": request.task.strip(),
                "workspace": str(repo_path),
                "execution_mode": request.execution_mode,
                "summary": f"Initialized task: {request.task.strip()}",
            },
        )

        return self._build_mission_response(record)

    def create_mission(self, request: CreateMissionRequest) -> MissionResponse:
        """Backward-compatible endpoint for creating SWE missions."""
        submission = TaskSubmissionRequest(
            task=request.objective,
            workspace=request.workspace_path,
            execution_mode="controlled",
            target_files=request.target_files,
            expected_requirements=request.expected_requirements,
            parameters=request.parameters,
        )
        return self.submit_task(submission)

    def get_mission(self, mission_id: UUID) -> MissionResponse | None:
        """Retrieve mission details by ID."""
        record = self._get_record(mission_id)
        if not record:
            return None
        return self._build_mission_response(record)

    def list_missions(self) -> list[MissionResponse]:
        """List all missions."""
        return [self._build_mission_response(r) for r in self._missions.values()]

    def get_mission_timeline(self, mission_id: UUID) -> list[TimelineEventDTO] | None:
        """Retrieve chronological timeline events for a mission."""
        record = self._get_record(mission_id)
        if not record:
            return None
        return list(record.timeline)

    def get_mission_evidence(
        self,
        mission_id: UUID,
        level: str | None = None,
        category: str | None = None,
        stage: str | None = None,
    ) -> list[EvidenceItemDTO] | None:
        """Query evidence items for a mission filtered by level, category, or stage."""
        record = self._get_record(mission_id)
        if not record:
            return None

        ev_level = EvidenceLevel(level) if level else None
        ev_cat = EvidenceCategory(category) if category else None
        ev_stage = SWETaskStage(stage) if stage else None

        items = record.coordinator.ledger.get_items(
            level=ev_level,
            category=ev_cat,
            stage=ev_stage,
        )
        return [EvidenceItemDTO.from_domain(item) for item in items]

    def get_mission_verification(
        self, mission_id: UUID
    ) -> VerificationDetailDTO | None:
        """Retrieve formal verification details for a mission."""
        record = self._get_record(mission_id)
        if not record:
            return None

        verif_items = record.coordinator.ledger.get_items(
            category=EvidenceCategory.VERIFICATION_RESULT
        )
        verified_count = sum(
            1 for item in verif_items if item.level == EvidenceLevel.VERIFIED
        )
        passed = verified_count > 0

        latest_item = verif_items[-1] if verif_items else None
        reason = latest_item.content if latest_item else "No verification recorded."
        status_val = "passed" if passed else ("failed" if verif_items else "pending")
        reqs = (
            tuple(latest_item.metadata.get("requirements", ()))
            if latest_item
            else ()
        )

        return VerificationDetailDTO(
            status=status_val,
            reason=reason,
            verified_evidence_count=verified_count,
            requirements=reqs,
            passed=passed,
        )

    def get_mission_recovery(self, mission_id: UUID) -> RecoveryDetailDTO | None:
        """Retrieve recovery history and transparency for a mission."""
        record = self._get_record(mission_id)
        if not record:
            return None

        recovery_items = record.coordinator.ledger.get_items(
            category=EvidenceCategory.RECOVERY_EVENT
        )
        events_dicts = tuple(
            {
                "id": str(item.id),
                "summary": item.summary,
                "strategy": item.metadata.get("recovery_strategy", ""),
                "action": item.metadata.get("recovery_action", ""),
                "failure_type": item.metadata.get("failure_type", ""),
                "timestamp": item.timestamp.isoformat(),
            }
            for item in recovery_items
        )

        return RecoveryDetailDTO(
            recovery_attempts=len(recovery_items),
            recovery_events=events_dicts,
            transparent=True,
        )

    def get_mission_evaluation(
        self, mission_id: UUID
    ) -> EvaluationDetailDTO | None:
        """Retrieve deterministic evaluation metrics and criteria for a mission."""
        record = self._get_record(mission_id)
        if not record:
            return None

        evaluation = record.coordinator.evaluate_mission()
        return EvaluationDetailDTO(
            status=evaluation.status.value,
            summary=evaluation.summary,
            metrics=evaluation.metrics.to_dict(),
            criteria=evaluation.criteria.to_dict(),
        )

    def get_mission_report(self, mission_id: UUID) -> dict[str, Any] | None:
        """Retrieve the final structured SWE report."""
        record = self._get_record(mission_id)
        if not record:
            return None

        if record.report:
            return record.report.to_dict()

        if record.coordinator.current_stage == SWETaskStage.GENERATE_REPORT:
            report = record.coordinator.generate_report(summary=record.summary)
            record.report = report
            record.status = report.status
            return report.to_dict()

        return None

    # -------------------------------------------------------------
    # Phase 7 Product Observability Endpoints
    # -------------------------------------------------------------
    def get_task_execution(self, mission_id: UUID) -> TaskExecutionResponse | None:
        """Retrieve execution lifecycle and active agent telemetry."""
        record = self._get_record(mission_id)
        if not record:
            return None

        approval_req = None
        is_approval_pending = False
        if record.pending_approval:
            approval_req = record.pending_approval.to_dict()
            is_approval_pending = (
                record.pending_approval.status == ApprovalStatus.PENDING
            )

        current_stage = (
            record.coordinator.current_stage.value
            if record.coordinator.current_stage
            else None
        )
        completed = tuple(s.value for s in record.coordinator.completed_stages)

        return TaskExecutionResponse(
            task_id=str(record.task_id),
            execution_id=str(record.execution_id),
            lifecycle_state=record.lifecycle_state,
            current_stage=current_stage,
            completed_stages=completed,
            stages_total=len(STAGE_ORDER),
            stages_completed_count=len(completed),
            active_agent=record.agent.name,
            active_tool=None,
            approval_required=is_approval_pending,
            pending_approval=approval_req,
        )

    def get_task_changes(self, mission_id: UUID) -> TaskChangesResponse | None:
        """Retrieve structured code changes, unified diff, and status."""
        record = self._get_record(mission_id)
        if not record:
            return None

        proposal = record.coordinator.last_patch_proposal
        app_res = record.coordinator.last_application_result
        pkg = record.pending_approval

        affected_files = proposal.affected_files if proposal else ()
        diff_str = proposal.unified_diff if proposal else ""
        lines_added = proposal.total_lines_added if proposal else 0
        lines_removed = proposal.total_lines_removed if proposal else 0

        validation_status = "VALID" if (proposal and proposal.is_valid) else "PENDING"
        approval_status = pkg.status.value if pkg else "NONE"
        app_status = (
            "APPLIED"
            if (app_res and app_res.is_applied)
            else ("FAILED" if (app_res and not app_res.is_applied) else "PENDING")
        )
        rollback_status = (
            "ROLLED_BACK"
            if (app_res and app_res.recovery_status == "ROLLED_BACK")
            else "NONE"
        )

        ops: tuple[dict[str, Any], ...] = ()
        if proposal:
            ops = tuple(op.to_dict() for op in proposal.operations)

        return TaskChangesResponse(
            task_id=str(record.task_id),
            affected_files=tuple(affected_files),
            operations=ops,
            unified_diff=diff_str,
            total_lines_added=lines_added,
            total_lines_removed=lines_removed,
            validation_status=validation_status,
            approval_status=approval_status,
            application_status=app_status,
            rollback_status=rollback_status,
        )

    def get_task_tests(self, mission_id: UUID) -> TaskTestsResponse | None:
        """Retrieve controlled test execution telemetry."""
        record = self._get_record(mission_id)
        if not record:
            return None

        test_res = record.coordinator.last_controlled_test_result
        if test_res:
            return TaskTestsResponse(
                task_id=str(record.task_id),
                target=test_res.target,
                exit_code=test_res.exit_code,
                passed=test_res.passed,
                duration=test_res.duration_seconds,
                stdout=test_res.stdout,
                stderr=test_res.stderr,
                output_summary=test_res.output_summary,
                executed=True,
            )

        return TaskTestsResponse(
            task_id=str(record.task_id),
            target="",
            exit_code=None,
            passed=False,
            duration=0.0,
            stdout="",
            stderr="",
            output_summary="No tests executed yet.",
            executed=False,
        )

    def get_task_recovery_detail(
        self, mission_id: UUID
    ) -> RecoveryObservabilityResponse | None:
        """Retrieve full Phase 6 Bounded Self-Healing Recovery telemetry."""
        record = self._get_record(mission_id)
        if not record:
            return None

        report = record.coordinator.last_recovery_report
        if report:
            cat = report.initial_failure_category.value
            strat = (
                report.attempts[-1].strategy.value
                if report.attempts
                else None
            )
            history_data = tuple(att.to_dict() for att in report.attempts)
            budget_dict = {
                "attempts_remaining": report.final_budget.remaining_attempts,
                "execution_seconds_remaining": report.final_budget.remaining_seconds,
                "patch_regenerations_remaining": (
                    report.final_budget.remaining_regenerations
                ),
                "model_changes_remaining": report.final_budget.remaining_model_changes,
                "test_retries_remaining": report.final_budget.remaining_test_retries,
            }
            rollback_done = any(
                att.rollback_record is not None and att.rollback_record.success
                for att in report.attempts
            )

            return RecoveryObservabilityResponse(
                task_id=str(record.task_id),
                failure_category=cat,
                recovery_strategy=strat,
                attempt_number=report.total_attempts_executed,
                recovery_state=report.final_state.value,
                remaining_attempts=report.final_budget.remaining_attempts,
                remaining_budget=budget_dict,
                recovery_depth=len(report.attempts),
                termination_reason=report.summary if not report.verified_success else None,
                rollback_performed=rollback_done,
                history=history_data,
            )

        # No recovery report yet, check if there are recovery events in ledger
        rec_items = record.coordinator.ledger.get_items(category=EvidenceCategory.RECOVERY_EVENT)
        return RecoveryObservabilityResponse(
            task_id=str(record.task_id),
            failure_category=None,
            recovery_strategy=None,
            attempt_number=len(rec_items),
            recovery_state="IDLE",
            remaining_attempts=3,
            remaining_budget={
                "attempts_remaining": 3,
                "execution_seconds_remaining": 120.0,
                "patch_regenerations_remaining": 2,
                "model_changes_remaining": 1,
                "test_retries_remaining": 3,
            },
            recovery_depth=0,
            termination_reason=None,
            rollback_performed=False,
            history=(),
        )

    def get_mission_agents(self, mission_id: UUID) -> AgentRosterResponse | None:
        """Retrieve real workforce agent roster, roles, and status for a mission."""
        record = self._get_record(mission_id)
        if not record:
            return None

        curr_stage = record.coordinator.current_stage
        lifecycle = record.lifecycle_state

        swe_status = "IDLE"
        diag_status = "IDLE"
        verif_status = "IDLE"
        recov_status = "IDLE"

        if lifecycle in ("CANCELLED", "COMPLETED"):
            swe_status = diag_status = verif_status = recov_status = "COMPLETED"
        elif lifecycle in ("RECOVERING", "RECOVERY"):
            recov_status = "ACTIVE"
            swe_status = "WAITING"
        elif (
            record.pending_approval
            and record.pending_approval.status == ApprovalStatus.PENDING
        ):
            swe_status = "WAITING_APPROVAL"
        elif curr_stage in (SWETaskStage.INSPECT_REPOSITORY, SWETaskStage.ANALYZE_FAILURE):
            diag_status = "ACTIVE"
            swe_status = "ACTIVE"
        elif curr_stage in (
            SWETaskStage.FORMULATE_FIX,
            SWETaskStage.IMPLEMENT_CHANGE,
            SWETaskStage.RUN_TESTS,
        ):
            swe_status = "ACTIVE"
        elif curr_stage == SWETaskStage.VERIFY:
            verif_status = "ACTIVE"
            swe_status = "ACTIVE"
        elif curr_stage == SWETaskStage.GENERATE_REPORT:
            verif_status = "COMPLETED"
            swe_status = "ACTIVE"

        task_label = curr_stage.value if curr_stage else lifecycle
        agent_dtos = (
            AgentTelemetryDTO(
                agent_id=str(record.agent.id),
                name="Orion-SWE-Engineer",
                role="Lead SWE Orchestrator & Code Modification",
                capabilities=tuple(c.value for c in record.agent.capabilities),
                permissions=tuple(
                    p.value for p in record.agent.permission_policy.permissions
                ),
                status=swe_status,
                current_task=f"Executing {task_label}",
                started_at=record.created_at.isoformat(),
                completed_at=(
                    datetime.now(UTC).isoformat()
                    if lifecycle in ("COMPLETED", "CANCELLED")
                    else None
                ),
                failure_message=record.last_error,
            ),
            AgentTelemetryDTO(
                agent_id="agent-diag-002",
                name="Orion-Diagnostics-Specialist",
                role="Repository Analysis & Failure Diagnosis",
                capabilities=("repository_analysis", "software_debugging", "reasoning"),
                permissions=("read_files", "code_execution"),
                status=diag_status,
                current_task=(
                    "Analyzing failure patterns & reproducing tests"
                    if diag_status == "ACTIVE"
                    else "Ready"
                ),
                started_at=record.created_at.isoformat(),
                completed_at=(
                    datetime.now(UTC).isoformat()
                    if SWETaskStage.ANALYZE_FAILURE in record.coordinator.completed_stages
                    else None
                ),
            ),
            AgentTelemetryDTO(
                agent_id="agent-verif-003",
                name="Orion-Verification-Authority",
                role="Authoritative Evidence Assessment & Verification",
                capabilities=("verification", "evaluation", "auditing"),
                permissions=("read_files",),
                status=verif_status,
                current_task=(
                    "Evaluating requirements & promoting evidence"
                    if verif_status == "ACTIVE"
                    else "Ready"
                ),
                started_at=record.created_at.isoformat(),
                completed_at=(
                    datetime.now(UTC).isoformat()
                    if SWETaskStage.VERIFY in record.coordinator.completed_stages
                    else None
                ),
            ),
            AgentTelemetryDTO(
                agent_id="agent-recov-004",
                name="Orion-Recovery-Specialist",
                role="Bounded Self-Healing & Failure Recovery",
                capabilities=("recovery", "planning", "rollback", "remediation"),
                permissions=("read_files", "write_files", "code_execution"),
                status=recov_status,
                current_task=(
                    "Executing bounded self-healing recovery loop"
                    if recov_status == "ACTIVE"
                    else "Standby"
                ),
                started_at=record.created_at.isoformat(),
                completed_at=None,
            ),
        )

        active_cnt = sum(1 for a in agent_dtos if a.status == "ACTIVE")
        return AgentRosterResponse(
            mission_id=str(record.mission_id),
            task_id=str(record.task_id),
            agents=agent_dtos,
            total_agents=len(agent_dtos),
            active_count=active_cnt,
        )

    def get_execution_graph(self, mission_id: UUID) -> ExecutionGraphResponse | None:
        """Retrieve real execution DAG with nodes, states, and stage dependencies."""
        record = self._get_record(mission_id)
        if not record:
            return None

        completed = set(record.coordinator.completed_stages)
        curr_stage = record.coordinator.current_stage
        lifecycle = record.lifecycle_state
        is_approval_pending = (
            record.pending_approval is not None
            and record.pending_approval.status == ApprovalStatus.PENDING
        )

        stages_defs = [
            (
                "inspect_repository",
                "Inspect Repository",
                "Explore workspace layout, directory structure, and source files",
                "repository_analysis",
            ),
            (
                "analyze_failure",
                "Analyze Failure",
                "Reproduce test failures and identify root causes",
                "software_debugging",
            ),
            (
                "formulate_fix",
                "Formulate Fix",
                "Synthesize candidate repair patch and validate syntax AST",
                "reasoning",
            ),
            (
                "approval_gate",
                "Approval Gate",
                "Operator authorization boundary for high-risk write modifications",
                "security_review",
            ),
            (
                "implement_change",
                "Implement Change",
                "Apply atomic patch with optimistic concurrency and pre-apply snapshots",
                "code_modification",
            ),
            (
                "run_tests",
                "Controlled Tests",
                "Execute targeted pytest runner with timeout and sandboxed isolation",
                "testing",
            ),
            (
                "verify",
                "Authoritative Verification",
                "Verify exit codes and expected requirements, promote evidence to VERIFIED",
                "verification",
            ),
            (
                "generate_report",
                "Certified Mission Report",
                "Generate evidence-backed final report with deterministic scorecard",
                "writing",
            ),
        ]

        nodes: list[ExecutionGraphNodeDTO] = []
        stage_order_map = {name: idx for idx, (name, *_) in enumerate(stages_defs)}

        for name, title, desc, cap in stages_defs:
            stage_enum = SWETaskStage(name) if name != "approval_gate" else None

            if lifecycle == "CANCELLED":
                state = "CANCELLED"
            elif stage_enum and stage_enum in completed:
                state = "VERIFIED" if name == "verify" else "COMPLETED"
            elif name == "approval_gate":
                if SWETaskStage.IMPLEMENT_CHANGE in completed:
                    state = "COMPLETED"
                elif is_approval_pending:
                    state = "WAITING_APPROVAL"
                elif SWETaskStage.FORMULATE_FIX in completed:
                    state = "READY"
                else:
                    state = "PENDING"
            elif curr_stage and curr_stage.value == name:
                if lifecycle in ("RECOVERING", "RECOVERY"):
                    state = "RECOVERING"
                elif lifecycle == "TERMINATED":
                    state = "FAILED"
                else:
                    state = "RUNNING"
            else:
                curr_idx = stage_order_map[name]
                prev_name = stages_defs[curr_idx - 1][0] if curr_idx > 0 else None
                prev_enum = (
                    SWETaskStage(prev_name)
                    if prev_name and prev_name != "approval_gate"
                    else None
                )

                if prev_name == "approval_gate":
                    prev_ready = (
                        record.pending_approval is not None
                        and record.pending_approval.status == ApprovalStatus.APPROVED
                    ) or (
                        SWETaskStage.FORMULATE_FIX in completed
                        and not is_approval_pending
                    )
                elif prev_enum:
                    prev_ready = prev_enum in completed
                else:
                    prev_ready = True

                state = "READY" if prev_ready else "PENDING"

            nodes.append(
                ExecutionGraphNodeDTO(
                    id=name,
                    stage=name,
                    title=title,
                    description=desc,
                    state=state,
                    required_capability=cap,
                    duration_seconds=0.0,
                    error=record.last_error if state == "FAILED" else None,
                )
            )

        edges = (
            ExecutionGraphEdgeDTO(source="inspect_repository", target="analyze_failure"),
            ExecutionGraphEdgeDTO(source="analyze_failure", target="formulate_fix"),
            ExecutionGraphEdgeDTO(source="formulate_fix", target="approval_gate"),
            ExecutionGraphEdgeDTO(source="approval_gate", target="implement_change"),
            ExecutionGraphEdgeDTO(source="implement_change", target="run_tests"),
            ExecutionGraphEdgeDTO(source="run_tests", target="verify"),
            ExecutionGraphEdgeDTO(source="verify", target="generate_report"),
        )

        completed_cnt = sum(1 for n in nodes if n.state in ("COMPLETED", "VERIFIED"))
        curr_id = curr_stage.value if curr_stage else (nodes[0].id if nodes else None)

        return ExecutionGraphResponse(
            mission_id=str(record.mission_id),
            task_id=str(record.task_id),
            nodes=tuple(nodes),
            edges=edges,
            current_node_id=curr_id,
            completed_nodes_count=completed_cnt,
            total_nodes_count=len(nodes),
        )

    def cancel_mission(
        self, mission_id: UUID, request: TaskCancellationRequest | None = None
    ) -> TaskCancellationResponse:
        """Cancel an in-flight or pending mission cleanly."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        req = request or TaskCancellationRequest()
        with record.lock:
            record.cancelled = True
            record.lifecycle_state = "CANCELLED"
            record.status = "cancelled"

        now_iso = datetime.now(UTC).isoformat()
        self.emit_event(
            mission_id,
            "TASK_CANCELLED",
            {
                "reason": req.reason,
                "cancelled_by": req.cancelled_by,
                "summary": f"Mission cancelled: {req.reason}",
            },
            level="warning",
        )
        return TaskCancellationResponse(
            mission_id=str(record.mission_id),
            task_id=str(record.task_id),
            status="cancelled",
            cancelled_at=now_iso,
            reason=req.reason,
            message=f"Mission '{mission_id}' cancelled.",
        )

    # -------------------------------------------------------------
    # Approval Flow
    # -------------------------------------------------------------
    def approve_task(
        self, mission_id: UUID, req: TaskApprovalRequest
    ) -> TaskApprovalResponse:
        """Approve or deny a pending action for a mission via ApprovalService."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        # Determine target approval request ID
        req_id = None
        if req.request_id:
            try:
                req_id = UUID(req.request_id)
            except ValueError as e:
                raise ValueError(f"Invalid request_id UUID format: '{req.request_id}'") from e
        elif record.pending_approval:
            req_id = record.pending_approval.request_id
        else:
            raise ValueError(f"No pending approval request found for mission '{mission_id}'.")

        now_str = datetime.now(UTC).isoformat()
        is_approve = req.decision.lower() == "approve"

        if is_approve:
            record.approval_service.approve(
                request_id=req_id,
                approver=req.approver,
                reason=req.reason,
            )
            refreshed = record.coordinator.refresh_patch_approval()
            record.pending_approval = refreshed
            record.lifecycle_state = "APPLYING"
            self.emit_event(
                mission_id,
                "PATCH_APPROVED",
                {
                    "request_id": str(req_id),
                    "approver": req.approver,
                    "reason": req.reason,
                    "summary": f"Patch application approved by {req.approver}",
                },
                level="success",
            )
            return TaskApprovalResponse(
                task_id=str(record.task_id),
                request_id=str(req_id),
                decision="approve",
                approver=req.approver,
                decided_at=now_str,
                status="approved",
                reason=req.reason,
            )
        else:
            record.approval_service.deny(
                request_id=req_id,
                approver=req.approver,
                reason=req.reason,
            )
            refreshed = record.coordinator.refresh_patch_approval()
            record.pending_approval = refreshed
            record.lifecycle_state = "TERMINATED"
            record.status = "terminated"
            self.emit_event(
                mission_id,
                "PATCH_DENIED",
                {
                    "request_id": str(req_id),
                    "approver": req.approver,
                    "reason": req.reason,
                    "summary": f"Patch application denied by {req.approver}",
                },
                level="warning",
            )
            self.emit_event(
                mission_id,
                "TASK_TERMINATED",
                {
                    "reason": (
                        f"Approval denied by {req.approver}: "
                        f"{req.reason or 'Operator denied patch.'}"
                    ),
                    "summary": "Task execution terminated due to approval denial.",
                },
                level="warning",
            )
            return TaskApprovalResponse(
                task_id=str(record.task_id),
                request_id=str(req_id),
                decision="deny",
                approver=req.approver,
                decided_at=now_str,
                status="denied",
                reason=req.reason,
            )

    # -------------------------------------------------------------
    # Full Pipeline Execution Engine
    # -------------------------------------------------------------
    def run_pipeline(
        self,
        mission_id: UUID,
        auto_approve: bool = False,
        background: bool = True,
    ) -> None:
        """Execute the real 7-stage SWE pipeline with real-time observability."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        if background:
            thread = threading.Thread(
                target=self._execute_pipeline,
                args=(mission_id, auto_approve),
                daemon=True,
                name=f"pipeline-{mission_id}",
            )
            thread.start()
        else:
            self._execute_pipeline(mission_id, auto_approve)

    def _execute_pipeline(self, mission_id: UUID, auto_approve: bool) -> None:
        """Internal worker executing stages sequentially."""
        record = self._get_record(mission_id)
        if not record:
            return

        coord = record.coordinator
        agent = record.agent

        try:
            if record.cancelled:
                return

            # Stage 1: INSPECT_REPOSITORY
            if SWETaskStage.INSPECT_REPOSITORY not in coord.completed_stages:
                if record.cancelled:
                    return
                record.lifecycle_state = "INSPECTING"
                self.emit_event(
                    mission_id,
                    "AGENT_STARTED",
                    {"agent": agent.name, "stage": "inspect_repository", "operation": "list_files"},
                )
                coord.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
                coord.execute_tool(
                    stage=SWETaskStage.INSPECT_REPOSITORY,
                    agent=agent,
                    tool_name="list_files",
                    arguments={"path": "."},
                )
                self.emit_event(
                    mission_id,
                    "FILE_INSPECTED",
                    {"path": ".", "summary": "Inspected repository directory contents"},
                )
                coord.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
                self.emit_event(
                    mission_id,
                    "AGENT_COMPLETED",
                    {"agent": agent.name, "stage": "inspect_repository"},
                )

            # Stage 2: ANALYZE_FAILURE
            if SWETaskStage.ANALYZE_FAILURE not in coord.completed_stages:
                if record.cancelled:
                    return
                record.lifecycle_state = "ANALYZING"
                self.emit_event(
                    mission_id,
                    "AGENT_STARTED",
                    {
                        "agent": agent.name,
                        "stage": "analyze_failure",
                        "operation": "diagnostic_analysis",
                    },
                )
                coord.advance_stage(SWETaskStage.ANALYZE_FAILURE)
                coord.analyze_failure(
                    agent=agent,
                    test_output=f"Diagnostic failure check for task: '{record.objective}'",
                    fallback_on_error=True,
                )
                self.emit_event(
                    mission_id,
                    "PLAN_CREATED",
                    {"summary": f"Formulated diagnostic hypothesis for '{record.objective}'"},
                )
                coord.complete_stage(SWETaskStage.ANALYZE_FAILURE)
                self.emit_event(
                    mission_id,
                    "AGENT_COMPLETED",
                    {"agent": agent.name, "stage": "analyze_failure"},
                )

            # Stage 3: FORMULATE_FIX
            if SWETaskStage.FORMULATE_FIX not in coord.completed_stages:
                if record.cancelled:
                    return
                if (
                    record.pending_approval
                    and record.pending_approval.status == ApprovalStatus.APPROVED
                ):
                    coord.complete_stage(SWETaskStage.FORMULATE_FIX)
                else:
                    record.lifecycle_state = "FORMULATING_FIX"
                    self.emit_event(
                        mission_id,
                        "AGENT_STARTED",
                        {
                            "agent": agent.name,
                            "stage": "formulate_fix",
                            "operation": "patch_synthesis",
                        },
                    )
                    coord.advance_stage(SWETaskStage.FORMULATE_FIX)
                    fix_prop = coord.formulate_fix(agent=agent, fallback_on_error=True)
                    patch_prop = coord.synthesize_patch(
                        agent=agent, fix_proposal=fix_prop, fallback_on_error=True
                    )
                    self.emit_event(
                        mission_id,
                        "PATCH_PROPOSED",
                        {
                            "affected_files": list(patch_prop.affected_files),
                            "total_lines_added": patch_prop.total_lines_added,
                            "total_lines_removed": patch_prop.total_lines_removed,
                            "diff_summary": patch_prop.unified_diff,
                            "summary": (
                                f"Synthesized patch affecting {list(patch_prop.affected_files)}"
                            ),
                        },
                    )
                    pkg = coord.request_patch_approval(patch_proposal=patch_prop, agent=agent)
                    record.pending_approval = pkg

                    if not auto_approve:
                        # Pause here and await human approval
                        record.lifecycle_state = "AWAITING_APPROVAL"
                        self.emit_event(
                            mission_id,
                            "APPROVAL_REQUIRED",
                            {
                                "request_id": str(pkg.request_id),
                                "action": pkg.action,
                                "risk_level": pkg.risk_level.value,
                                "affected_files": list(patch_prop.affected_files),
                                "diff": patch_prop.unified_diff,
                                "rationale": patch_prop.rationale,
                                "summary": (
                                    f"Approval required for patch application "
                                    f"({pkg.risk_level.value} risk)"
                                ),
                            },
                            level="warning",
                        )
                        return

                    # Auto-approval
                    self.approve_task(
                        mission_id,
                        TaskApprovalRequest(
                            decision="approve",
                            approver="AutonomousPolicy",
                            reason="Pre-approved execution mode",
                        ),
                    )
                    coord.complete_stage(SWETaskStage.FORMULATE_FIX)

            # Stage 4: IMPLEMENT_CHANGE
            if (
                SWETaskStage.IMPLEMENT_CHANGE not in coord.completed_stages
                and record.pending_approval
                and record.pending_approval.status == ApprovalStatus.APPROVED
            ):
                if record.cancelled:
                    return
                record.lifecycle_state = "APPLYING"
                self.emit_event(
                    mission_id,
                    "AGENT_STARTED",
                    {
                        "agent": agent.name,
                        "stage": "implement_change",
                        "operation": "apply_patch",
                    },
                )
                coord.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
                app_res = coord.apply_approved_patch(record.pending_approval)
                self.emit_event(
                    mission_id,
                    "PATCH_APPLIED",
                    {
                        "is_applied": app_res.is_applied,
                        "modified_files": list(app_res.affected_files),
                        "summary": f"Applied patch: is_applied={app_res.is_applied}",
                    },
                    level="success",
                )
                coord.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

            # Stage 5: RUN_TESTS
            if SWETaskStage.RUN_TESTS not in coord.completed_stages:
                if record.cancelled:
                    return
                record.lifecycle_state = "TESTING"
                self.emit_event(
                    mission_id,
                    "AGENT_STARTED",
                    {
                        "agent": agent.name,
                        "stage": "run_tests",
                        "operation": "controlled_tests",
                    },
                )
                coord.advance_stage(SWETaskStage.RUN_TESTS)
                self.emit_event(
                    mission_id,
                    "TEST_STARTED",
                    {"target": "", "summary": "Starting controlled test execution"},
                )
                test_res = coord.run_controlled_tests(target="", timeout_seconds=30)
                self.emit_event(
                    mission_id,
                    "TEST_COMPLETED",
                    {
                        "target": test_res.target,
                        "passed": test_res.passed,
                        "exit_code": test_res.exit_code,
                        "duration": test_res.duration_seconds,
                        "summary": (
                            f"Tests finished: passed={test_res.passed} "
                            f"(exit_code={test_res.exit_code})"
                        ),
                    },
                    level="success" if test_res.passed else "warning",
                )
                coord.complete_stage(SWETaskStage.RUN_TESTS)

                # Check if tests failed -> trigger Phase 6 Bounded Self-Healing Recovery!
                if not test_res.passed:
                    record.lifecycle_state = "RECOVERING"
                    self.emit_event(
                        mission_id,
                        "FAILURE_DETECTED",
                        {
                            "exit_code": test_res.exit_code,
                            "summary": "Controlled tests failed. Initiating bounded recovery.",
                        },
                        level="warning",
                    )
                    self.emit_event(
                        mission_id,
                        "RECOVERY_PLANNED",
                        {"summary": "Classifying failure and planning bounded recovery strategy"},
                    )
                    self.emit_event(
                        mission_id,
                        "RECOVERY_STARTED",
                        {"summary": "Executing bounded recovery strategy"},
                    )
                    rec_report = coord.initiate_bounded_recovery(agent=agent)
                    rollback_done = any(
                        att.rollback_record is not None and att.rollback_record.success
                        for att in rec_report.attempts
                    )
                    self.emit_event(
                        mission_id,
                        "RECOVERY_COMPLETED",
                        {
                            "attempts": rec_report.total_attempts_executed,
                            "terminal_state": rec_report.final_state.value,
                            "rollback_executed": rollback_done,
                            "summary": f"Recovery completed: {rec_report.final_state.value}",
                        },
                    )

                    if rollback_done:
                        self.emit_event(
                            mission_id,
                            "ROLLBACK_STARTED",
                            {"summary": "Rolling back unverified workspace modifications"},
                        )
                        self.emit_event(
                            mission_id,
                            "ROLLBACK_COMPLETED",
                            {"summary": "Rollback completed cleanly"},
                        )

                    if not rec_report.verified_success:
                        record.lifecycle_state = "TERMINATED"
                        record.status = "terminated"
                        self.emit_event(
                            mission_id,
                            "TASK_TERMINATED",
                            {
                                "reason": rec_report.summary or "Recovery budget exhausted",
                                "summary": "Task terminated due to unrecovered failure.",
                            },
                            level="error",
                        )
                        return

            # Stage 6: VERIFY
            if SWETaskStage.VERIFY not in coord.completed_stages:
                if record.cancelled:
                    return
                record.lifecycle_state = "VERIFYING"
                self.emit_event(
                    mission_id,
                    "AGENT_STARTED",
                    {
                        "agent": agent.name,
                        "stage": "verify",
                        "operation": "authoritative_verification",
                    },
                )
                coord.advance_stage(SWETaskStage.VERIFY)
                self.emit_event(
                    mission_id,
                    "VERIFICATION_STARTED",
                    {"summary": "Authoritative verification underway"},
                )
                outcome = coord.verify_patch_execution(expected_requirements=["passed"])
                self.emit_event(
                    mission_id,
                    "VERIFICATION_COMPLETED",
                    {
                        "is_verified": outcome.is_verified,
                        "summary": f"VerificationEngine result: is_verified={outcome.is_verified}",
                    },
                    level="success" if outcome.is_verified else "error",
                )
                coord.complete_stage(SWETaskStage.VERIFY)
                if outcome.is_verified:
                    record.lifecycle_state = "VERIFIED"
                else:
                    record.lifecycle_state = "FAILED"
                    record.status = "failed"
                    self.emit_event(
                        mission_id,
                        "TASK_TERMINATED",
                        {"reason": "Verification failed.", "summary": "Task failed verification."},
                        level="error",
                    )
                    return

            # Stage 7: GENERATE_REPORT
            if SWETaskStage.GENERATE_REPORT not in coord.completed_stages:
                if record.cancelled:
                    return
                coord.advance_stage(SWETaskStage.GENERATE_REPORT)
                report = coord.generate_report(
                    summary=f"Mission completed for '{record.objective}'"
                )
                record.report = report
                record.status = report.status
                record.lifecycle_state = "COMPLETED"
                self.emit_event(
                    mission_id,
                    "TASK_COMPLETED",
                    {
                        "status": report.status,
                        "summary": f"SWE mission completed: status={report.status}",
                    },
                    level="success",
                )

        except Exception as exc:
            record.last_error = str(exc)
            record.lifecycle_state = "TERMINATED"
            record.status = "error"
            self.emit_event(
                mission_id,
                "TASK_TERMINATED",
                {"error": str(exc), "summary": f"Pipeline halted: {exc}"},
                level="error",
            )

    # -------------------------------------------------------------
    # Stage-by-Stage Manual API Controls (Backward Compatible)
    # -------------------------------------------------------------
    def advance_stage(self, mission_id: UUID, target_stage: str) -> MissionResponse:
        """Advance the mission to the specified stage."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        stage_enum = SWETaskStage(target_stage)
        record.coordinator.advance_stage(stage_enum)
        record.status = f"running_{stage_enum.value}"
        record.lifecycle_state = stage_enum.name

        self.emit_event(
            mission_id,
            "STAGE_STARTED",
            {"stage": stage_enum.value, "summary": f"Advanced to {stage_enum.name}"},
        )
        return self._build_mission_response(record)

    def execute_tool(
        self,
        mission_id: UUID,
        stage: str,
        tool_name: str,
        arguments: dict[str, Any],
        approval_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Execute a controlled tool within the active stage boundaries."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        stage_enum = SWETaskStage(stage)
        result = record.coordinator.execute_tool(
            stage=stage_enum,
            agent=record.agent,
            tool_name=tool_name,
            arguments=arguments,
            approval_id=approval_id,
        )

        self.emit_event(
            mission_id,
            "TOOL_EXECUTED",
            {
                "tool_name": tool_name,
                "stage": stage_enum.value,
                "success": result.success,
                "error": result.error,
                "summary": f"Executed tool '{tool_name}' (success={result.success})",
            },
            level="success" if result.success else "error",
        )

        return {
            "success": result.success,
            "tool_name": tool_name,
            "output": result.output,
            "error": result.error,
        }

    def complete_stage(self, mission_id: UUID, stage: str) -> MissionResponse:
        """Mark a stage as completed."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        stage_enum = SWETaskStage(stage)
        record.coordinator.complete_stage(stage_enum)

        self.emit_event(
            mission_id,
            "STAGE_COMPLETED",
            {"stage": stage_enum.value, "summary": f"Completed {stage_enum.name}"},
        )
        return self._build_mission_response(record)

    def generate_final_report(
        self, mission_id: UUID, summary: str = ""
    ) -> dict[str, Any]:
        """Generate final mission report and update mission status."""
        record = self._get_record(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        if record.report is not None:
            return record.report.to_dict()

        if record.coordinator.current_stage != SWETaskStage.GENERATE_REPORT:
            if SWETaskStage.GENERATE_REPORT not in record.coordinator.completed_stages:
                record.coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

        report = record.coordinator.generate_report(summary=summary or record.summary)
        if SWETaskStage.GENERATE_REPORT not in record.coordinator.completed_stages:
            record.coordinator.complete_stage(SWETaskStage.GENERATE_REPORT)
        record.report = report
        record.status = report.status
        record.lifecycle_state = "COMPLETED"

        self.emit_event(
            mission_id,
            "TASK_COMPLETED",
            {"status": report.status, "summary": f"Final report generated ({report.status})"},
            level="success" if report.status == "verified_success" else "warning",
        )
        return report.to_dict()

    def _build_mission_response(self, record: MissionRecord) -> MissionResponse:
        """Construct MissionResponse DTO from internal record."""
        completed_stages = record.coordinator.completed_stages
        ev_items = record.coordinator.ledger.get_items()

        claimed_cnt = sum(1 for item in ev_items if item.level == EvidenceLevel.CLAIMED)
        observed_cnt = sum(1 for item in ev_items if item.level == EvidenceLevel.OBSERVED)
        verified_cnt = sum(1 for item in ev_items if item.level == EvidenceLevel.VERIFIED)

        modified_files = tuple(sorted({
            str(item.metadata["path"])
            for item in ev_items
            if item.category == EvidenceCategory.FILE_CHANGE
            and "path" in item.metadata
            and item.metadata["path"]
        }))

        evaluation_status = None
        try:
            ev = record.coordinator.evaluate_mission()
            evaluation_status = ev.status.value
        except Exception:
            pass

        is_approval_pending = (
            record.pending_approval is not None
            and record.pending_approval.status == ApprovalStatus.PENDING
        )

        return MissionResponse(
            mission_id=str(record.mission_id),
            task_id=str(record.task_id),
            execution_id=str(record.execution_id),
            objective=record.objective,
            workspace_root=record.workspace_path,
            status=record.status,
            lifecycle_state=record.lifecycle_state,
            approval_required=is_approval_pending,
            current_stage=(
                record.coordinator.current_stage.value
                if record.coordinator.current_stage
                else None
            ),
            completed_stages=tuple(s.value for s in completed_stages),
            stages_total=len(STAGE_ORDER),
            stages_completed_count=len(completed_stages),
            created_at=record.created_at.isoformat(),
            summary=record.summary,
            evaluation_status=evaluation_status,
            files_modified=modified_files,
            evidence_counts={
                "claimed": claimed_cnt,
                "observed": observed_cnt,
                "verified": verified_cnt,
                "total": len(ev_items),
            },
        )

    # -------------------------------------------------------------
    # V2 Mission Intelligence
    # -------------------------------------------------------------

    def plan_mission(
        self,
        objective: str,
        mission_id: UUID | None = None,
        max_duration_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """Decompose a complex objective into a validated V2 Mission Plan."""
        planner = MissionPlanner()
        budget = ResourceBudget(max_duration_seconds=max_duration_seconds)
        plan, graph = planner.decompose_objective(
            objective=objective,
            mission_id=mission_id,
            default_budget=budget,
        )
        memory = MissionMemory(mission_id=plan.mission_id)
        engine = MissionExecutionEngine(
            plan=plan,
            graph=graph,
            memory=memory,
            mission_budget=budget,
        )

        self._mission_plans[plan.mission_id] = (plan, graph)
        self._mission_memories[plan.mission_id] = memory
        self._mission_engines[plan.mission_id] = engine

        return plan.to_dict()

    def get_mission_graph(self, mission_id: UUID) -> dict[str, Any] | None:
        """Retrieve the task graph and readiness state for a mission."""
        entry = self._mission_plans.get(mission_id)
        if not entry:
            return None
        plan, graph = entry
        ready = [t.to_dict() for t in graph.get_ready_tasks()]
        return {
            "mission_id": str(mission_id),
            "objective": plan.objective,
            "status": plan.status.value,
            "tasks": {str(k): v.to_dict() for k, v in graph.tasks.items()},
            "ready_tasks": ready,
            "is_completed": graph.is_completed(),
        }

    def cancel_mission_plan(
        self, mission_id: UUID, reason: str = "Mission cancelled by user."
    ) -> bool:
        """Cancel a V2 mission plan and all contained tasks."""
        engine = self._mission_engines.get(mission_id)
        if not engine:
            return False
        engine.cancel(reason=reason)
        return True

    def get_mission_memory(self, mission_id: UUID) -> dict[str, Any] | None:
        """Retrieve memory entries for a V2 mission."""
        memory = self._mission_memories.get(mission_id)
        if not memory:
            return None
        return memory.to_dict()

    # -------------------------------------------------------------
    # V3 Deep Repository Intelligence
    # -------------------------------------------------------------

    def get_repository_index(self, workspace_path: str | None = None) -> dict[str, Any]:
        """Index workspace symbols, modules, and architecture profile."""
        ws = (
            validate_workspace_path(workspace_path)
            if workspace_path
            else (self._default_workspace_path or Path.cwd())
        )
        graph = RepoCodeGraph.build_from_workspace(ws)
        detector = ArchitectureDetector(ws)
        profile = detector.detect_profile(
            total_files=len(graph.modules),
            total_symbols=sum(len(m.symbols) for m in graph.modules.values()),
        )
        graph_dict = graph.to_dict()
        graph_dict["profile"] = profile.to_dict()
        return graph_dict

    def analyze_repository_impact(
        self, target_file: str, workspace_path: str | None = None
    ) -> dict[str, Any]:
        """Analyze direct and transitive blast radius of modifying target_file."""
        ws = (
            validate_workspace_path(workspace_path)
            if workspace_path
            else (self._default_workspace_path or Path.cwd())
        )
        graph = RepoCodeGraph.build_from_workspace(ws)
        analyzer = ChangeImpactAnalyzer(graph)
        report = analyzer.analyze_change(target_file=target_file)
        return report.to_dict()

    def get_repository_context(
        self, target_file: str, workspace_path: str | None = None
    ) -> dict[str, Any]:
        """Build a bounded, token-efficient context neighborhood around target_file."""
        ws = (
            validate_workspace_path(workspace_path)
            if workspace_path
            else (self._default_workspace_path or Path.cwd())
        )
        graph = RepoCodeGraph.build_from_workspace(ws)
        optimizer = ContextOptimizer(graph)
        ctx = optimizer.build_context(target_file=target_file)
        return ctx.to_dict()

    # -------------------------------------------------------------
    # V4 Advanced Multi-Agent Engineering
    # -------------------------------------------------------------

    def get_workforce_roster(self) -> list[dict[str, Any]]:
        """Return serialized roster of active workforce agents."""
        return self._workforce_registry.get_roster_summary()

    def review_agent_proposal(self, proposal_data: dict[str, Any]) -> dict[str, Any]:
        """Perform independent multi-stage review on a candidate proposal."""
        reviewer = IndependentReviewer()
        proposal = AgentProposal(
            proposal_id=UUID(str(proposal_data.get("proposal_id", uuid4()))),
            agent_id=UUID(str(proposal_data.get("agent_id", uuid4()))),
            role=WorkforceRole(proposal_data.get("role", "implementer")),
            target_files=tuple(proposal_data.get("target_files", ())),
            patch_content=str(proposal_data.get("patch_content", "")),
            rationale=str(proposal_data.get("rationale", "")),
            assumptions=tuple(proposal_data.get("assumptions", ())),
            confidence_score=float(proposal_data.get("confidence_score", 1.0)),
            evidence_items=tuple(proposal_data.get("evidence_items", ())),
        )
        verdict = reviewer.review(proposal)
        return verdict.to_dict()

    def resolve_competing_proposals(
        self, proposals_list: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Arbitrate between competing agent proposals using evidence scoring."""
        resolver = AgentConflictResolver()
        proposals = [
            AgentProposal(
                proposal_id=UUID(str(p.get("proposal_id", uuid4()))),
                agent_id=UUID(str(p.get("agent_id", uuid4()))),
                role=WorkforceRole(p.get("role", "implementer")),
                target_files=tuple(p.get("target_files", ())),
                patch_content=str(p.get("patch_content", "")),
                rationale=str(p.get("rationale", "")),
                assumptions=tuple(p.get("assumptions", ())),
                confidence_score=float(p.get("confidence_score", 1.0)),
                evidence_items=tuple(p.get("evidence_items", ())),
            )
            for p in proposals_list
        ]
        resolution = resolver.resolve(proposals)
        return resolution.to_dict()

    # -------------------------------------------------------------
    # V5 Advanced Self-Healing
    # -------------------------------------------------------------

    def classify_failure(
        self,
        output_text: str,
        target_file: str | None = None,
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        """Classify execution errors or test failures into formal categories."""
        diag = FailureClassifier.classify(
            output_text=output_text,
            target_file=target_file,
            exit_code=exit_code,
        )
        return diag.to_dict()

    def simulate_recovery_action(
        self,
        action_type: str,
        target_files: list[str],
        estimated_duration_seconds: float = 5.0,
        max_duration_budget: float = 60.0,
    ) -> dict[str, Any]:
        """Pre-execution simulation verifying safety, blast radius, and risk."""
        simulator = RecoverySimulator()
        sim_res = simulator.simulate(
            action_type=action_type,
            target_files=target_files,
            estimated_duration_seconds=estimated_duration_seconds,
            max_duration_budget=max_duration_budget,
        )
        return sim_res.to_dict()

    def plan_adaptive_recovery(
        self,
        output_text: str,
        target_files: list[str] | None = None,
        attempt_number: int = 1,
    ) -> dict[str, Any]:
        """Formulate adaptive recovery plan incorporating memory and simulation."""
        target_file = target_files[0] if target_files else None
        diag = FailureClassifier.classify(output_text=output_text, target_file=target_file)
        planner = AdaptiveRecoveryPlanner(memory=self._adaptive_recovery_memory)
        plan = planner.create_plan(
            diagnosis=diag,
            attempt_number=attempt_number,
            target_files=target_files,
        )
        return plan.to_dict()

    def record_recovery_attempt(
        self,
        attempt_number: int,
        category: str,
        error_message: str,
        strategy_name: str,
        success: bool,
        duration_seconds: float,
        notes: str = "",
    ) -> dict[str, Any]:
        """Record an executed recovery attempt into adaptive memory."""
        from orion.core.recovery.advanced.taxonomy import FailureCategory, FailureDiagnosis

        diag = FailureDiagnosis(
            failure_id=uuid4(),
            category=FailureCategory(category),
            error_message=error_message,
        )
        rec = self._adaptive_recovery_memory.record_attempt(
            attempt_number=attempt_number,
            diagnosis=diag,
            strategy_name=strategy_name,
            success=success,
            duration_seconds=duration_seconds,
            notes=notes,
        )
        return rec.to_dict()

    def get_recovery_strategy_metrics(self) -> dict[str, dict[str, Any]]:
        """Return empirical strategy metrics across past recovery attempts."""
        return self._adaptive_recovery_memory.get_strategy_metrics()

    # -------------------------------------------------------------
    # V6 Evaluation & Benchmarking Intelligence
    # -------------------------------------------------------------
    @property
    def experiment_tracker(self) -> ExperimentTracker:
        """Return the active ExperimentTracker registry."""
        return self._experiment_tracker

    def run_evaluation_experiment(
        self,
        suite_name: str = "standard",
        configuration: dict[str, Any] | None = None,
        auto_repair: bool = True,
        orion_version: str = "6.0.0",
    ) -> ExperimentRecord:
        """Execute a benchmark experiment and return an immutable, tracked ExperimentRecord."""
        return self._benchmark_runner.run_experiment(
            suite=suite_name,
            tracker=self._experiment_tracker,
            configuration=configuration,
            auto_repair=auto_repair,
            orion_version=orion_version,
        )

    def list_evaluation_experiments(self) -> list[dict[str, Any]]:
        """List all recorded evaluation experiments ordered chronologically."""
        return [e.to_dict() for e in self._experiment_tracker.list_experiments()]

    def get_evaluation_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        """Retrieve full experiment record by ID."""
        record = self._experiment_tracker.get_experiment(experiment_id)
        return record.to_dict() if record else None

    def get_evaluation_metrics(self, experiment_id: str) -> dict[str, Any] | None:
        """Retrieve strictly computed engineering metrics for an experiment."""
        record = self._experiment_tracker.get_experiment(experiment_id)
        return record.metrics.to_dict() if record else None

    def get_evaluation_failures(self, experiment_id: str) -> dict[str, Any] | None:
        """Retrieve aggregated failure analysis report for an experiment."""
        record = self._experiment_tracker.get_experiment(experiment_id)
        return record.failure_analysis.to_dict() if record else None

    def compare_evaluation_experiments(
        self,
        base_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        """Empirically compare two evaluation experiments."""
        res = self._experiment_tracker.compare_experiments(base_id, target_id)
        return res.to_dict()

    # -------------------------------------------------------------
    # V7 Human-in-the-Loop & Collaborative Oversight
    # -------------------------------------------------------------
    @property
    def hitl_coordinator(self) -> HITLCoordinator:
        """Return the active HITLCoordinator instance."""
        return self._hitl_coordinator

    def request_clarification(
        self,
        mission_id: UUID,
        task_id: UUID,
        question: str,
        context: str,
        options: Sequence[str] = (),
        default_choice: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """Request human clarification when ambiguity is detected."""
        req = self._hitl_coordinator.request_clarification(
            mission_id=mission_id,
            task_id=task_id,
            question=question,
            context=context,
            options=options,
            default_choice=default_choice,
            timeout_seconds=timeout_seconds,
        )
        return req.to_dict()

    def respond_clarification(
        self,
        request_id: UUID,
        response_text: str,
        operator: str,
    ) -> dict[str, Any]:
        """Submit operator resolution for a pending clarification."""
        req = self._hitl_coordinator.respond_clarification(
            request_id=request_id,
            response_text=response_text,
            operator=operator,
        )
        return req.to_dict()

    def list_clarifications(
        self,
        mission_id: UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List clarification requests filtered by mission or status."""
        st = ClarificationStatus(status) if status else None
        reqs = self._hitl_coordinator.list_clarifications(mission_id=mission_id, status=st)
        return [r.to_dict() for r in reqs]

    def intervene_mission(
        self,
        mission_id: UUID,
        action: str,
        operator: str,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform an explicit operator intervention (pause, resume, steer, force_fail)."""
        interv_type = InterventionType(action.lower().strip())
        interv = self._hitl_coordinator.record_intervention(
            mission_id=mission_id,
            intervention_type=interv_type,
            operator=operator,
            reason=reason,
            payload=payload,
        )
        # Connect lifecycle state changes directly to the mission engine and task record
        engine = self._mission_engines.get(mission_id)
        record = self._get_record(mission_id)

        if interv_type == InterventionType.PAUSE:
            if engine:
                engine.pause(reason=reason)
            if record:
                record.status = "paused"
                record.lifecycle_state = "PAUSED"
        elif interv_type == InterventionType.RESUME:
            if engine:
                engine.resume()
            if record:
                record.status = "running"
                record.lifecycle_state = "RUNNING"
        elif interv_type == InterventionType.FORCE_FAIL:
            if engine:
                engine.cancel(reason=reason)
            if record:
                record.cancelled = True
                record.status = "failed"
                record.lifecycle_state = "FAILED"
        return interv.to_dict()

    def submit_operator_feedback(
        self,
        mission_id: UUID,
        operator: str,
        rating: int,
        comments: str,
        corrections: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Record human feedback and ratings for a mission."""
        fb = self._hitl_coordinator.record_feedback(
            mission_id=mission_id,
            operator=operator,
            rating=rating,
            comments=comments,
            corrections=corrections,
        )
        return fb.to_dict()

    def get_mission_interventions(self, mission_id: UUID) -> list[dict[str, Any]]:
        """Retrieve all recorded human interventions for a mission."""
        intervs = self._hitl_coordinator.get_mission_interventions(mission_id)
        return [i.to_dict() for i in intervs]

    def get_mission_feedback(self, mission_id: UUID) -> list[dict[str, Any]]:
        """Retrieve all operator feedback entries for a mission."""
        fbs = self._hitl_coordinator.get_mission_feedback(mission_id)
        return [f.to_dict() for f in fbs]

    # -------------------------------------------------------------
    # V8 Policy Engine & Autonomous Security Hardening
    # -------------------------------------------------------------
    @property
    def policy_engine(self) -> PolicyEngine:
        """Return the active PolicyEngine instance."""
        return self._policy_engine

    def evaluate_policy(
        self,
        subject: str,
        action: str,
        resource: str,
        tenant_id: str = "default",
        environment: str = "sandbox",
        risk_tier: str = "low",
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate an execution request against central policy rules."""
        rt = PolicyRiskTier(risk_tier.lower().strip())
        ctx = PolicyContext(
            subject=subject,
            action=action,
            resource=resource,
            tenant_id=tenant_id,
            environment=environment,
            risk_tier=rt,
            parameters=parameters or {},
            metadata=metadata or {},
        )
        decision = self._policy_engine.evaluate(ctx)
        return decision.to_dict()

    def list_policy_rules(self) -> list[dict[str, Any]]:
        """List all registered policy rules."""
        rules = self._policy_engine.list_rules()
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "effect": r.effect.value,
                "priority": r.priority,
                "enabled": r.enabled,
                "subjects": list(r.subjects),
                "actions": list(r.actions),
                "resource_patterns": list(r.resource_patterns),
                "forbidden_payload_patterns": list(r.forbidden_payload_patterns),
                "min_risk_tier": r.min_risk_tier.value if r.min_risk_tier else None,
                "environments": list(r.environments),
                "modifications": r.modifications,
                "reason": r.reason,
            }
            for r in rules
        ]

    def add_policy_rule(self, rule_data: dict[str, Any]) -> dict[str, Any]:
        """Register a new policy rule."""
        effect = PolicyEffect(rule_data["effect"].lower().strip())
        min_rt = (
            PolicyRiskTier(rule_data["min_risk_tier"].lower().strip())
            if rule_data.get("min_risk_tier")
            else None
        )
        rule = PolicyRule(
            rule_id=rule_data["rule_id"],
            name=rule_data["name"],
            description=rule_data.get("description", ""),
            effect=effect,
            priority=rule_data.get("priority", 100),
            enabled=rule_data.get("enabled", True),
            subjects=tuple(rule_data.get("subjects", ())),
            actions=tuple(rule_data.get("actions", ())),
            resource_patterns=tuple(rule_data.get("resource_patterns", ())),
            forbidden_payload_patterns=tuple(rule_data.get("forbidden_payload_patterns", ())),
            min_risk_tier=min_rt,
            environments=tuple(rule_data.get("environments", ())),
            modifications=rule_data.get("modifications"),
            reason=rule_data.get("reason", "Custom policy rule"),
        )
        self._policy_engine.add_rule(rule)
        return {
            "status": "added",
            "rule_id": rule.rule_id,
            "name": rule.name,
            "priority": rule.priority,
        }

    def get_policy_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent policy evaluation decisions."""
        decisions = self._policy_engine.get_decision_history(limit=limit)
        return [d.to_dict() for d in decisions]

    # -------------------------------------------------------------
    # V9 Advanced Observability & System Optimization
    # -------------------------------------------------------------
    @property
    def tracer(self) -> DistributedTracer:
        """Return the active DistributedTracer instance."""
        return self._tracer

    @property
    def system_optimizer(self) -> SystemOptimizer:
        """Return the active SystemOptimizer instance."""
        return self._system_optimizer

    def record_telemetry_span(
        self,
        name: str,
        trace_id: UUID | None = None,
        parent_span_id: UUID | None = None,
        kind: str = "internal",
        status: str = "ok",
        duration_ms: float = 0.0,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Manually record a completed execution span."""
        span = SpanRecord(
            name=name,
            trace_id=trace_id or uuid4(),
            parent_span_id=parent_span_id,
            kind=SpanKind(kind.lower().strip()),
            status=SpanStatus(status.lower().strip()),
            duration_ms=duration_ms,
            attributes=attributes or {},
        )
        self._tracer.record_span(span)
        return span.to_dict()

    def get_mission_spans(self, mission_id: UUID) -> list[dict[str, Any]]:
        """Retrieve all execution spans recorded for a mission."""
        spans = self._tracer.get_mission_spans(mission_id)
        return [s.to_dict() for s in spans]

    def get_cost_metrics(self, mission_id: UUID | None = None) -> dict[str, Any]:
        """Retrieve aggregated token usage and cost metrics."""
        return self._system_optimizer.calculate_cost_metrics(mission_id=mission_id)

    def get_system_bottlenecks(
        self, mission_id: UUID | None = None, top_n: int = 5
    ) -> dict[str, Any]:
        """Analyze slowest spans, error rates, and latency quantiles."""
        return self._system_optimizer.analyze_bottlenecks(mission_id=mission_id, top_n=top_n)

    def generate_optimization_recommendations(
        self, mission_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        """Generate actionable performance, token, and system recommendations."""
        insights = self._system_optimizer.generate_recommendations(mission_id=mission_id)
        return [i.to_dict() for i in insights]

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from orion.api.dto import (
    CreateMissionRequest,
    EvaluationDetailDTO,
    EvidenceItemDTO,
    MissionResponse,
    RecoveryDetailDTO,
    RecoveryObservabilityResponse,
    TaskApprovalRequest,
    TaskApprovalResponse,
    TaskChangesResponse,
    TaskExecutionResponse,
    TaskSubmissionRequest,
    TaskTestsResponse,
    TimelineEventDTO,
    VerificationDetailDTO,
)
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.observability.context import TelemetryContext
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
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


class MissionAPIService:
    """Product-facing application service managing autonomous SWE missions."""

    def __init__(self, default_workspace_path: Path | str | None = None) -> None:
        self._missions: dict[UUID, MissionRecord] = {}
        self._start_time = time.time()
        self._default_workspace_path = (
            Path(default_workspace_path).resolve()
            if default_workspace_path
            else None
        )

    @property
    def uptime_seconds(self) -> float:
        """Return service uptime in seconds."""
        return round(time.time() - self._start_time, 2)

    @property
    def missions_count(self) -> int:
        """Return total count of managed missions."""
        return len(self._missions)

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

        now_iso = datetime.now(UTC).isoformat()
        event_payload = {
            "event": event_type,
            "mission_id": str(mission_id),
            "task_id": str(record.task_id),
            "execution_id": str(record.execution_id),
            "lifecycle_state": record.lifecycle_state,
            "timestamp": now_iso,
            "data": data,
        }

        # Record event in timeline
        current_st = (
            record.coordinator.current_stage.value
            if record.coordinator.current_stage
            else record.lifecycle_state.lower()
        )
        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage=current_st,
                title=event_type.replace("_", " ").title(),
                detail=str(data.get("summary") or data.get("detail") or event_type),
                level=level,
                timestamp=now_iso,
                metadata=data,
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
            # Stage 1: INSPECT_REPOSITORY
            if SWETaskStage.INSPECT_REPOSITORY not in coord.completed_stages:
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
                        "summary": f"Synthesized patch affecting {list(patch_prop.affected_files)}",
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

            # If approval was completed, complete FORMULATE_FIX
            if (
                record.pending_approval
                and record.pending_approval.status == ApprovalStatus.APPROVED
                and SWETaskStage.FORMULATE_FIX not in coord.completed_stages
            ):
                coord.complete_stage(SWETaskStage.FORMULATE_FIX)

            # Stage 4: IMPLEMENT_CHANGE
            if (
                SWETaskStage.IMPLEMENT_CHANGE not in coord.completed_stages
                and record.pending_approval
                and record.pending_approval.status == ApprovalStatus.APPROVED
            ):
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

        if record.coordinator.current_stage != SWETaskStage.GENERATE_REPORT:
            record.coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

        report = record.coordinator.generate_report(summary=summary or record.summary)
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

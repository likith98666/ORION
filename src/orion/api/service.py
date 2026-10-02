from __future__ import annotations

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
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
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


@dataclass
class MissionRecord:
    """Internal record tracking an active or completed mission."""

    mission_id: UUID
    task_id: UUID
    objective: str
    workspace_path: str
    workspace: Workspace
    coordinator: SWEWorkflowCoordinator
    approval_service: ApprovalService
    agent: Agent
    created_at: datetime
    status: str = "initialized"
    summary: str = ""
    report: SWEReport | None = None
    timeline: list[TimelineEventDTO] = field(default_factory=list)


class MissionAPIService:
    """Product-facing application service managing autonomous SWE missions."""

    def __init__(self) -> None:
        self._missions: dict[UUID, MissionRecord] = {}
        self._start_time = time.time()

    @property
    def uptime_seconds(self) -> float:
        """Return service uptime in seconds."""
        return round(time.time() - self._start_time, 2)

    @property
    def missions_count(self) -> int:
        """Return total count of managed missions."""
        return len(self._missions)

    def create_mission(self, request: CreateMissionRequest) -> MissionResponse:
        """Create a new SWE mission with isolated workspace, tools, and coordinator."""
        repo_path = Path(request.workspace_path).resolve()
        if not repo_path.exists():
            raise ValueError(f"Workspace directory does not exist: '{request.workspace_path}'")

        mission_id = uuid4()
        task_id = uuid4()

        workspace = Workspace(repository_root=repo_path)
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
            description="Autonomous SWE workforce agent with repository inspection and repair capabilities",
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
            objective=request.objective.strip(),
            workspace_path=str(repo_path),
            workspace=workspace,
            coordinator=coordinator,
            approval_service=approval_service,
            agent=agent,
            created_at=datetime.now(UTC),
            status="initialized",
            summary=f"Mission initialized for workspace '{repo_path.name}'.",
        )

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage="initialized",
                title="Mission Initialized",
                detail=f"Created mission for objective: '{request.objective}'",
                level="info",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )

        self._missions[mission_id] = record
        return self._build_mission_response(record)

    def get_mission(self, mission_id: UUID) -> MissionResponse | None:
        """Retrieve mission details by ID."""
        record = self._missions.get(mission_id)
        if not record:
            return None
        return self._build_mission_response(record)

    def list_missions(self) -> list[MissionResponse]:
        """List all missions."""
        return [self._build_mission_response(r) for r in self._missions.values()]

    def get_mission_timeline(self, mission_id: UUID) -> list[TimelineEventDTO] | None:
        """Retrieve chronological timeline events for a mission."""
        record = self._missions.get(mission_id)
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
        record = self._missions.get(mission_id)
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

    def get_mission_verification(self, mission_id: UUID) -> VerificationDetailDTO | None:
        """Retrieve formal verification details for a mission."""
        record = self._missions.get(mission_id)
        if not record:
            return None

        verif_items = record.coordinator.ledger.get_items(category=EvidenceCategory.VERIFICATION_RESULT)
        verified_count = sum(1 for item in verif_items if item.level == EvidenceLevel.VERIFIED)
        passed = verified_count > 0

        latest_item = verif_items[-1] if verif_items else None
        reason = latest_item.content if latest_item else "No verification recorded."
        status_val = "passed" if passed else ("failed" if verif_items else "pending")
        reqs = tuple(latest_item.metadata.get("requirements", ())) if latest_item else ()

        return VerificationDetailDTO(
            status=status_val,
            reason=reason,
            verified_evidence_count=verified_count,
            requirements=reqs,
            passed=passed,
        )

    def get_mission_recovery(self, mission_id: UUID) -> RecoveryDetailDTO | None:
        """Retrieve recovery history and transparency for a mission."""
        record = self._missions.get(mission_id)
        if not record:
            return None

        recovery_items = record.coordinator.ledger.get_items(category=EvidenceCategory.RECOVERY_EVENT)
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

    def get_mission_evaluation(self, mission_id: UUID) -> EvaluationDetailDTO | None:
        """Retrieve deterministic evaluation metrics and criteria for a mission."""
        record = self._missions.get(mission_id)
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
        record = self._missions.get(mission_id)
        if not record:
            return None

        if record.report:
            return record.report.to_dict()

        # If report not yet generated, attempt generation if at report stage
        if record.coordinator.current_stage == SWETaskStage.GENERATE_REPORT:
            report = record.coordinator.generate_report(summary=record.summary)
            record.report = report
            record.status = report.status
            return report.to_dict()

        return None

    def advance_stage(self, mission_id: UUID, target_stage: str) -> MissionResponse:
        """Advance the mission to the specified stage."""
        record = self._missions.get(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        stage_enum = SWETaskStage(target_stage)
        record.coordinator.advance_stage(stage_enum)
        record.status = f"running_{stage_enum.value}"

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage=stage_enum.value,
                title=f"Advanced to {stage_enum.name}",
                detail=f"Workflow transitioned to stage '{stage_enum.value}'",
                level="info",
                timestamp=datetime.now(UTC).isoformat(),
            )
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
        record = self._missions.get(mission_id)
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

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage=stage_enum.value,
                title=f"Executed Tool: {tool_name}",
                detail=f"Success: {result.success}" if result.success else f"Error: {result.error}",
                level="success" if result.success else "error",
                timestamp=datetime.now(UTC).isoformat(),
                metadata={"tool_name": tool_name},
            )
        )

        return {
            "success": result.success,
            "tool_name": tool_name,
            "output": result.output,
            "error": result.error,
        }

    def complete_stage(self, mission_id: UUID, stage: str) -> MissionResponse:
        """Mark a stage as completed."""
        record = self._missions.get(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        stage_enum = SWETaskStage(stage)
        record.coordinator.complete_stage(stage_enum)

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage=stage_enum.value,
                title=f"Completed {stage_enum.name}",
                detail=f"Stage '{stage_enum.value}' marked complete",
                level="info",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
        return self._build_mission_response(record)

    def generate_final_report(self, mission_id: UUID, summary: str = "") -> dict[str, Any]:
        """Generate final mission report and update mission status."""
        record = self._missions.get(mission_id)
        if not record:
            raise KeyError(f"Mission '{mission_id}' not found.")

        if record.coordinator.current_stage != SWETaskStage.GENERATE_REPORT:
            record.coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

        report = record.coordinator.generate_report(summary=summary or record.summary)
        record.report = report
        record.status = report.status

        record.timeline.append(
            TimelineEventDTO(
                event_id=str(uuid4()),
                stage="generate_report",
                title="Mission Report Generated",
                detail=f"Final outcome: {report.status}",
                level="success" if report.status == "verified_success" else "warning",
                timestamp=datetime.now(UTC).isoformat(),
            )
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
            if item.category == EvidenceCategory.FILE_CHANGE and "path" in item.metadata and item.metadata["path"]
        }))

        evaluation_status = None
        try:
            ev = record.coordinator.evaluate_mission()
            evaluation_status = ev.status.value
        except Exception:
            pass

        return MissionResponse(
            mission_id=str(record.mission_id),
            task_id=str(record.task_id),
            objective=record.objective,
            workspace_root=record.workspace_path,
            status=record.status,
            current_stage=record.coordinator.current_stage.value if record.coordinator.current_stage else None,
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

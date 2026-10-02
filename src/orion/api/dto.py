from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CreateMissionRequest:
    """Request payload for creating a new SWE mission."""

    objective: str
    workspace_path: str
    target_files: tuple[str, ...] = ()
    expected_requirements: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective or not self.objective.strip():
            raise ValueError("objective cannot be empty.")
        if not self.workspace_path or not self.workspace_path.strip():
            raise ValueError("workspace_path cannot be empty.")


@dataclass(frozen=True)
class TaskSubmissionRequest:
    """Product-facing typed task submission request."""

    task: str
    workspace: str
    execution_mode: str = "controlled"
    target_files: tuple[str, ...] = ()
    expected_requirements: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task or len(self.task.strip()) < 3:
            raise ValueError("task must contain at least 3 non-whitespace characters.")
        if not self.workspace or not self.workspace.strip():
            raise ValueError("workspace path cannot be empty.")
        if self.execution_mode not in ("controlled", "autonomous"):
            raise ValueError(
                f"Unsupported execution_mode: '{self.execution_mode}'. "
                "Must be 'controlled' or 'autonomous'."
            )

    def to_create_mission_request(self) -> CreateMissionRequest:
        return CreateMissionRequest(
            objective=self.task.strip(),
            workspace_path=self.workspace.strip(),
            target_files=self.target_files,
            expected_requirements=self.expected_requirements,
            parameters=self.parameters,
        )


@dataclass(frozen=True)
class TaskApprovalRequest:
    """Interactive approval decision submission."""

    decision: str = "approve"  # "approve" or "deny"
    approver: str = "Operator"
    reason: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.decision.lower() not in ("approve", "deny"):
            raise ValueError(f"Invalid decision: '{self.decision}'. Must be 'approve' or 'deny'.")
        if not self.approver or not self.approver.strip():
            raise ValueError("approver name cannot be empty.")


@dataclass(frozen=True)
class TaskApprovalResponse:
    """Interactive approval response acknowledgment."""

    task_id: str
    request_id: str
    decision: str
    approver: str
    decided_at: str
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "decision": self.decision,
            "approver": self.approver,
            "decided_at": self.decided_at,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TaskExecutionResponse:
    """Execution lifecycle and active agent telemetry."""

    task_id: str
    execution_id: str
    lifecycle_state: str
    current_stage: str | None
    completed_stages: tuple[str, ...]
    stages_total: int
    stages_completed_count: int
    active_agent: str | None
    active_tool: str | None
    approval_required: bool
    pending_approval: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "lifecycle_state": self.lifecycle_state,
            "current_stage": self.current_stage,
            "completed_stages": list(self.completed_stages),
            "stages_total": self.stages_total,
            "stages_completed_count": self.stages_completed_count,
            "active_agent": self.active_agent,
            "active_tool": self.active_tool,
            "approval_required": self.approval_required,
            "pending_approval": self.pending_approval,
        }


@dataclass(frozen=True)
class TaskChangesResponse:
    """Structured code changes and unified diff response."""

    task_id: str
    affected_files: tuple[str, ...]
    operations: tuple[dict[str, Any], ...]
    unified_diff: str
    total_lines_added: int
    total_lines_removed: int
    validation_status: str
    approval_status: str
    application_status: str
    rollback_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "affected_files": list(self.affected_files),
            "operations": list(self.operations),
            "unified_diff": self.unified_diff,
            "total_lines_added": self.total_lines_added,
            "total_lines_removed": self.total_lines_removed,
            "validation_status": self.validation_status,
            "approval_status": self.approval_status,
            "application_status": self.application_status,
            "rollback_status": self.rollback_status,
        }


@dataclass(frozen=True)
class TaskTestsResponse:
    """Controlled test execution results response."""

    task_id: str
    target: str
    exit_code: int | None
    passed: bool
    duration: float
    stdout: str
    stderr: str
    output_summary: str
    executed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "target": self.target,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "duration": self.duration,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output_summary": self.output_summary,
            "executed": self.executed,
        }


@dataclass(frozen=True)
class RecoveryObservabilityResponse:
    """Phase 6 Bounded Self-Healing Recovery telemetry response."""

    task_id: str
    failure_category: str | None
    recovery_strategy: str | None
    attempt_number: int
    recovery_state: str
    remaining_attempts: int
    remaining_budget: dict[str, Any]
    recovery_depth: int
    termination_reason: str | None
    rollback_performed: bool
    history: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "failure_category": self.failure_category,
            "recovery_strategy": self.recovery_strategy,
            "attempt_number": self.attempt_number,
            "recovery_state": self.recovery_state,
            "remaining_attempts": self.remaining_attempts,
            "remaining_budget": self.remaining_budget,
            "recovery_depth": self.recovery_depth,
            "termination_reason": self.termination_reason,
            "rollback_performed": self.rollback_performed,
            "history": list(self.history),
        }


@dataclass(frozen=True)
class EvidenceItemDTO:
    """DTO representing an evidence item with full provenance."""

    id: str
    level: str
    category: str
    stage: str
    source: str
    summary: str
    content: str
    task_id: str | None
    execution_id: str | None
    tool_name: str | None
    request_id: str | None
    trace_id: str | None
    workspace_root: str | None
    metadata: dict[str, Any]
    timestamp: str

    @classmethod
    def from_domain(cls, item: Any) -> EvidenceItemDTO:
        """Convert a domain EvidenceItem to DTO."""
        return cls(
            id=str(item.id),
            level=item.level.value if hasattr(item.level, "value") else str(item.level),
            category=item.category.value if hasattr(item.category, "value") else str(item.category),
            stage=item.stage.value if hasattr(item.stage, "value") else str(item.stage),
            source=str(item.source),
            summary=str(item.summary),
            content=str(item.content),
            task_id=str(item.task_id) if item.task_id else None,
            execution_id=str(item.execution_id) if item.execution_id else None,
            tool_name=str(item.tool_name) if item.tool_name else None,
            request_id=str(item.request_id) if item.request_id else None,
            trace_id=str(item.trace_id) if item.trace_id else None,
            workspace_root=str(item.workspace_root) if item.workspace_root else None,
            metadata=dict(item.metadata),
            timestamp=(
                item.timestamp.isoformat()
                if hasattr(item.timestamp, "isoformat")
                else str(item.timestamp)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "stage": self.stage,
            "source": self.source,
            "summary": self.summary,
            "content": self.content,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "workspace_root": self.workspace_root,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class TimelineEventDTO:
    """DTO representing a chronological event in the mission lifecycle."""

    event_id: str
    stage: str
    title: str
    detail: str
    level: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "event_id": self.event_id,
            "stage": self.stage,
            "title": self.title,
            "detail": self.detail,
            "level": self.level,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class MissionResponse:
    """DTO representing an SWE mission."""

    mission_id: str
    task_id: str
    objective: str
    workspace_root: str
    status: str
    current_stage: str | None
    completed_stages: tuple[str, ...]
    stages_total: int
    stages_completed_count: int
    created_at: str
    summary: str = ""
    evaluation_status: str | None = None
    files_modified: tuple[str, ...] = ()
    evidence_counts: dict[str, int] = field(default_factory=dict)
    execution_id: str = ""
    lifecycle_state: str = "RECEIVED"
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "objective": self.objective,
            "workspace_root": self.workspace_root,
            "status": self.status,
            "lifecycle_state": self.lifecycle_state,
            "approval_required": self.approval_required,
            "current_stage": self.current_stage,
            "completed_stages": list(self.completed_stages),
            "stages_total": self.stages_total,
            "stages_completed_count": self.stages_completed_count,
            "created_at": self.created_at,
            "summary": self.summary,
            "evaluation_status": self.evaluation_status,
            "files_modified": list(self.files_modified),
            "evidence_counts": self.evidence_counts,
        }


@dataclass(frozen=True)
class VerificationDetailDTO:
    """DTO representing verification outcome."""

    status: str
    reason: str
    verified_evidence_count: int
    requirements: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "status": self.status,
            "reason": self.reason,
            "verified_evidence_count": self.verified_evidence_count,
            "requirements": list(self.requirements),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class RecoveryDetailDTO:
    """DTO representing recovery history and transparency."""

    recovery_attempts: int
    recovery_events: tuple[dict[str, Any], ...]
    transparent: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "recovery_attempts": self.recovery_attempts,
            "recovery_events": list(self.recovery_events),
            "transparent": self.transparent,
        }


@dataclass(frozen=True)
class EvaluationDetailDTO:
    """DTO representing deterministic evaluation."""

    status: str
    summary: str
    metrics: dict[str, int]
    criteria: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
            "criteria": self.criteria,
        }


@dataclass(frozen=True)
class HealthResponse:
    """DTO representing system health check."""

    status: str
    version: str
    uptime_seconds: float
    missions_count: int
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "status": self.status,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "missions_count": self.missions_count,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class AgentTelemetryDTO:
    """Telemetry data representing an autonomous workforce agent."""

    agent_id: str
    name: str
    role: str
    capabilities: tuple[str, ...]
    permissions: tuple[str, ...]
    status: str  # IDLE, ACTIVE, WAITING_APPROVAL, COMPLETED, FAILED
    current_task: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failure_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
            "status": self.status,
            "current_task": self.current_task,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_message": self.failure_message,
        }


@dataclass(frozen=True)
class AgentRosterResponse:
    """Workforce observatory roster exposing all participating agents."""

    mission_id: str
    task_id: str
    agents: tuple[AgentTelemetryDTO, ...]
    total_agents: int
    active_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "agents": [a.to_dict() for a in self.agents],
            "total_agents": self.total_agents,
            "active_count": self.active_count,
        }


@dataclass(frozen=True)
class ExecutionGraphNodeDTO:
    """Node in the execution DAG representing a stage or unit of work."""

    id: str
    stage: str
    title: str
    description: str
    state: str  # PENDING, READY, RUNNING, BLOCKED, COMPLETED, FAILED, RECOVERING, VERIFIED
    required_capability: str | None = None
    duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "required_capability": self.required_capability,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


@dataclass(frozen=True)
class ExecutionGraphEdgeDTO:
    """Edge in the execution DAG representing execution dependency."""

    source: str
    target: str
    relationship: str = "depends_on"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relationship": self.relationship,
        }


@dataclass(frozen=True)
class ExecutionGraphResponse:
    """Execution DAG visualization response."""

    mission_id: str
    task_id: str
    nodes: tuple[ExecutionGraphNodeDTO, ...]
    edges: tuple[ExecutionGraphEdgeDTO, ...]
    current_node_id: str | None
    completed_nodes_count: int
    total_nodes_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "current_node_id": self.current_node_id,
            "completed_nodes_count": self.completed_nodes_count,
            "total_nodes_count": self.total_nodes_count,
        }


@dataclass(frozen=True)
class TaskCancellationRequest:
    """Request payload to cancel an in-flight mission."""

    reason: str = "Operator requested cancellation"
    cancelled_by: str = "Operator"


@dataclass(frozen=True)
class TaskCancellationResponse:
    """Response payload acknowledging mission cancellation."""

    mission_id: str
    task_id: str
    status: str
    cancelled_at: str
    reason: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "status": self.status,
            "cancelled_at": self.cancelled_at,
            "reason": self.reason,
            "message": self.message,
        }


@dataclass(frozen=True)
class ReadinessResponse:
    """Readiness probe response verifying environment, workspace, and subsystems."""

    status: str
    version: str
    environment: str
    workspace_path: str
    workspace_writable: bool
    active_missions: int
    checks: dict[str, bool]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "version": self.version,
            "environment": self.environment,
            "workspace_path": self.workspace_path,
            "workspace_writable": self.workspace_writable,
            "active_missions": self.active_missions,
            "checks": self.checks,
            "timestamp": self.timestamp,
        }

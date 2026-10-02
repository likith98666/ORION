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
            timestamp=item.timestamp.isoformat() if hasattr(item.timestamp, "isoformat") else str(item.timestamp),
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

    def to_dict(self) -> dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "objective": self.objective,
            "workspace_root": self.workspace_root,
            "status": self.status,
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

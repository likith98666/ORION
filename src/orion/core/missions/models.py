"""Data models and enums for V2 Advanced Mission Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class TaskState(str, Enum):
    """Lifecycle states for decomposed tasks in a mission task graph."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VERIFIED = "verified"


class TaskPriority(str, Enum):
    """Task priority levels for mission scheduling."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskRisk(str, Enum):
    """Assessed risk of a task execution."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ResourceBudget:
    """Resource constraints bounding task and mission execution."""

    max_duration_seconds: float = 300.0
    max_attempts: int = 3
    max_file_changes: int = 10
    allow_network: bool = False

    def __post_init__(self) -> None:
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive.")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive.")
        if self.max_file_changes < 0:
            raise ValueError("max_file_changes cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        """Convert budget to dictionary."""
        return {
            "max_duration_seconds": self.max_duration_seconds,
            "max_attempts": self.max_attempts,
            "max_file_changes": self.max_file_changes,
            "allow_network": self.allow_network,
        }


@dataclass
class TaskNode:
    """A single node representing an actionable sub-objective in a mission graph."""

    task_id: UUID
    title: str
    description: str
    parent_id: UUID | None = None
    dependencies: set[UUID] = field(default_factory=set)
    priority: TaskPriority = TaskPriority.MEDIUM
    state: TaskState = TaskState.PENDING
    risk: TaskRisk = TaskRisk.LOW
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    owner: str = "orion:default"
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Task title cannot be empty.")
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID instance.")
        if not isinstance(self.priority, TaskPriority):
            raise TypeError("priority must be a TaskPriority instance.")
        if not isinstance(self.state, TaskState):
            raise TypeError("state must be a TaskState instance.")
        if not isinstance(self.risk, TaskRisk):
            raise TypeError("risk must be a TaskRisk instance.")
        if not isinstance(self.budget, ResourceBudget):
            raise TypeError("budget must be a ResourceBudget instance.")

    def mark_state(self, new_state: TaskState, error_message: str | None = None) -> None:
        """Update task lifecycle state."""
        self.state = new_state
        if error_message is not None:
            self.error_message = error_message
        if new_state in (
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.VERIFIED,
        ):
            self.completed_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Serialize task node to dictionary."""
        return {
            "task_id": str(self.task_id),
            "title": self.title,
            "description": self.description,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "dependencies": [str(d) for d in sorted(self.dependencies, key=str)],
            "priority": self.priority.value,
            "state": self.state.value,
            "risk": self.risk.value,
            "budget": self.budget.to_dict(),
            "owner": self.owner,
            "evidence_ids": list(self.evidence_ids),
            "metadata": dict(self.metadata),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class MissionPlan:
    """Full mission decomposition containing the structured task graph and objectives."""

    mission_id: UUID
    objective: str
    tasks: dict[UUID, TaskNode] = field(default_factory=dict)
    root_task_ids: list[UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: TaskState = TaskState.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("Mission objective cannot be empty.")
        if not isinstance(self.mission_id, UUID):
            raise TypeError("mission_id must be a UUID instance.")

    @classmethod
    def create(cls, objective: str, mission_id: UUID | None = None) -> MissionPlan:
        """Create a new mission plan."""
        return cls(mission_id=mission_id or uuid4(), objective=objective)

    def to_dict(self) -> dict[str, Any]:
        """Serialize mission plan to dictionary."""
        return {
            "mission_id": str(self.mission_id),
            "objective": self.objective,
            "tasks": {str(k): v.to_dict() for k, v in self.tasks.items()},
            "root_task_ids": [str(rid) for rid in self.root_task_ids],
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }

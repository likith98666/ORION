"""Domain models and DTOs for Human-in-the-Loop (HITL) and Collaborative Oversight."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class InterventionType(str, Enum):
    """Categorization of operator interventions into autonomous execution."""

    PAUSE = "pause"
    RESUME = "resume"
    STEER = "steer"
    OVERRIDE_DECISION = "override_decision"
    REVERT_STAGE = "revert_stage"
    FORCE_FAIL = "force_fail"


class ClarificationStatus(str, Enum):
    """Lifecycle state of an interactive clarification request."""

    PENDING = "pending"
    ANSWERED = "answered"
    TIMED_OUT = "timed_out"
    DEFAULT_ACCEPTED = "default_accepted"


class RiskTier(str, Enum):
    """Classification of action risk determining human oversight requirements."""

    LOW = "low"            # Autonomous execution
    MEDIUM = "medium"      # Asynchronous advisory notification
    HIGH = "high"          # Mandatory synchronous approval before execution
    CRITICAL = "critical"  # Dual-authorization or security review required


@dataclass(frozen=True)
class ClarificationRequest:
    """Structured question dispatched by agent when requirements are ambiguous."""

    request_id: UUID
    mission_id: UUID
    task_id: UUID
    question: str
    context: str
    options: tuple[str, ...] = ()
    default_choice: str | None = None
    timeout_seconds: float = 300.0
    status: ClarificationStatus = ClarificationStatus.PENDING
    response: str | None = None
    answered_by: str | None = None
    answered_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.question or not self.question.strip():
            raise ValueError("question cannot be empty.")
        if not self.context or not self.context.strip():
            raise ValueError("context cannot be empty.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")

    def to_dict(self) -> dict[str, Any]:
        """Convert clarification request to structured dictionary."""
        return {
            "request_id": str(self.request_id),
            "mission_id": str(self.mission_id),
            "task_id": str(self.task_id),
            "question": self.question,
            "context": self.context,
            "options": list(self.options),
            "default_choice": self.default_choice,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "response": self.response,
            "answered_by": self.answered_by,
            "answered_at": self.answered_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class HumanIntervention:
    """Record of an explicit human operator action overriding or steering workflow."""

    intervention_id: UUID
    mission_id: UUID
    intervention_type: InterventionType
    operator: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    applied: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.operator or not self.operator.strip():
            raise ValueError("operator cannot be empty.")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        """Convert human intervention record to dictionary."""
        return {
            "intervention_id": str(self.intervention_id),
            "mission_id": str(self.mission_id),
            "intervention_type": self.intervention_type.value,
            "operator": self.operator,
            "reason": self.reason,
            "payload": dict(self.payload),
            "applied": self.applied,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class OperatorFeedback:
    """Post-mission or in-flight feedback submitted by human reviewers."""

    feedback_id: UUID
    mission_id: UUID
    operator: str
    rating: int  # 1 to 5 scale
    comments: str
    corrections: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.operator or not self.operator.strip():
            raise ValueError("operator cannot be empty.")
        if self.rating < 1 or self.rating > 5:
            raise ValueError("rating must be between 1 and 5.")

    def to_dict(self) -> dict[str, Any]:
        """Convert operator feedback to dictionary."""
        return {
            "feedback_id": str(self.feedback_id),
            "mission_id": str(self.mission_id),
            "operator": self.operator,
            "rating": self.rating,
            "comments": self.comments,
            "corrections": list(self.corrections),
            "created_at": self.created_at,
        }

from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4


class PlanStatus(str, Enum):
    """Lifecycle status of an ORION execution plan."""

    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Plan:
    """Represents a structured execution plan for an ORION task."""

    id: UUID
    task_id: UUID
    objective: str
    status: PlanStatus = PlanStatus.DRAFT

    @classmethod
    def create(
        cls,
        task_id: UUID,
        objective: str,
    ) -> "Plan":
        """Create a validated execution plan."""

        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Plan objective cannot be empty.")

        if len(cleaned_objective) > 10_000:
            raise ValueError(
                "Plan objective cannot exceed 10,000 characters."
            )

        return cls(
            id=uuid4(),
            task_id=task_id,
            objective=cleaned_objective,
        )
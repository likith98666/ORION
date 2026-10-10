from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability


class PlanStepStatus(str, Enum):
    """Lifecycle status of a plan step."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Represents one executable step inside an ORION plan."""

    id: UUID
    plan_id: UUID
    order: int
    description: str
    required_capability: AgentCapability
    dependencies: frozenset[UUID] = field(default_factory=frozenset)
    priority: int = 3
    status: PlanStepStatus = PlanStepStatus.PENDING

    @classmethod
    def create(
        cls,
        plan_id: UUID,
        order: int,
        description: str,
        required_capability: AgentCapability,
        dependencies: frozenset[UUID] | None = None,
        priority: int = 3,
    ) -> "PlanStep":
        """Create a validated plan step."""

        if order < 1:
            raise ValueError("Plan step order must be at least 1.")

        if priority < 1 or priority > 5:
            raise ValueError("Plan step priority must be between 1 and 5.")

        cleaned_description = description.strip()

        if not cleaned_description:
            raise ValueError("Plan step description cannot be empty.")

        if len(cleaned_description) > 5_000:
            raise ValueError("Plan step description cannot exceed 5,000 characters.")

        if dependencies is None:
            dependencies = frozenset()

        return cls(
            id=uuid4(),
            plan_id=plan_id,
            order=order,
            description=cleaned_description,
            required_capability=required_capability,
            dependencies=frozenset(dependencies),
            priority=priority,
        )

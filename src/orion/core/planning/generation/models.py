from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.capabilities import AgentCapability


@dataclass(frozen=True)
class GeneratedPlanStep:
    """A single step produced by a plan-generation component."""

    order: int
    description: str
    required_capability: AgentCapability
    dependencies: frozenset[int] = frozenset()
    priority: int = 3


@dataclass(frozen=True)
class GeneratedPlan:
    """Structured plan produced from a high-level objective."""

    task_id: UUID
    objective: str
    steps: tuple[GeneratedPlanStep, ...]

    @classmethod
    def create(
        cls,
        task_id: UUID,
        objective: str,
        steps: tuple[GeneratedPlanStep, ...],
    ) -> "GeneratedPlan":
        """Create a validated generated plan."""

        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Generated plan objective cannot be empty.")

        if len(cleaned_objective) > 10_000:
            raise ValueError(
                "Generated plan objective cannot exceed 10,000 characters."
            )

        if not steps:
            raise ValueError("Generated plan must contain at least one step.")

        return cls(
            task_id=task_id,
            objective=cleaned_objective,
            steps=steps,
        )

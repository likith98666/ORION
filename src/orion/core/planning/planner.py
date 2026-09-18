from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.models import Plan
from orion.core.planning.steps import PlanStep


@dataclass(frozen=True)
class PlannedStep:
    """Structured description of a step produced by a planner."""

    order: int
    description: str
    required_capability: AgentCapability
    dependencies: frozenset[int] = frozenset()
    priority: int = 3


class Planner:
    """Creates structured execution plans from high-level objectives."""

    def create_plan(
        self,
        task_id: UUID,
        objective: str,
        steps: list[PlannedStep],
    ) -> tuple[Plan, list[PlanStep]]:
        """Create a plan and convert planned steps into executable plan steps."""

        plan = Plan.create(
            task_id=task_id,
            objective=objective,
        )

        plan_steps = self._build_steps(
            plan_id=plan.id,
            planned_steps=steps,
        )

        return plan, plan_steps

    def _build_steps(
        self,
        plan_id: UUID,
        planned_steps: list[PlannedStep],
    ) -> list[PlanStep]:
        """Convert planner output into validated PlanStep objects."""

        step_ids_by_order: dict[int, UUID] = {}
        plan_steps: list[PlanStep] = []

        for planned_step in planned_steps:
            if planned_step.order in step_ids_by_order:
                raise ValueError(
                    f"Duplicate plan step order: {planned_step.order}."
                )

            step = PlanStep.create(
                plan_id=plan_id,
                order=planned_step.order,
                description=planned_step.description,
                required_capability=planned_step.required_capability,
                priority=planned_step.priority,
            )

            step_ids_by_order[planned_step.order] = step.id
            plan_steps.append(step)

        for plan_step, planned_step in zip(
            plan_steps,
            planned_steps,
            strict=True,
        ):
            unknown_dependencies = (
                planned_step.dependencies - step_ids_by_order.keys()
            )

            if unknown_dependencies:
                raise ValueError(
                    "Plan step contains unknown dependency orders: "
                    f"{sorted(unknown_dependencies)}."
                )

            if planned_step.order in planned_step.dependencies:
                raise ValueError(
                    f"Plan step {planned_step.order} cannot depend on itself."
                )

            plan_step.dependencies = frozenset(
                step_ids_by_order[dependency_order]
                for dependency_order in planned_step.dependencies
            )

        return plan_steps

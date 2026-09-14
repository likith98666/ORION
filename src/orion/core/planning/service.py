from uuid import UUID

from orion.core.planning.memory_repository import InMemoryPlanRepository
from orion.core.planning.models import Plan
from orion.core.planning.repository import PlanRepository
from orion.core.planning.steps import PlanStep
from orion.core.planning.validator import PlanValidationResult, PlanValidator


class PlanService:
    """Application service for managing ORION execution plans."""

    def __init__(
        self,
        repository: PlanRepository | None = None,
        validator: PlanValidator | None = None,
    ) -> None:
        self._repository = repository or InMemoryPlanRepository()
        self._validator = validator or PlanValidator()

    def create_plan(
        self,
        task_id: UUID,
        objective: str,
    ) -> Plan:
        """Create and persist a new execution plan."""

        plan = Plan.create(
            task_id=task_id,
            objective=objective,
        )

        self._repository.save(plan)

        return plan

    def get_plan(
        self,
        plan_id: UUID,
    ) -> Plan | None:
        """Retrieve a plan by ID."""

        return self._repository.get(plan_id)

    def delete_plan(
        self,
        plan_id: UUID,
    ) -> None:
        """Delete a plan by ID."""

        self._repository.delete(plan_id)

    def list_plans_for_task(
        self,
        task_id: UUID,
    ) -> list[Plan]:
        """List all plans belonging to a task."""

        return self._repository.list_for_task(task_id)

    def validate_steps(
        self,
        steps: list[PlanStep],
    ) -> PlanValidationResult:
        """Validate the structural integrity of plan steps."""

        return self._validator.validate(steps)
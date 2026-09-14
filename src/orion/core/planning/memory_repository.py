from uuid import UUID

from orion.core.planning.models import Plan
from orion.core.planning.repository import PlanRepository


class InMemoryPlanRepository(PlanRepository):
    """In-memory implementation of the ORION plan repository."""

    def __init__(self) -> None:
        self._plans: dict[UUID, Plan] = {}

    def save(self, plan: Plan) -> None:
        """Save or replace a plan."""
        self._plans[plan.id] = plan

    def get(self, plan_id: UUID) -> Plan | None:
        """Retrieve a plan by ID."""
        return self._plans.get(plan_id)

    def delete(self, plan_id: UUID) -> None:
        """Delete a plan by ID if it exists."""
        self._plans.pop(plan_id, None)

    def list_for_task(self, task_id: UUID) -> list[Plan]:
        """List all plans belonging to a task."""
        return [
            plan
            for plan in self._plans.values()
            if plan.task_id == task_id
        ]
from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.planning.models import Plan


class PlanRepository(ABC):
    """Abstract repository for storing ORION execution plans."""

    @abstractmethod
    def save(self, plan: Plan) -> None:
        """Save a plan."""
        raise NotImplementedError

    @abstractmethod
    def get(self, plan_id: UUID) -> Plan | None:
        """Retrieve a plan by ID."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, plan_id: UUID) -> None:
        """Delete a plan by ID."""
        raise NotImplementedError

    @abstractmethod
    def list_for_task(self, task_id: UUID) -> list[Plan]:
        """List all plans belonging to a task."""
        raise NotImplementedError

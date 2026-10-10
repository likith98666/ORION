from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.planning.generation.models import GeneratedPlan


class PlanGenerator(ABC):
    """Interface for components that generate plans from task objectives."""

    @abstractmethod
    def generate(
        self,
        task_id: UUID,
        objective: str,
    ) -> GeneratedPlan:
        """Generate a structured plan for a task objective."""
        raise NotImplementedError

from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.agents.tasks import AgentTask


class AgentTaskRepository(ABC):
    """Abstract repository for storing ORION agent tasks."""

    @abstractmethod
    def save(self, task: AgentTask) -> None:
        """Save an agent task."""

    @abstractmethod
    def get(self, task_id: UUID) -> AgentTask | None:
        """Get an agent task by ID."""

    @abstractmethod
    def delete(self, task_id: UUID) -> None:
        """Delete an agent task."""

    @abstractmethod
    def list_for_task(self, task_id: UUID) -> list[AgentTask]:
        """List all agent tasks belonging to a parent task."""
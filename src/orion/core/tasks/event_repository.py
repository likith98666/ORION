from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.tasks.events import TaskEvent


class TaskEventRepository(ABC):
    @abstractmethod
    def save(self, event: TaskEvent) -> None:
        """Save a task event."""

    @abstractmethod
    def get(self, event_id: UUID) -> TaskEvent | None:
        """Get an event by ID."""

    @abstractmethod
    def list_for_task(self, task_id: UUID) -> list[TaskEvent]:
        """List all events belonging to a task."""

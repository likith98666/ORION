from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.tasks.models import Task


class TaskRepository(ABC):
    @abstractmethod
    def save(self, task: Task) -> None:
        """Save a task."""

    @abstractmethod
    def get(self, task_id: UUID) -> Task | None:
        """Get a task by ID."""

    @abstractmethod
    def delete(self, task_id: UUID) -> None:
        """Delete a task."""
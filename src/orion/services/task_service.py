from uuid import UUID

from orion.core.tasks.event_repository import TaskEventRepository
from orion.core.tasks.events import TaskEvent
from orion.core.tasks.manager import TaskManager
from orion.core.tasks.models import Task, TaskStatus
from orion.core.tasks.repository import TaskRepository


class TaskService:
    """Application-level service for task operations."""

    def __init__(
        self,
        repository: TaskRepository,
        event_repository: TaskEventRepository,
    ) -> None:
        self._manager = TaskManager(
            repository,
            event_repository,
        )
        self._event_repository = event_repository

    def create_task(self, objective: str) -> Task:
        """Create a new task."""
        return self._manager.create_task(objective)

    def get_task(self, task_id: UUID) -> Task | None:
        """Retrieve a task by ID."""
        return self._manager.get_task(task_id)

    def update_task_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        error: str | None = None,
    ) -> Task:
        """Update a task's status."""
        return self._manager.update_status(
            task_id,
            status,
            error,
        )

    def get_task_events(self, task_id: UUID) -> list[TaskEvent]:
        """Retrieve the complete event history for a task."""
        return self._event_repository.list_for_task(task_id)

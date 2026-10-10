from uuid import UUID

from orion.core.tasks.models import Task
from orion.core.tasks.repository import TaskRepository


class InMemoryTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    def delete(self, task_id: UUID) -> None:
        self._tasks.pop(task_id, None)

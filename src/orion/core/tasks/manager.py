from datetime import datetime
from uuid import UUID

from orion.core.tasks.event_repository import TaskEventRepository
from orion.core.tasks.events import TaskEvent, TaskEventType
from orion.core.tasks.models import Task, TaskStatus
from orion.core.tasks.repository import TaskRepository

ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.PLANNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PLANNING: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.WAITING,
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.FAILED: {
        TaskStatus.PLANNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskManager:
    def __init__(
        self,
        repository: TaskRepository,
        event_repository: TaskEventRepository,
    ) -> None:
        self._repository = repository
        self._event_repository = event_repository

    def create_task(self, objective: str) -> Task:
        task = Task.create(objective)
        self._repository.save(task)

        event = TaskEvent.create(
            task_id=task.id,
            event_type=TaskEventType.TASK_CREATED,
            message="Task created",
        )
        self._event_repository.save(event)

        return task

    def get_task(self, task_id: UUID) -> Task | None:
        return self._repository.get(task_id)

    def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        error: str | None = None,
    ) -> Task:
        task = self._repository.get(task_id)

        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if status != TaskStatus.FAILED and error is not None:
            raise ValueError(
                "An error message can only be provided when transitioning a task to FAILED."
            )

        allowed_statuses = ALLOWED_TRANSITIONS[task.status]

        if status not in allowed_statuses:
            raise ValueError(f"Invalid task transition: {task.status.value} -> {status.value}")

        previous_status = task.status

        if status == TaskStatus.FAILED:
            cleaned_error = error.strip() if error is not None else None

            if not cleaned_error:
                raise ValueError("An error message is required when a task fails.")

            task.last_error = cleaned_error

        elif status == TaskStatus.PLANNING:
            task.last_error = None

        now = datetime.now()

        if status == TaskStatus.RUNNING:
            task.started_at = task.started_at or now
            task.attempt_count += 1

        if status == TaskStatus.COMPLETED:
            task.completed_at = now

        task.status = status
        self._repository.save(task)

        if status == TaskStatus.FAILED:
            event_type = TaskEventType.TASK_FAILED
            message = f"Task failed: {task.last_error}"
        else:
            event_type = TaskEventType.STATUS_CHANGED
            message = f"Task status changed: {previous_status.value} -> {status.value}"

        event = TaskEvent.create(
            task_id=task.id,
            event_type=event_type,
            message=message,
            metadata={
                "previous_status": previous_status.value,
                "new_status": status.value,
                "attempt_count": task.attempt_count,
            },
        )
        self._event_repository.save(event)

        return task

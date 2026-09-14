from uuid import UUID

from orion.core.tasks.event_repository import TaskEventRepository
from orion.core.tasks.events import TaskEvent


class InMemoryTaskEventRepository(TaskEventRepository):
    def __init__(self) -> None:
        self._events: dict[UUID, TaskEvent] = {}

    def save(self, event: TaskEvent) -> None:
        self._events[event.id] = event

    def get(self, event_id: UUID) -> TaskEvent | None:
        return self._events.get(event_id)

    def list_for_task(self, task_id: UUID) -> list[TaskEvent]:
        events = [
            event
            for event in self._events.values()
            if event.task_id == task_id
        ]

        return sorted(
            events,
            key=lambda event: event.timestamp,
        )
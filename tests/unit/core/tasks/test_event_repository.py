from uuid import uuid4

from orion.core.tasks.events import TaskEvent, TaskEventType
from orion.core.tasks.memory_event_repository import (
    InMemoryTaskEventRepository,
)


def test_event_repository_can_save_and_get() -> None:
    repository = InMemoryTaskEventRepository()
    task_id = uuid4()

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Task created",
    )

    repository.save(event)

    retrieved_event = repository.get(event.id)

    assert retrieved_event is event


def test_event_repository_returns_none_for_unknown_event() -> None:
    repository = InMemoryTaskEventRepository()

    assert repository.get(uuid4()) is None


def test_event_repository_can_list_events_for_task() -> None:
    repository = InMemoryTaskEventRepository()

    task_id = uuid4()
    another_task_id = uuid4()

    first_event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Task created",
    )

    second_event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.STATUS_CHANGED,
        message="Task started",
    )

    unrelated_event = TaskEvent.create(
        task_id=another_task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Another task created",
    )

    repository.save(first_event)
    repository.save(second_event)
    repository.save(unrelated_event)

    events = repository.list_for_task(task_id)

    assert events == [first_event, second_event]


def test_event_repository_returns_empty_list_for_unknown_task() -> None:
    repository = InMemoryTaskEventRepository()

    assert repository.list_for_task(uuid4()) == []


def test_event_repository_preserves_event_order() -> None:
    repository = InMemoryTaskEventRepository()
    task_id = uuid4()

    first_event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Task created",
    )

    second_event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.STATUS_CHANGED,
        message="Planning started",
    )

    third_event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.STATUS_CHANGED,
        message="Execution started",
    )

    repository.save(first_event)
    repository.save(second_event)
    repository.save(third_event)

    events = repository.list_for_task(task_id)

    assert events == [first_event, second_event, third_event]

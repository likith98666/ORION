from uuid import uuid4

import pytest

from orion.core.tasks.events import TaskEvent, TaskEventType


def test_task_event_can_be_created() -> None:
    task_id = uuid4()

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Task created",
    )

    assert event.id is not None
    assert event.task_id == task_id
    assert event.event_type == TaskEventType.TASK_CREATED
    assert event.timestamp is not None
    assert event.message == "Task created"
    assert event.metadata == {}


def test_task_event_trims_message() -> None:
    task_id = uuid4()

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.STATUS_CHANGED,
        message="   Task started   ",
    )

    assert event.message == "Task started"


def test_task_event_rejects_empty_message() -> None:
    task_id = uuid4()

    with pytest.raises(ValueError, match="cannot be empty"):
        TaskEvent.create(
            task_id=task_id,
            event_type=TaskEventType.TASK_CREATED,
            message="",
        )


def test_task_event_rejects_whitespace_only_message() -> None:
    task_id = uuid4()

    with pytest.raises(ValueError, match="cannot be empty"):
        TaskEvent.create(
            task_id=task_id,
            event_type=TaskEventType.TASK_CREATED,
            message="     ",
        )


def test_task_event_preserves_metadata() -> None:
    task_id = uuid4()

    metadata = {
        "previous_status": "running",
        "new_status": "failed",
        "attempt": 1,
    }

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_FAILED,
        message="Task execution failed",
        metadata=metadata,
    )

    assert event.metadata == metadata


def test_task_event_metadata_is_copied() -> None:
    task_id = uuid4()

    metadata = {"attempt": 1}

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_FAILED,
        message="Task failed",
        metadata=metadata,
    )

    metadata["attempt"] = 99

    assert event.metadata["attempt"] == 1


def test_task_event_is_immutable() -> None:
    task_id = uuid4()

    event = TaskEvent.create(
        task_id=task_id,
        event_type=TaskEventType.TASK_CREATED,
        message="Task created",
    )

    with pytest.raises(AttributeError):
        event.message = "Modified"

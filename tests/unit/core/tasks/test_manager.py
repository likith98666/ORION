from uuid import uuid4

import pytest

from orion.core.tasks.manager import TaskManager
from orion.core.tasks.memory_event_repository import (
    InMemoryTaskEventRepository,
)
from orion.core.tasks.memory_repository import InMemoryTaskRepository
from orion.core.tasks.models import TaskStatus


def test_task_can_be_created() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Research the Indian AI education market")

    assert task.objective == "Research the Indian AI education market"
    assert task.status == TaskStatus.CREATED
    assert task.id is not None
    assert task.created_at is not None
    assert task.started_at is None
    assert task.completed_at is None
    assert task.attempt_count == 0
    assert task.last_error is None


def test_task_rejects_empty_objective() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.create_task("")


def test_task_rejects_whitespace_only_objective() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.create_task("     ")


def test_task_objective_is_trimmed() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("   Research autonomous AI systems   ")

    assert task.objective == "Research autonomous AI systems"


def test_task_has_default_execution_metadata() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Analyze autonomous AI systems")

    assert task.started_at is None
    assert task.completed_at is None
    assert task.attempt_count == 0
    assert task.last_error is None


def test_task_status_can_transition_to_planning() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Plan an AI research task")

    updated_task = manager.update_status(
        task.id,
        TaskStatus.PLANNING,
    )

    assert updated_task.status == TaskStatus.PLANNING
    assert updated_task.last_error is None


def test_task_status_can_transition_to_running() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Execute an AI task")

    manager.update_status(task.id, TaskStatus.PLANNING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.RUNNING,
    )

    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.started_at is not None
    assert updated_task.attempt_count == 1


def test_task_running_transition_increments_attempt_count() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Execute a task")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)
    manager.update_status(task.id, TaskStatus.WAITING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.RUNNING,
    )

    assert updated_task.attempt_count == 2


def test_task_can_transition_to_waiting() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Wait for external input")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.WAITING,
    )

    assert updated_task.status == TaskStatus.WAITING


def test_task_can_resume_from_waiting() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Resume a waiting task")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)
    manager.update_status(task.id, TaskStatus.WAITING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.RUNNING,
    )

    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.attempt_count == 2


def test_task_can_transition_to_verifying() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Verify an AI result")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.VERIFYING,
    )

    assert updated_task.status == TaskStatus.VERIFYING


def test_task_can_complete_after_verification() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Complete an AI task")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)
    manager.update_status(task.id, TaskStatus.VERIFYING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.COMPLETED,
    )

    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.completed_at is not None


def test_task_can_fail_with_error() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Run a failing task")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)

    updated_task = manager.update_status(
        task.id,
        TaskStatus.FAILED,
        error="Tool execution failed",
    )

    assert updated_task.status == TaskStatus.FAILED
    assert updated_task.last_error == "Tool execution failed"


def test_task_failed_requires_error_message() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Test missing failure reason")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)

    with pytest.raises(
        ValueError,
        match="An error message is required when a task fails",
    ):
        manager.update_status(
            task.id,
            TaskStatus.FAILED,
        )


def test_failed_task_can_return_to_planning() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Retry a failed task")

    manager.update_status(task.id, TaskStatus.PLANNING)
    manager.update_status(task.id, TaskStatus.RUNNING)
    manager.update_status(
        task.id,
        TaskStatus.FAILED,
        error="Temporary failure",
    )

    updated_task = manager.update_status(
        task.id,
        TaskStatus.PLANNING,
    )

    assert updated_task.status == TaskStatus.PLANNING
    assert updated_task.last_error is None


def test_task_can_be_cancelled_from_created_state() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Cancel a task")

    updated_task = manager.update_status(
        task.id,
        TaskStatus.CANCELLED,
    )

    assert updated_task.status == TaskStatus.CANCELLED


def test_update_status_rejects_invalid_transition() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Test invalid transition")

    with pytest.raises(
        ValueError,
        match="Invalid task transition",
    ):
        manager.update_status(
            task.id,
            TaskStatus.COMPLETED,
        )


def test_update_status_rejects_error_for_non_failed_status() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Test invalid error")

    with pytest.raises(
        ValueError,
        match="An error message can only be provided",
    ):
        manager.update_status(
            task.id,
            TaskStatus.PLANNING,
            error="Unexpected error",
        )


def test_update_status_rejects_unknown_task() -> None:
    manager = TaskManager(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )

    unknown_task_id = uuid4()

    with pytest.raises(
        ValueError,
        match="Task not found",
    ):
        manager.update_status(
            unknown_task_id,
            TaskStatus.PLANNING,
        )
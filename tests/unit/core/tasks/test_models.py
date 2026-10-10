import pytest

from orion.core.tasks.manager import TaskManager
from orion.core.tasks.memory_event_repository import (
    InMemoryTaskEventRepository,
)
from orion.core.tasks.memory_repository import InMemoryTaskRepository
from orion.core.tasks.models import Task, TaskStatus


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


def test_task_create_rejects_objective_over_10000_characters() -> None:
    objective = "x" * 10_001

    with pytest.raises(
        ValueError,
        match="Task objective cannot exceed 10,000 characters",
    ):
        Task.create(objective)

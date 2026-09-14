from orion.core.tasks.manager import TaskManager
from orion.core.tasks.memory_event_repository import (
    InMemoryTaskEventRepository,
)
from orion.core.tasks.memory_repository import InMemoryTaskRepository


def test_task_repository_can_save_and_get() -> None:
    repository = InMemoryTaskRepository()
    manager = TaskManager(
        repository,
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Research autonomous AI systems")

    repository.save(task)

    retrieved_task = repository.get(task.id)

    assert retrieved_task is task


def test_task_repository_can_delete() -> None:
    repository = InMemoryTaskRepository()
    manager = TaskManager(
        repository,
        InMemoryTaskEventRepository(),
    )

    task = manager.create_task("Analyze AI infrastructure")

    repository.save(task)
    repository.delete(task.id)

    assert repository.get(task.id) is None
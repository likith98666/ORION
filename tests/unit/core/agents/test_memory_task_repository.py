from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.memory_task_repository import (
    InMemoryAgentTaskRepository,
)
from orion.core.agents.tasks import AgentTask


def create_test_task(
    task_id=None,
    description="Research the AI education market.",
) -> AgentTask:
    return AgentTask.create(
        task_id=task_id or uuid4(),
        description=description,
        required_capability=AgentCapability.RESEARCH,
    )


def test_repository_starts_empty() -> None:
    repository = InMemoryAgentTaskRepository()

    assert repository.list_for_task(uuid4()) == []


def test_repository_can_save_and_get_task() -> None:
    repository = InMemoryAgentTaskRepository()
    task = create_test_task()

    repository.save(task)

    assert repository.get(task.id) is task


def test_repository_returns_none_for_unknown_task() -> None:
    repository = InMemoryAgentTaskRepository()

    assert repository.get(uuid4()) is None


def test_repository_can_delete_task() -> None:
    repository = InMemoryAgentTaskRepository()
    task = create_test_task()

    repository.save(task)
    repository.delete(task.id)

    assert repository.get(task.id) is None


def test_repository_delete_unknown_task_does_not_fail() -> None:
    repository = InMemoryAgentTaskRepository()

    repository.delete(uuid4())


def test_repository_lists_tasks_for_parent_task() -> None:
    repository = InMemoryAgentTaskRepository()
    parent_task_id = uuid4()

    first = create_test_task(
        task_id=parent_task_id,
        description="Research competitors.",
    )
    second = create_test_task(
        task_id=parent_task_id,
        description="Analyze market data.",
    )
    unrelated = create_test_task(
        task_id=uuid4(),
        description="Write a report.",
    )

    repository.save(first)
    repository.save(second)
    repository.save(unrelated)

    result = repository.list_for_task(parent_task_id)

    assert result == [first, second]


def test_repository_returns_empty_for_parent_with_no_tasks() -> None:
    repository = InMemoryAgentTaskRepository()

    assert repository.list_for_task(uuid4()) == []


def test_repository_can_replace_existing_task() -> None:
    repository = InMemoryAgentTaskRepository()

    task = create_test_task()
    repository.save(task)

    task.status = task.status.CANCELLED
    repository.save(task)

    result = repository.get(task.id)

    assert result is task
    assert result.status.value == "cancelled"
def test_repository_lists_all_tasks() -> None:
    repository = InMemoryAgentTaskRepository()

    first = create_test_task(
        description="Research competitors.",
    )
    second = create_test_task(
        description="Analyze market data.",
    )

    repository.save(first)
    repository.save(second)

    result = repository.list_all()

    assert result == [first, second]

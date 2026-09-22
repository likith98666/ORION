from datetime import timedelta

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.tasks import AgentTask
from orion.core.memory.context_provider import MemoryContextProvider
from orion.core.memory.models import MemoryImportance, MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService


def create_task(*, assigned: bool = True) -> AgentTask:
    task = AgentTask.create(
        task_id=__import__("uuid").uuid4(),
        description="Find previous execution knowledge about deployment.",
        required_capability=AgentCapability.REASONING,
    )

    if assigned:
        task.assigned_agent_id = __import__("uuid").uuid4()

    return task


def test_provider_builds_execution_memory_context() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = create_task()
    service.remember(
        content="Previous deployment succeeded using the staging model.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.MEDIUM,
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(task)

    assert context.task_id == task.task_id
    assert context.agent_id == task.assigned_agent_id
    assert context.memory_count == 1
    assert context.is_empty is False


def test_provider_respects_max_memories() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = create_task()

    for index in range(5):
        service.remember(
            content=f"Deployment knowledge item {index}.",
            memory_type=MemoryType.EPISODIC,
            task_id=task.task_id,
            agent_id=task.assigned_agent_id,
        )

    provider = MemoryContextProvider(
        service,
        max_memories=2,
    )

    context = provider.provide(task)

    assert context.memory_count == 2
    assert context.max_memories == 2


def test_provider_forwards_memory_filters() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = create_task()

    service.remember(
        content="Previous execution knowledge about deployment is important.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.HIGH,
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    service.remember(
        content="Low importance deployment note.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.LOW,
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    provider = MemoryContextProvider(
        service,
        minimum_importance=MemoryImportance.HIGH,
        memory_types=frozenset({MemoryType.EPISODIC}),
        max_age=timedelta(days=30),
    )

    context = provider.provide(task)

    assert context.memory_count == 1
    assert context.memories[0].memory.importance == MemoryImportance.HIGH


def test_provider_returns_empty_context_when_no_memory_matches() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = create_task()

    provider = MemoryContextProvider(service)

    context = provider.provide(task)

    assert context.is_empty is True
    assert context.memory_count == 0


def test_provider_requires_assigned_agent() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = create_task(assigned=False)

    provider = MemoryContextProvider(service)

    with pytest.raises(
        ValueError,
        match="assigned agent",
    ):
        provider.provide(task)


def test_provider_rejects_invalid_max_memories() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    with pytest.raises(
        ValueError,
        match="between 1 and 100",
    ):
        MemoryContextProvider(
            service,
            max_memories=0,
        )

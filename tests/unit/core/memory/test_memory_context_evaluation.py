from datetime import timedelta
from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.tasks import AgentTask
from orion.core.memory.context_provider import MemoryContextProvider
from orion.core.memory.models import MemoryImportance, MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService


def make_task(
    *,
    task_id=None,
    agent_id=None,
    description="Analyze the deployment failure",
) -> AgentTask:
    task = AgentTask.create(
        task_id=task_id or uuid4(),
        description=description,
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = agent_id or uuid4()
    return task


def make_memory(
    service: MemoryService,
    content: str,
    *,
    task_id=None,
    agent_id=None,
    memory_type=MemoryType.LONG_TERM,
    importance=MemoryImportance.MEDIUM,
):
    return service.remember(
        content=content,
        memory_type=memory_type,
        importance=importance,
        task_id=task_id,
        agent_id=agent_id,
    )


def test_provider_returns_relevant_memory_for_current_task():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)
    task = make_task()

    relevant = make_memory(
        service,
        "Deployment failed because the model endpoint timed out.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )
    make_memory(
        service,
        "Unrelated discussion about image preprocessing.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(task)

    assert context.task_id == task.task_id
    assert context.agent_id == task.assigned_agent_id
    assert context.memory_count >= 1
    assert context.memories[0].memory.id == relevant.id


def test_provider_considers_relevant_prior_task_memory_for_same_agent():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    agent_id = uuid4()
    current_task = make_task(
        agent_id=agent_id,
        description="Diagnose why the production model endpoint is timing out",
    )

    prior_task_memory = make_memory(
        service,
        "A previous production deployment had the same model endpoint timeout; "
        "the root cause was an overloaded inference worker.",
        task_id=uuid4(),
        agent_id=agent_id,
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH,
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(current_task)

    returned_ids = {result.memory.id for result in context.memories}

    assert prior_task_memory.id in returned_ids


def test_provider_considers_relevant_cross_agent_memory():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task_id = uuid4()
    current_agent = uuid4()
    other_agent = uuid4()

    current_task = make_task(
        task_id=task_id,
        agent_id=current_agent,
        description="Diagnose the production model endpoint timeout",
    )

    cross_agent = make_memory(
        service,
        "Another agent previously diagnosed the same production model endpoint "
        "timeout and found an overloaded inference worker.",
        task_id=task_id,
        agent_id=other_agent,
        importance=MemoryImportance.HIGH,
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(current_task)

    returned_ids = {result.memory.id for result in context.memories}

    assert cross_agent.id in returned_ids


def test_provider_considers_relevant_global_long_term_memory():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    current_task = make_task(
        description="Diagnose why the production model endpoint is timing out",
    )

    global_memory = make_memory(
        service,
        "Production model endpoints can experience transient timeouts "
        "when inference workers are overloaded; bounded retry with backoff "
        "is appropriate for transient failures.",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH,
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(current_task)

    returned_ids = {result.memory.id for result in context.memories}

    assert global_memory.id in returned_ids


def test_provider_respects_max_memories():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = make_task()

    for index in range(10):
        make_memory(
            service,
            f"Deployment failure observation number {index}.",
            task_id=task.task_id,
            agent_id=task.assigned_agent_id,
        )

    provider = MemoryContextProvider(service, max_memories=3)

    context = provider.provide(task)

    assert context.memory_count == 3
    assert len(context.memories) == 3


def test_provider_respects_memory_type_filter():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = make_task()

    short_term = make_memory(
        service,
        "Deployment timeout from current execution.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
        memory_type=MemoryType.SHORT_TERM,
    )

    make_memory(
        service,
        "Deployment timeout from historical execution.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
        memory_type=MemoryType.LONG_TERM,
    )

    provider = MemoryContextProvider(
        service,
        memory_types=frozenset({MemoryType.SHORT_TERM}),
    )

    context = provider.provide(task)

    returned_ids = {result.memory.id for result in context.memories}

    assert short_term.id in returned_ids
    assert len(context.memories) == 1


def test_provider_respects_minimum_importance():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = make_task()

    high = make_memory(
        service,
        "Critical deployment failure requiring recovery.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
        importance=MemoryImportance.HIGH,
    )

    make_memory(
        service,
        "Minor deployment observation.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
        importance=MemoryImportance.LOW,
    )

    provider = MemoryContextProvider(
        service,
        minimum_importance=MemoryImportance.HIGH,
    )

    context = provider.provide(task)

    returned_ids = {result.memory.id for result in context.memories}

    assert high.id in returned_ids
    assert len(context.memories) == 1


def test_provider_respects_max_age():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = make_task()

    recent = make_memory(
        service,
        "Recent deployment timeout investigation.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    old = make_memory(
        service,
        "Old deployment timeout investigation.",
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )
    old.created_at = recent.created_at - timedelta(days=30)

    provider = MemoryContextProvider(
        service,
        max_age=timedelta(days=7),
    )

    context = provider.provide(task)

    returned_ids = {result.memory.id for result in context.memories}

    assert recent.id in returned_ids
    assert old.id not in returned_ids


def test_provider_excludes_semantically_irrelevant_memory():
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository)

    task = make_task(
        description="Analyze the deployment failure",
    )

    make_memory(
        service,
        "Completely unrelated database migration information.",
        task_id=uuid4(),
        agent_id=uuid4(),
    )

    provider = MemoryContextProvider(service)

    context = provider.provide(task)

    assert context.is_empty
    assert context.memory_count == 0

from uuid import uuid4

from orion.core.memory.models import MemoryImportance, MemoryRecord, MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository


def create_memory(
    memory_type: MemoryType = MemoryType.LONG_TERM,
    task_id=None,
    agent_id=None,
) -> MemoryRecord:
    return MemoryRecord.create(
        content="Reusable ORION memory.",
        memory_type=memory_type,
        importance=MemoryImportance.MEDIUM,
        task_id=task_id,
        agent_id=agent_id,
    )


def test_save_and_get_memory() -> None:
    repository = InMemoryMemoryRepository()
    memory = create_memory()

    repository.save(memory)

    assert repository.get(memory.id) == memory


def test_get_missing_memory_returns_none() -> None:
    repository = InMemoryMemoryRepository()

    assert repository.get(uuid4()) is None


def test_delete_memory() -> None:
    repository = InMemoryMemoryRepository()
    memory = create_memory()

    repository.save(memory)
    repository.delete(memory.id)

    assert repository.get(memory.id) is None


def test_list_memories_for_task() -> None:
    repository = InMemoryMemoryRepository()
    task_id = uuid4()

    matching = create_memory(task_id=task_id)
    other = create_memory(task_id=uuid4())

    repository.save(matching)
    repository.save(other)

    assert repository.list_for_task(task_id) == [matching]


def test_list_memories_for_agent() -> None:
    repository = InMemoryMemoryRepository()
    agent_id = uuid4()

    matching = create_memory(agent_id=agent_id)
    other = create_memory(agent_id=uuid4())

    repository.save(matching)
    repository.save(other)

    assert repository.list_for_agent(agent_id) == [matching]


def test_list_memories_by_type() -> None:
    repository = InMemoryMemoryRepository()

    short_term = create_memory(MemoryType.SHORT_TERM)
    long_term = create_memory(MemoryType.LONG_TERM)
    episodic = create_memory(MemoryType.EPISODIC)

    repository.save(short_term)
    repository.save(long_term)
    repository.save(episodic)

    assert repository.list_by_type(MemoryType.SHORT_TERM) == [short_term]
    assert repository.list_by_type(MemoryType.LONG_TERM) == [long_term]
    assert repository.list_by_type(MemoryType.EPISODIC) == [episodic]


def test_list_all_memories() -> None:
    repository = InMemoryMemoryRepository()

    first = create_memory()
    second = create_memory()

    repository.save(first)
    repository.save(second)

    assert repository.list_all() == [first, second]


def test_save_replaces_existing_memory() -> None:
    repository = InMemoryMemoryRepository()
    memory = create_memory()

    repository.save(memory)
    memory.content = "Updated memory."
    repository.save(memory)

    stored = repository.get(memory.id)

    assert stored is memory
    assert stored.content == "Updated memory."

from uuid import uuid4

from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)
from orion.core.memory.models import MemoryImportance, MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService


def create_service() -> MemoryService:
    return MemoryService(InMemoryMemoryRepository())


def test_remember_creates_and_persists_memory() -> None:
    service = create_service()

    memory = service.remember(
        content="Important research finding.",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH,
    )

    assert memory.content == "Important research finding."
    assert memory.memory_type == MemoryType.LONG_TERM
    assert memory.importance == MemoryImportance.HIGH
    assert memory.access_count == 0


def test_get_memory_tracks_access() -> None:
    service = create_service()

    memory = service.remember(
        content="Reusable information.",
        memory_type=MemoryType.LONG_TERM,
    )

    retrieved = service.get(memory.id)

    assert retrieved is memory
    assert retrieved.access_count == 1
    assert retrieved.last_accessed_at is not None


def test_repeated_access_increments_access_count() -> None:
    service = create_service()

    memory = service.remember(
        content="Frequently used information.",
        memory_type=MemoryType.LONG_TERM,
    )

    service.get(memory.id)
    service.get(memory.id)

    assert memory.access_count == 2


def test_missing_memory_returns_none() -> None:
    service = create_service()

    assert service.get(uuid4()) is None


def test_list_for_task_tracks_access() -> None:
    service = create_service()
    task_id = uuid4()

    first = service.remember(
        content="Task memory one.",
        memory_type=MemoryType.SHORT_TERM,
        task_id=task_id,
    )
    second = service.remember(
        content="Task memory two.",
        memory_type=MemoryType.EPISODIC,
        task_id=task_id,
    )

    memories = service.list_for_task(task_id)

    assert memories == [first, second]
    assert first.access_count == 1
    assert second.access_count == 1


def test_list_for_agent_tracks_access() -> None:
    service = create_service()
    agent_id = uuid4()

    memory = service.remember(
        content="Agent-specific knowledge.",
        memory_type=MemoryType.LONG_TERM,
        agent_id=agent_id,
    )

    memories = service.list_for_agent(agent_id)

    assert memories == [memory]
    assert memory.access_count == 1


def test_list_by_type_tracks_access() -> None:
    service = create_service()

    memory = service.remember(
        content="Current execution context.",
        memory_type=MemoryType.SHORT_TERM,
    )

    memories = service.list_by_type(MemoryType.SHORT_TERM)

    assert memories == [memory]
    assert memory.access_count == 1


def test_delete_memory() -> None:
    service = create_service()

    memory = service.remember(
        content="Temporary information.",
        memory_type=MemoryType.SHORT_TERM,
    )

    service.delete(memory.id)

    assert service.get(memory.id) is None


def test_remember_completed_execution() -> None:
    service = create_service()

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )
    execution.status = AgentExecutionStatus.COMPLETED
    execution.output = "Research completed."
    execution.model_name = "test-model"
    execution.provider_name = "test-provider"
    execution.input_tokens = 100
    execution.output_tokens = 50
    execution.latency_ms = 250.0

    task_id = uuid4()

    memory = service.remember_execution(
        execution=execution,
        task_id=task_id,
    )

    assert memory.memory_type == MemoryType.EPISODIC
    assert memory.importance == MemoryImportance.MEDIUM
    assert memory.task_id == task_id
    assert memory.agent_id == execution.agent_id
    assert memory.source_execution_id == execution.id
    assert "Research completed." in memory.content
    assert memory.metadata["execution_status"] == "completed"
    assert memory.metadata["model_name"] == "test-model"
    assert memory.metadata["latency_ms"] == 250.0


def test_remember_failed_execution() -> None:
    service = create_service()

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )
    execution.status = AgentExecutionStatus.FAILED
    execution.error_message = "Model timeout."

    memory = service.remember_execution(execution)

    assert memory.memory_type == MemoryType.EPISODIC
    assert memory.importance == MemoryImportance.HIGH
    assert memory.source_execution_id == execution.id
    assert "Model timeout." in memory.content
    assert memory.metadata["execution_status"] == "failed"


def test_remember_non_terminal_execution() -> None:
    service = create_service()

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    memory = service.remember_execution(execution)

    assert memory.memory_type == MemoryType.EPISODIC
    assert memory.importance == MemoryImportance.LOW
    assert memory.source_execution_id == execution.id
    assert memory.metadata["execution_status"] == "running"

from uuid import uuid4

import pytest

from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.models import MemoryImportance, MemoryRecord, MemoryType
from orion.core.memory.retrieval_models import MemoryRetrievalResult


def create_result() -> MemoryRetrievalResult:
    memory = MemoryRecord.create(
        memory_type=MemoryType.EPISODIC,
        content="Previous execution result.",
        importance=MemoryImportance.MEDIUM,
        task_id=uuid4(),
        agent_id=uuid4(),
    )

    return MemoryRetrievalResult(
        memory=memory,
        score=0.8,
        reasons=("query_relevance",),
    )


def test_execution_memory_context_stores_bounded_results() -> None:
    task_id = uuid4()
    agent_id = uuid4()
    result = create_result()

    context = ExecutionMemoryContext(
        task_id=task_id,
        agent_id=agent_id,
        memories=(result,),
    )

    assert context.task_id == task_id
    assert context.agent_id == agent_id
    assert context.memories == (result,)
    assert context.memory_count == 1
    assert context.is_empty is False


def test_execution_memory_context_can_be_empty() -> None:
    context = ExecutionMemoryContext(
        task_id=uuid4(),
        agent_id=uuid4(),
    )

    assert context.memories == ()
    assert context.memory_count == 0
    assert context.is_empty is True


def test_execution_memory_context_rejects_non_uuid_task_id() -> None:
    with pytest.raises(TypeError, match="task_id must be a UUID"):
        ExecutionMemoryContext(
            task_id="invalid",
            agent_id=uuid4(),
        )


def test_execution_memory_context_rejects_non_uuid_agent_id() -> None:
    with pytest.raises(TypeError, match="agent_id must be a UUID"):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id="invalid",
        )


def test_execution_memory_context_rejects_list() -> None:
    with pytest.raises(TypeError, match="memories must be a tuple"):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id=uuid4(),
            memories=[create_result()],
        )


def test_execution_memory_context_rejects_invalid_maximum() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id=uuid4(),
            max_memories=0,
        )


def test_execution_memory_context_rejects_too_many_memories() -> None:
    results = tuple(create_result() for _ in range(2))

    with pytest.raises(ValueError, match="cannot exceed max_memories"):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id=uuid4(),
            memories=results,
            max_memories=1,
        )


def test_execution_memory_context_rejects_duplicate_memory_ids() -> None:
    result = create_result()

    with pytest.raises(ValueError, match="Duplicate memory"):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id=uuid4(),
            memories=(result, result),
        )


def test_execution_memory_context_rejects_invalid_result() -> None:
    with pytest.raises(
        TypeError,
        match="MemoryRetrievalResult instances",
    ):
        ExecutionMemoryContext(
            task_id=uuid4(),
            agent_id=uuid4(),
            memories=("invalid",),
        )

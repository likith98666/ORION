from uuid import uuid4

import pytest

from orion.core.memory.models import (
    MemoryImportance,
    MemoryRecord,
    MemoryType,
)


def test_create_memory_record() -> None:
    task_id = uuid4()
    agent_id = uuid4()
    execution_id = uuid4()

    memory = MemoryRecord.create(
        content="Python dependency failed during execution.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.HIGH,
        task_id=task_id,
        agent_id=agent_id,
        source_execution_id=execution_id,
        metadata={"category": "failure"},
    )

    assert memory.content == "Python dependency failed during execution."
    assert memory.memory_type == MemoryType.EPISODIC
    assert memory.importance == MemoryImportance.HIGH
    assert memory.task_id == task_id
    assert memory.agent_id == agent_id
    assert memory.source_execution_id == execution_id
    assert memory.metadata == {"category": "failure"}
    assert memory.access_count == 0
    assert memory.last_accessed_at is None


def test_create_memory_record_strips_content() -> None:
    memory = MemoryRecord.create(
        content="  reusable research finding  ",
        memory_type=MemoryType.LONG_TERM,
    )

    assert memory.content == "reusable research finding"


def test_memory_record_rejects_empty_content() -> None:
    with pytest.raises(
        ValueError,
        match="Memory content cannot be empty.",
    ):
        MemoryRecord.create(
            content="   ",
            memory_type=MemoryType.SHORT_TERM,
        )


def test_memory_record_rejects_oversized_content() -> None:
    with pytest.raises(
        ValueError,
        match="Memory content cannot exceed 20,000 characters.",
    ):
        MemoryRecord.create(
            content="x" * 20_001,
            memory_type=MemoryType.LONG_TERM,
        )


def test_memory_record_defaults() -> None:
    memory = MemoryRecord.create(
        content="Current task context.",
        memory_type=MemoryType.SHORT_TERM,
    )

    assert memory.importance == MemoryImportance.MEDIUM
    assert memory.task_id is None
    assert memory.agent_id is None
    assert memory.source_execution_id is None
    assert memory.metadata == {}


def test_memory_record_has_unique_id() -> None:
    first = MemoryRecord.create(
        content="First memory.",
        memory_type=MemoryType.LONG_TERM,
    )
    second = MemoryRecord.create(
        content="Second memory.",
        memory_type=MemoryType.LONG_TERM,
    )

    assert first.id != second.id

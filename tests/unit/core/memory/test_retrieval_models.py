from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.memory.models import (
    MemoryImportance,
    MemoryRecord,
    MemoryType,
)
from orion.core.memory.retrieval_models import (
    MemoryQuery,
    MemoryRetrievalResult,
)


def test_memory_query_accepts_valid_values() -> None:
    task_id = uuid4()
    agent_id = uuid4()

    query = MemoryQuery(
        query="previous execution failures",
        task_id=task_id,
        agent_id=agent_id,
        memory_types=frozenset({MemoryType.EPISODIC}),
        minimum_importance=MemoryImportance.MEDIUM,
        limit=10,
    )

    assert query.query == "previous execution failures"
    assert query.task_id == task_id
    assert query.agent_id == agent_id
    assert query.memory_types == frozenset({MemoryType.EPISODIC})
    assert query.minimum_importance == MemoryImportance.MEDIUM
    assert query.limit == 10


def test_memory_query_strips_query() -> None:
    query = MemoryQuery(query="  previous result  ")

    assert query.query == "previous result"


def test_memory_query_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        MemoryQuery(query="   ")


def test_memory_query_rejects_query_over_limit() -> None:
    with pytest.raises(ValueError, match="5,000"):
        MemoryQuery(query="x" * 5_001)


@pytest.mark.parametrize("limit", [0, -1])
def test_memory_query_rejects_invalid_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        MemoryQuery(query="test", limit=limit)


def test_memory_query_rejects_limit_over_100() -> None:
    with pytest.raises(ValueError, match="exceed 100"):
        MemoryQuery(query="test", limit=101)


def test_memory_query_rejects_invalid_date_range() -> None:
    earlier = datetime(2026, 1, 2)
    later = datetime(2026, 1, 1)

    with pytest.raises(ValueError, match="created_after"):
        MemoryQuery(
            query="test",
            created_after=earlier,
            created_before=later,
        )


def test_memory_query_rejects_negative_max_age() -> None:
    with pytest.raises(ValueError, match="max_age"):
        MemoryQuery(
            query="test",
            max_age=-timedelta(seconds=1),
        )


def test_memory_query_normalizes_memory_types() -> None:
    query = MemoryQuery(
        query="test",
        memory_types={MemoryType.EPISODIC},
    )

    assert isinstance(query.memory_types, frozenset)
    assert MemoryType.EPISODIC in query.memory_types


def test_memory_retrieval_result_accepts_valid_result() -> None:
    memory = MemoryRecord.create(
        content="Previous execution succeeded.",
        memory_type=MemoryType.EPISODIC,
    )

    result = MemoryRetrievalResult(
        memory=memory,
        score=0.85,
        reasons=(
            "query_relevance",
            "recent",
        ),
    )

    assert result.memory is memory
    assert result.score == 0.85
    assert result.reasons == (
        "query_relevance",
        "recent",
    )


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_memory_retrieval_result_rejects_invalid_score(
    score: float,
) -> None:
    memory = MemoryRecord.create(
        content="Previous execution succeeded.",
        memory_type=MemoryType.EPISODIC,
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        MemoryRetrievalResult(
            memory=memory,
            score=score,
        )


def test_memory_retrieval_result_rejects_invalid_memory() -> None:
    with pytest.raises(TypeError, match="MemoryRecord"):
        MemoryRetrievalResult(
            memory="not-memory",  # type: ignore[arg-type]
            score=0.5,
        )


def test_memory_retrieval_result_rejects_empty_reason() -> None:
    memory = MemoryRecord.create(
        content="Previous execution succeeded.",
        memory_type=MemoryType.EPISODIC,
    )

    with pytest.raises(ValueError, match="empty"):
        MemoryRetrievalResult(
            memory=memory,
            score=0.5,
            reasons=("query_relevance", " "),
        )

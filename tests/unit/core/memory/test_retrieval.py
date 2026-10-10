from datetime import datetime, timedelta
from uuid import uuid4

from orion.core.memory.models import (
    MemoryImportance,
    MemoryRecord,
    MemoryType,
)
from orion.core.memory.retrieval import MemoryRetrieval
from orion.core.memory.retrieval_models import MemoryQuery


def create_memory(
    content: str,
    *,
    importance: MemoryImportance = MemoryImportance.MEDIUM,
    task_id=None,
    agent_id=None,
    created_at=None,
    access_count: int = 0,
) -> MemoryRecord:
    memory = MemoryRecord.create(
        content=content,
        memory_type=MemoryType.EPISODIC,
        importance=importance,
        task_id=task_id,
        agent_id=agent_id,
    )

    if created_at is not None:
        memory.created_at = created_at

    memory.access_count = access_count

    return memory


def test_retrieval_returns_matching_memory() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memory = create_memory(
        "Previous model failure during execution.",
        created_at=now,
    )

    unrelated = create_memory(
        "Database migration completed.",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [memory, unrelated],
        MemoryQuery(query="model failure"),
        now=now,
    )

    assert results
    assert results[0].memory is memory


def test_retrieval_respects_limit() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memories = [
        create_memory(f"model execution failure {index}", created_at=now) for index in range(10)
    ]

    results = MemoryRetrieval().retrieve(
        memories,
        MemoryQuery(query="model execution failure", limit=3),
        now=now,
    )

    assert len(results) == 3


def test_retrieval_filters_by_task() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    task_id = uuid4()

    matching = create_memory(
        "execution failure",
        task_id=task_id,
        created_at=now,
    )

    unrelated = create_memory(
        "execution failure",
        task_id=uuid4(),
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [matching, unrelated],
        MemoryQuery(
            query="execution failure",
            task_id=task_id,
        ),
        now=now,
    )

    assert [result.memory for result in results] == [matching]


def test_retrieval_filters_by_agent() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    agent_id = uuid4()

    matching = create_memory(
        "execution failure",
        agent_id=agent_id,
        created_at=now,
    )

    unrelated = create_memory(
        "execution failure",
        agent_id=uuid4(),
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [matching, unrelated],
        MemoryQuery(
            query="execution failure",
            agent_id=agent_id,
        ),
        now=now,
    )

    assert [result.memory for result in results] == [matching]


def test_retrieval_filters_by_memory_type() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    episodic = create_memory(
        "execution failure",
        created_at=now,
    )

    long_term = MemoryRecord.create(
        content="execution failure",
        memory_type=MemoryType.LONG_TERM,
    )
    long_term.created_at = now

    results = MemoryRetrieval().retrieve(
        [episodic, long_term],
        MemoryQuery(
            query="execution failure",
            memory_types=frozenset({MemoryType.EPISODIC}),
        ),
        now=now,
    )

    assert [result.memory for result in results] == [episodic]


def test_retrieval_filters_by_minimum_importance() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    low = create_memory(
        "execution failure",
        importance=MemoryImportance.LOW,
        created_at=now,
    )

    high = create_memory(
        "execution failure",
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [low, high],
        MemoryQuery(
            query="execution failure",
            minimum_importance=MemoryImportance.HIGH,
        ),
        now=now,
    )

    assert [result.memory for result in results] == [high]


def test_retrieval_filters_by_age() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    recent = create_memory(
        "execution failure",
        created_at=now - timedelta(hours=1),
    )

    old = create_memory(
        "execution failure",
        created_at=now - timedelta(days=10),
    )

    results = MemoryRetrieval().retrieve(
        [recent, old],
        MemoryQuery(
            query="execution failure",
            max_age=timedelta(days=1),
        ),
        now=now,
    )

    assert [result.memory for result in results] == [recent]


def test_retrieval_filters_by_created_range() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    inside = create_memory(
        "execution failure",
        created_at=datetime(2026, 9, 20, 12, 0, 0),
    )

    outside = create_memory(
        "execution failure",
        created_at=datetime(2026, 9, 10, 12, 0, 0),
    )

    results = MemoryRetrieval().retrieve(
        [inside, outside],
        MemoryQuery(
            query="execution failure",
            created_after=datetime(2026, 9, 19, 0, 0, 0),
            created_before=datetime(2026, 9, 21, 0, 0, 0),
        ),
        now=now,
    )

    assert [result.memory for result in results] == [inside]


def test_higher_query_relevance_ranks_higher() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    exact = create_memory(
        "model failure recovery execution",
        created_at=now,
    )

    partial = create_memory(
        "model execution",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [partial, exact],
        MemoryQuery(query="model failure recovery"),
        now=now,
    )

    assert results[0].memory is exact
    assert results[0].score > results[1].score


def test_high_importance_affects_score() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    high = create_memory(
        "execution result",
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    low = create_memory(
        "execution result",
        importance=MemoryImportance.LOW,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [low, high],
        MemoryQuery(query="execution result"),
        now=now,
    )

    assert results[0].memory is high


def test_task_scope_contributes_to_ranking() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    task_id = uuid4()

    scoped = create_memory(
        "execution result",
        task_id=task_id,
        created_at=now,
    )

    unscoped = create_memory(
        "execution result",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [unscoped, scoped],
        MemoryQuery(
            query="execution result",
            task_id=task_id,
        ),
        now=now,
    )

    assert results[0].memory is scoped
    assert "task_scope_match" in results[0].reasons


def test_agent_scope_contributes_to_ranking() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    agent_id = uuid4()

    scoped = create_memory(
        "execution result",
        agent_id=agent_id,
        created_at=now,
    )

    unscoped = create_memory(
        "execution result",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [unscoped, scoped],
        MemoryQuery(
            query="execution result",
            agent_id=agent_id,
        ),
        now=now,
    )

    assert results[0].memory is scoped
    assert "agent_scope_match" in results[0].reasons


def test_recent_memory_receives_recency_reason() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    recent = create_memory(
        "recent execution result",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [recent],
        MemoryQuery(query="execution"),
        now=now,
    )

    assert "recent" in results[0].reasons


def test_accessed_memory_receives_usefulness_reason() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memory = create_memory(
        "execution result",
        created_at=now,
        access_count=3,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(query="execution"),
        now=now,
    )

    assert "previously_accessed" in results[0].reasons


def test_empty_candidates_return_empty_results() -> None:
    results = MemoryRetrieval().retrieve(
        [],
        MemoryQuery(query="anything"),
    )

    assert results == []


def test_retrieval_is_deterministic() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memories = [
        create_memory(
            f"execution result {index}",
            created_at=now,
        )
        for index in range(5)
    ]

    query = MemoryQuery(query="execution result", limit=5)
    retrieval = MemoryRetrieval()

    first = retrieval.retrieve(memories, query, now=now)
    second = retrieval.retrieve(memories, query, now=now)

    assert [result.memory.id for result in first] == [result.memory.id for result in second]


def test_scores_are_bounded() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memory = create_memory(
        "model failure recovery execution",
        importance=MemoryImportance.HIGH,
        task_id=uuid4(),
        agent_id=uuid4(),
        created_at=now,
        access_count=100,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(
            query="model failure recovery execution",
            task_id=memory.task_id,
            agent_id=memory.agent_id,
        ),
        now=now,
    )

    assert 0.0 <= results[0].score <= 1.0


def test_importance_is_used_as_deterministic_tie_breaker() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    low = create_memory(
        "exact matching content",
        importance=MemoryImportance.LOW,
        created_at=now,
    )

    high = create_memory(
        "exact matching content",
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [low, high],
        MemoryQuery(query="exact matching content", limit=2),
        now=now,
    )

    assert results[0].memory is high
    assert results[1].memory is low

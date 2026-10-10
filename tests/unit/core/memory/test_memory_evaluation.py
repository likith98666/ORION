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
    memory_type: MemoryType = MemoryType.EPISODIC,
    task_id=None,
    agent_id=None,
    created_at: datetime | None = None,
    access_count: int = 0,
) -> MemoryRecord:
    memory = MemoryRecord.create(
        content=content,
        memory_type=memory_type,
        importance=importance,
        task_id=task_id,
        agent_id=agent_id,
    )

    if created_at is not None:
        memory.created_at = created_at

    memory.access_count = access_count
    return memory


def test_evaluation_relevant_memory_ranks_above_unrelated_memory() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    relevant = create_memory(
        "Python deployment failed because the model input schema was invalid.",
        importance=MemoryImportance.MEDIUM,
        created_at=now,
    )

    unrelated = create_memory(
        "Database backup completed successfully.",
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [unrelated, relevant],
        MemoryQuery(query="model input schema deployment failure"),
        now=now,
    )

    assert results[0].memory is relevant


def test_evaluation_same_task_memory_gets_scope_bonus() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    task_id = uuid4()

    scoped = create_memory(
        "deployment model failure",
        task_id=task_id,
        created_at=now,
    )

    unscoped = create_memory(
        "deployment model failure",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [unscoped, scoped],
        MemoryQuery(
            query="deployment model failure",
            task_id=task_id,
        ),
        now=now,
    )

    assert results[0].memory is scoped
    assert "task_scope_match" in results[0].reasons


def test_evaluation_same_agent_memory_gets_scope_bonus() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)
    agent_id = uuid4()

    scoped = create_memory(
        "deployment model failure",
        agent_id=agent_id,
        created_at=now,
    )

    unscoped = create_memory(
        "deployment model failure",
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [unscoped, scoped],
        MemoryQuery(
            query="deployment model failure",
            agent_id=agent_id,
        ),
        now=now,
    )

    assert results[0].memory is scoped
    assert "agent_scope_match" in results[0].reasons


def test_evaluation_long_term_global_memory_is_retrievable_without_scope_filters() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memory = create_memory(
        "Global deployment architecture guidance.",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(query="deployment architecture guidance"),
        now=now,
    )

    assert len(results) == 1
    assert results[0].memory is memory


def test_evaluation_cross_task_memory_is_retrievable_when_no_task_filter_is_requested() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    previous_task = uuid4()

    memory = create_memory(
        "Previous deployment task discovered a schema validation failure.",
        task_id=previous_task,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(query="schema validation failure deployment"),
        now=now,
    )

    assert len(results) == 1
    assert results[0].memory is memory


def test_evaluation_cross_agent_memory_is_retrievable_when_no_agent_filter_is_requested() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    previous_agent = uuid4()

    memory = create_memory(
        "Previous agent discovered a deployment configuration issue.",
        agent_id=previous_agent,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(query="deployment configuration issue"),
        now=now,
    )

    assert len(results) == 1
    assert results[0].memory is memory


def test_evaluation_explicit_task_filter_remains_strict() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    requested_task = uuid4()

    matching = create_memory(
        "deployment failure",
        task_id=requested_task,
        created_at=now,
    )

    different_task = create_memory(
        "deployment failure",
        task_id=uuid4(),
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [different_task, matching],
        MemoryQuery(
            query="deployment failure",
            task_id=requested_task,
        ),
        now=now,
    )

    assert [result.memory for result in results] == [matching]


def test_evaluation_explicit_agent_filter_remains_strict() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    requested_agent = uuid4()

    matching = create_memory(
        "deployment failure",
        agent_id=requested_agent,
        created_at=now,
    )

    different_agent = create_memory(
        "deployment failure",
        agent_id=uuid4(),
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [different_agent, matching],
        MemoryQuery(
            query="deployment failure",
            agent_id=requested_agent,
        ),
        now=now,
    )

    assert [result.memory for result in results] == [matching]


def test_evaluation_importance_filter_and_ranking_work_together() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    medium = create_memory(
        "model deployment recovery",
        importance=MemoryImportance.MEDIUM,
        created_at=now,
    )

    high = create_memory(
        "model deployment recovery",
        importance=MemoryImportance.HIGH,
        created_at=now,
    )

    low = create_memory(
        "model deployment recovery",
        importance=MemoryImportance.LOW,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [low, medium, high],
        MemoryQuery(
            query="model deployment recovery",
            minimum_importance=MemoryImportance.MEDIUM,
            limit=2,
        ),
        now=now,
    )

    assert len(results) == 2
    assert results[0].memory is high
    assert results[1].memory is medium


def test_evaluation_recency_prefers_recent_memory_when_relevance_is_equal() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    recent = create_memory(
        "deployment execution result",
        created_at=now,
    )

    older = create_memory(
        "deployment execution result",
        created_at=now - timedelta(days=30),
    )

    results = MemoryRetrieval().retrieve(
        [older, recent],
        MemoryQuery(query="deployment execution result"),
        now=now,
    )

    assert results[0].memory is recent
    assert results[0].score > results[1].score


def test_evaluation_accessed_memory_receives_usefulness_signal() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    accessed = create_memory(
        "deployment execution result",
        access_count=5,
        created_at=now,
    )

    fresh = create_memory(
        "deployment execution result",
        access_count=0,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [fresh, accessed],
        MemoryQuery(query="deployment execution result"),
        now=now,
    )

    assert results[0].memory is accessed
    assert "previously_accessed" in results[0].reasons


def test_evaluation_top_k_is_strictly_bounded() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memories = [
        create_memory(
            f"deployment execution result {index}",
            created_at=now,
        )
        for index in range(20)
    ]

    results = MemoryRetrieval().retrieve(
        memories,
        MemoryQuery(
            query="deployment execution result",
            limit=5,
        ),
        now=now,
    )

    assert len(results) == 5


def test_evaluation_scores_are_always_bounded() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memory = create_memory(
        "model deployment recovery execution",
        importance=MemoryImportance.HIGH,
        task_id=uuid4(),
        agent_id=uuid4(),
        access_count=100,
        created_at=now,
    )

    results = MemoryRetrieval().retrieve(
        [memory],
        MemoryQuery(
            query="model deployment recovery execution",
            task_id=memory.task_id,
            agent_id=memory.agent_id,
        ),
        now=now,
    )

    assert 0.0 <= results[0].score <= 1.0


def test_evaluation_ranking_is_deterministic() -> None:
    now = datetime(2026, 9, 22, 12, 0, 0)

    memories = [
        create_memory(
            f"deployment execution result {index}",
            created_at=now,
        )
        for index in range(10)
    ]

    query = MemoryQuery(
        query="deployment execution result",
        limit=10,
    )

    retrieval = MemoryRetrieval()

    first = retrieval.retrieve(memories, query, now=now)
    second = retrieval.retrieve(memories, query, now=now)

    assert [result.memory.id for result in first] == [result.memory.id for result in second]

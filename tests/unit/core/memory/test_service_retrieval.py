from datetime import timedelta
from uuid import uuid4

from orion.core.memory.models import MemoryImportance, MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.retrieval import MemoryRetrieval
from orion.core.memory.retrieval_models import MemoryQuery
from orion.core.memory.service import MemoryService


def create_service() -> MemoryService:
    return MemoryService(InMemoryMemoryRepository())


def test_retrieve_returns_ranked_memory_results() -> None:
    service = create_service()

    service.remember(
        content="Python deployment architecture.",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH,
    )
    lower = service.remember(
        content="Unrelated database note.",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.LOW,
    )

    results = service.retrieve(
        MemoryQuery(
            query="Python deployment architecture",
            limit=10,
        )
    )

    assert len(results) == 2
    assert results[0].memory.content == "Python deployment architecture."
    assert results[0].score >= results[1].score
    assert results[0].memory.access_count == 1
    assert lower.access_count == 1


def test_retrieve_applies_query_filters() -> None:
    service = create_service()
    task_id = uuid4()

    matching = service.remember(
        content="Task-specific deployment knowledge.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.HIGH,
        task_id=task_id,
    )
    service.remember(
        content="Other task deployment knowledge.",
        memory_type=MemoryType.EPISODIC,
        importance=MemoryImportance.HIGH,
        task_id=uuid4(),
    )

    results = service.retrieve(
        MemoryQuery(
            query="deployment knowledge",
            task_id=task_id,
            memory_types=frozenset({MemoryType.EPISODIC}),
            minimum_importance=MemoryImportance.HIGH,
        )
    )

    assert [result.memory for result in results] == [matching]
    assert matching.access_count == 1


def test_retrieve_forwards_reference_time() -> None:
    service = create_service()

    recent = service.remember(
        content="Recent model result.",
        memory_type=MemoryType.EPISODIC,
    )

    reference_time = recent.created_at + timedelta(days=2)

    results = service.retrieve(
        MemoryQuery(
            query="model result",
            max_age=timedelta(days=3),
        ),
        now=reference_time,
    )

    assert [result.memory for result in results] == [recent]


def test_retrieve_empty_repository_returns_empty_list() -> None:
    service = create_service()

    results = service.retrieve(
        MemoryQuery(query="anything", limit=5)
    )

    assert results == []


def test_retrieve_marks_only_returned_memories_as_accessed() -> None:
    service = create_service()

    matching = service.remember(
        content="Relevant ORION execution memory.",
        memory_type=MemoryType.EPISODIC,
    )
    excluded = service.remember(
        content="Completely unrelated information.",
        memory_type=MemoryType.LONG_TERM,
    )

    results = service.retrieve(
        MemoryQuery(
            query="ORION execution",
            limit=1,
        )
    )

    assert len(results) == 1
    assert results[0].memory is matching
    assert matching.access_count == 1
    assert excluded.access_count == 0


def test_custom_retrieval_engine_can_be_injected() -> None:
    repository = InMemoryMemoryRepository()
    retrieval = MemoryRetrieval()
    service = MemoryService(repository, retrieval=retrieval)

    memory = service.remember(
        content="Injected retrieval engine.",
        memory_type=MemoryType.LONG_TERM,
    )

    results = service.retrieve(
        MemoryQuery(query="Injected retrieval engine")
    )

    assert len(results) == 1
    assert results[0].memory is memory

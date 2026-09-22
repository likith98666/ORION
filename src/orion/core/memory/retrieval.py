from datetime import datetime

from orion.core.memory.models import MemoryImportance, MemoryRecord
from orion.core.memory.retrieval_models import (
    ExecutionMemoryQuery,
    MemoryQuery,
    MemoryRetrievalResult,
)


class MemoryRetrieval:
    """Deterministic retrieval and ranking engine for ORION memory."""

    _IMPORTANCE_SCORE = {
        MemoryImportance.LOW: 0.25,
        MemoryImportance.MEDIUM: 0.5,
        MemoryImportance.HIGH: 1.0,
    }

    def retrieve(
        self,
        memories: list[MemoryRecord],
        query: MemoryQuery,
        *,
        now: datetime | None = None,
    ) -> list[MemoryRetrievalResult]:
        """Filter, score, rank, and return the most relevant memories."""

        reference_time = now or datetime.now()

        candidates = [
            memory
            for memory in memories
            if self._matches_filters(memory, query, reference_time)
        ]

        results = [
            self._score_memory(memory, query, reference_time)
            for memory in candidates
        ]

        return self._rank_results(results, query.limit)

    def retrieve_for_execution(
        self,
        memories: list[MemoryRecord],
        query: ExecutionMemoryQuery,
        *,
        now: datetime | None = None,
    ) -> list[MemoryRetrievalResult]:
        """Retrieve memories suitable for an agent execution context.

        Task and agent identifiers are treated as ranking context rather
        than hard filters. Other query constraints remain hard filters.
        """

        reference_time = now or datetime.now()

        candidates = [
            memory
            for memory in memories
            if self._matches_execution_filters(
                memory,
                query,
                reference_time,
            )
        ]

        results = [
            self._score_execution_memory(
                memory,
                query,
                reference_time,
            )
            for memory in candidates
        ]

        return self._rank_results(results, query.limit)

    def _matches_filters(
        self,
        memory: MemoryRecord,
        query: MemoryQuery,
        now: datetime,
    ) -> bool:
        if query.task_id is not None and memory.task_id != query.task_id:
            return False

        if query.agent_id is not None and memory.agent_id != query.agent_id:
            return False

        return self._matches_common_filters(memory, query, now)

    def _matches_execution_filters(
        self,
        memory: MemoryRecord,
        query: ExecutionMemoryQuery,
        now: datetime,
    ) -> bool:
        if not self._has_query_relevance(memory, query.query):
            return False

        return self._matches_common_filters(memory, query, now)

    def _matches_common_filters(
        self,
        memory: MemoryRecord,
        query: MemoryQuery | ExecutionMemoryQuery,
        now: datetime,
    ) -> bool:
        if query.memory_types and memory.memory_type not in query.memory_types:
            return False

        if (
            query.minimum_importance is not None
            and not self._importance_meets_minimum(
                memory.importance,
                query.minimum_importance,
            )
        ):
            return False

        if query.created_after is not None and memory.created_at < query.created_after:
            return False

        if query.created_before is not None and memory.created_at > query.created_before:
            return False

        if query.max_age is not None:
            if now - memory.created_at > query.max_age:
                return False

        return True

    def _score_memory(
        self,
        memory: MemoryRecord,
        query: MemoryQuery,
        now: datetime,
    ) -> MemoryRetrievalResult:
        return self._score_with_scope(
            memory,
            query,
            now,
        )

    def _score_execution_memory(
        self,
        memory: MemoryRecord,
        query: ExecutionMemoryQuery,
        now: datetime,
    ) -> MemoryRetrievalResult:
        return self._score_with_scope(
            memory,
            query,
            now,
        )

    def _score_with_scope(
        self,
        memory: MemoryRecord,
        query: MemoryQuery | ExecutionMemoryQuery,
        now: datetime,
    ) -> MemoryRetrievalResult:
        reasons: list[str] = []

        query_terms = set(query.query.lower().split())
        content_terms = set(memory.content.lower().split())

        overlap = query_terms & content_terms
        relevance = (
            len(overlap) / len(query_terms)
            if query_terms
            else 0.0
        )

        if relevance > 0:
            reasons.append("query_relevance")

        importance = self._IMPORTANCE_SCORE[memory.importance]

        if memory.importance == MemoryImportance.HIGH:
            reasons.append("high_importance")
        elif memory.importance == MemoryImportance.MEDIUM:
            reasons.append("medium_importance")

        age_seconds = max(
            0.0,
            (now - memory.created_at).total_seconds(),
        )

        recency = 1.0 / (1.0 + age_seconds / 86_400.0)

        if recency >= 0.5:
            reasons.append("recent")

        usefulness = min(memory.access_count / 10.0, 1.0)

        if memory.access_count > 0:
            reasons.append("previously_accessed")

        scope_bonus = 0.0

        if query.task_id is not None and memory.task_id == query.task_id:
            scope_bonus += 0.15
            reasons.append("task_scope_match")

        if query.agent_id is not None and memory.agent_id == query.agent_id:
            scope_bonus += 0.10
            reasons.append("agent_scope_match")

        score = min(
            1.0,
            (
                relevance * 0.45
                + importance * 0.25
                + recency * 0.15
                + usefulness * 0.05
                + scope_bonus
            ),
        )

        return MemoryRetrievalResult(
            memory=memory,
            score=score,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _has_query_relevance(
        memory: MemoryRecord,
        query: str,
    ) -> bool:
        query_terms = set(query.lower().split())
        content_terms = set(memory.content.lower().split())

        return bool(query_terms & content_terms)

    def _rank_results(
        self,
        results: list[MemoryRetrievalResult],
        limit: int,
    ) -> list[MemoryRetrievalResult]:
        results.sort(
            key=lambda result: (
                -result.score,
                -self._IMPORTANCE_SCORE[result.memory.importance],
                -result.memory.access_count,
                -result.memory.created_at.timestamp(),
                str(result.memory.id),
            )
        )

        return results[:limit]

    @staticmethod
    def _importance_meets_minimum(
        actual: MemoryImportance,
        minimum: MemoryImportance,
    ) -> bool:
        order = {
            MemoryImportance.LOW: 0,
            MemoryImportance.MEDIUM: 1,
            MemoryImportance.HIGH: 2,
        }

        return order[actual] >= order[minimum]

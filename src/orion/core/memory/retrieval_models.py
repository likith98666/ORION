from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from orion.core.memory.models import MemoryImportance, MemoryRecord, MemoryType


@dataclass(frozen=True)
class MemoryQuery:
    """Constraints and context used when retrieving ORION memories."""

    query: str
    task_id: UUID | None = None
    agent_id: UUID | None = None
    memory_types: frozenset[MemoryType] = frozenset()
    minimum_importance: MemoryImportance | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    max_age: timedelta | None = None
    limit: int = 5

    def __post_init__(self) -> None:
        cleaned_query = self.query.strip()

        if not cleaned_query:
            raise ValueError("Memory query cannot be empty.")

        if len(cleaned_query) > 5_000:
            raise ValueError(
                "Memory query cannot exceed 5,000 characters."
            )

        if self.limit < 1:
            raise ValueError("Memory query limit must be at least 1.")

        if self.limit > 100:
            raise ValueError("Memory query limit cannot exceed 100.")

        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError(
                "created_after cannot be later than created_before."
            )

        if self.max_age is not None and self.max_age < timedelta(0):
            raise ValueError("Memory query max_age cannot be negative.")

        object.__setattr__(self, "query", cleaned_query)
        object.__setattr__(
            self,
            "memory_types",
            frozenset(self.memory_types),
        )


@dataclass(frozen=True)
class ExecutionMemoryQuery:
    """Retrieval constraints plus execution scope used for ranking."""

    query: str
    task_id: UUID | None = None
    agent_id: UUID | None = None
    memory_types: frozenset[MemoryType] = frozenset()
    minimum_importance: MemoryImportance | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    max_age: timedelta | None = None
    limit: int = 5

    def __post_init__(self) -> None:
        cleaned_query = self.query.strip()

        if not cleaned_query:
            raise ValueError("Execution memory query cannot be empty.")

        if len(cleaned_query) > 5_000:
            raise ValueError(
                "Execution memory query cannot exceed 5,000 characters."
            )

        if self.limit < 1:
            raise ValueError(
                "Execution memory query limit must be at least 1."
            )

        if self.limit > 100:
            raise ValueError(
                "Execution memory query limit cannot exceed 100."
            )

        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError(
                "created_after cannot be later than created_before."
            )

        if self.max_age is not None and self.max_age < timedelta(0):
            raise ValueError(
                "Execution memory query max_age cannot be negative."
            )

        object.__setattr__(self, "query", cleaned_query)
        object.__setattr__(
            self,
            "memory_types",
            frozenset(self.memory_types),
        )


@dataclass(frozen=True)
class MemoryRetrievalResult:
    """A memory together with query-specific retrieval information."""

    memory: MemoryRecord
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.memory, MemoryRecord):
            raise TypeError("memory must be a MemoryRecord.")

        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Retrieval score must be between 0 and 1.")

        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("Retrieval reasons cannot contain empty values.")

        object.__setattr__(
            self,
            "reasons",
            tuple(self.reasons),
        )

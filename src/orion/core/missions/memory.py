"""Scoped, bounded, inspectable, and deletable Mission Memory for ORION V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MemoryEntryType(str, Enum):
    """Categorization of items retained in mission memory."""

    DECISION = "decision"
    ATTEMPT = "attempt"
    FAILURE = "failure"
    PATCH = "patch"
    TEST_RESULT = "test_result"
    APPROVAL = "approval"
    CONSTRAINT = "constraint"
    OBSERVATION = "observation"


@dataclass(frozen=True)
class MemoryEntry:
    """An immutable record inside mission memory."""

    entry_id: UUID
    mission_id: UUID
    entry_type: MemoryEntryType
    title: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    task_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "entry_id": str(self.entry_id),
            "mission_id": str(self.mission_id),
            "entry_type": self.entry_type.value,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "task_id": str(self.task_id) if self.task_id else None,
            "metadata": dict(self.metadata),
        }


class MissionMemory:
    """Bounded, inspectable, and scoped memory repository for an individual mission."""

    def __init__(self, mission_id: UUID, max_entries: int = 1000) -> None:
        if not isinstance(mission_id, UUID):
            raise TypeError("mission_id must be a UUID instance.")
        if max_entries <= 0:
            raise ValueError("max_entries must be a positive integer.")

        self.mission_id = mission_id
        self.max_entries = max_entries
        self._entries: list[MemoryEntry] = []
        self._entry_index: dict[UUID, MemoryEntry] = {}

    def record(
        self,
        entry_type: MemoryEntryType,
        title: str,
        content: str,
        task_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Record an entry into memory with FIFO eviction if bounded limit is exceeded."""
        if not title.strip():
            raise ValueError("Memory entry title cannot be empty.")

        entry = MemoryEntry(
            entry_id=uuid4(),
            mission_id=self.mission_id,
            entry_type=entry_type,
            title=title,
            content=content,
            task_id=task_id,
            metadata=dict(metadata or {}),
        )

        # Evict oldest entry if capacity reached
        if len(self._entries) >= self.max_entries:
            oldest = self._entries.pop(0)
            self._entry_index.pop(oldest.entry_id, None)

        self._entries.append(entry)
        self._entry_index[entry.entry_id] = entry
        return entry

    def record_decision(
        self, title: str, rationale: str, task_id: UUID | None = None, **kwargs: Any
    ) -> MemoryEntry:
        """Convenience helper to record an architectural or execution decision."""
        return self.record(
            entry_type=MemoryEntryType.DECISION,
            title=title,
            content=rationale,
            task_id=task_id,
            metadata=kwargs,
        )

    def record_failure(
        self, title: str, details: str, task_id: UUID | None = None, **kwargs: Any
    ) -> MemoryEntry:
        """Convenience helper to record a diagnostic or execution failure."""
        return self.record(
            entry_type=MemoryEntryType.FAILURE,
            title=title,
            content=details,
            task_id=task_id,
            metadata=kwargs,
        )

    def record_constraint(
        self, constraint_name: str, rule: str, task_id: UUID | None = None, **kwargs: Any
    ) -> MemoryEntry:
        """Convenience helper to record an operational or user constraint."""
        return self.record(
            entry_type=MemoryEntryType.CONSTRAINT,
            title=constraint_name,
            content=rule,
            task_id=task_id,
            metadata=kwargs,
        )

    def get_entries(
        self,
        entry_type: MemoryEntryType | None = None,
        task_id: UUID | None = None,
        limit: int | None = None,
    ) -> list[MemoryEntry]:
        """Query entries filtered by type or task ID."""
        filtered = self._entries

        if entry_type is not None:
            filtered = [e for e in filtered if e.entry_type == entry_type]

        if task_id is not None:
            filtered = [e for e in filtered if e.task_id == task_id]

        if limit is not None and limit > 0:
            return filtered[-limit:]

        return list(filtered)

    def search(self, query: str) -> list[MemoryEntry]:
        """Search entries for occurrences of query in title, content, or metadata values."""
        q_lower = query.lower()
        results: list[MemoryEntry] = []
        for entry in self._entries:
            if (
                q_lower in entry.title.lower()
                or q_lower in entry.content.lower()
                or any(q_lower in str(v).lower() for v in entry.metadata.values())
            ):
                results.append(entry)
        return results

    def delete_entry(self, entry_id: UUID) -> bool:
        """Explicitly delete a specific memory entry."""
        if entry_id not in self._entry_index:
            return False

        entry = self._entry_index.pop(entry_id)
        self._entries.remove(entry)
        return True

    def clear(self) -> int:
        """Clear all entries from mission memory and return the number deleted."""
        count = len(self._entries)
        self._entries.clear()
        self._entry_index.clear()
        return count

    def to_dict(self) -> dict[str, Any]:
        """Export serialized representation of mission memory."""
        return {
            "mission_id": str(self.mission_id),
            "max_entries": self.max_entries,
            "total_entries": len(self._entries),
            "entries": [e.to_dict() for e in self._entries],
        }

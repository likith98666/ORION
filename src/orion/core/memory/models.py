from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MemoryType(str, Enum):
    """Categories of memory retained by ORION."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"


class MemoryImportance(str, Enum):
    """Importance levels used when managing retained memory."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class MemoryRecord:
    """A durable piece of information available to ORION agents."""

    id: UUID
    memory_type: MemoryType
    content: str
    importance: MemoryImportance
    created_at: datetime
    task_id: UUID | None = None
    agent_id: UUID | None = None
    source_execution_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        content: str,
        memory_type: MemoryType,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        task_id: UUID | None = None,
        agent_id: UUID | None = None,
        source_execution_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MemoryRecord":
        cleaned_content = content.strip()

        if not cleaned_content:
            raise ValueError("Memory content cannot be empty.")

        if len(cleaned_content) > 20_000:
            raise ValueError(
                "Memory content cannot exceed 20,000 characters."
            )

        return cls(
            id=uuid4(),
            memory_type=memory_type,
            content=cleaned_content,
            importance=importance,
            created_at=datetime.now(),
            task_id=task_id,
            agent_id=agent_id,
            source_execution_id=source_execution_id,
            metadata=dict(metadata) if metadata is not None else {},
        )

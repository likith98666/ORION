from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class TaskEventType(str, Enum):
    TASK_CREATED = "task_created"
    STATUS_CHANGED = "status_changed"
    TASK_FAILED = "task_failed"


@dataclass(frozen=True)
class TaskEvent:
    id: UUID
    task_id: UUID
    event_type: TaskEventType
    timestamp: datetime
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task_id: UUID,
        event_type: TaskEventType,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> "TaskEvent":
        cleaned_message = message.strip()

        if not cleaned_message:
            raise ValueError("Event message cannot be empty.")

        return cls(
            id=uuid4(),
            task_id=task_id,
            event_type=event_type,
            timestamp=datetime.now(),
            message=cleaned_message,
            metadata=dict(metadata) if metadata is not None else {},
        )
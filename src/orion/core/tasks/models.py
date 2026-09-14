from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: UUID
    objective: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt_count: int = 0
    last_error: str | None = None

    @classmethod
    def create(cls, objective: str) -> "Task":
        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Task objective cannot be empty.")

        if len(cleaned_objective) > 10_000:
            raise ValueError("Task objective cannot exceed 10,000 characters.")

        return cls(
            id=uuid4(),
            objective=cleaned_objective,
            status=TaskStatus.CREATED,
            created_at=datetime.now(),
        )
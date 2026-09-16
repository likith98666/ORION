from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from orion.core.recovery.failures import Failure


class AgentExecutionStatus(str, Enum):
    """Lifecycle status of an ORION agent execution attempt."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentExecution:
    """Represents one execution attempt of an ORION agent task."""

    id: UUID
    agent_task_id: UUID
    agent_id: UUID
    status: AgentExecutionStatus = AgentExecutionStatus.RUNNING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    output: str | None = None
    error_message: str | None = None
    failure: Failure | None = None
    model_name: str | None = None
    provider_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None

    @classmethod
    def create(
        cls,
        agent_task_id: UUID,
        agent_id: UUID,
    ) -> "AgentExecution":
        """Create a new agent execution attempt."""

        return cls(
            id=uuid4(),
            agent_task_id=agent_task_id,
            agent_id=agent_id,
        )

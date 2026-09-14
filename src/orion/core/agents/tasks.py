from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability


class AgentTaskStatus(str, Enum):
    """Lifecycle status of an agent task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """Represents a subtask assigned to an ORION agent."""

    id: UUID
    task_id: UUID
    description: str
    required_capability: AgentCapability
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    assigned_agent_id: UUID | None = None

    @classmethod
    def create(
        cls,
        task_id: UUID,
        description: str,
        required_capability: AgentCapability,
    ) -> "AgentTask":
        """Create a validated agent task."""

        cleaned_description = description.strip()

        if not cleaned_description:
            raise ValueError("Agent task description cannot be empty.")

        if len(cleaned_description) > 5_000:
            raise ValueError(
                "Agent task description cannot exceed 5,000 characters."
            )

        return cls(
            id=uuid4(),
            task_id=task_id,
            description=cleaned_description,
            required_capability=required_capability,
        )
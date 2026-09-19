from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ToolExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolExecution:
    """Lifecycle record for one ORION tool execution."""

    id: UUID
    tool_name: str
    agent_id: UUID
    execution_id: UUID | None
    arguments: dict[str, Any]
    status: ToolExecutionStatus = ToolExecutionStatus.PENDING
    output: Any = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        tool_name: str,
        agent_id: UUID,
        arguments: dict[str, Any],
        execution_id: UUID | None = None,
    ) -> "ToolExecution":
        cleaned_name = tool_name.strip()

        if not cleaned_name:
            raise ValueError("Tool execution name cannot be empty.")

        return cls(
            id=uuid4(),
            tool_name=cleaned_name,
            agent_id=agent_id,
            execution_id=execution_id,
            arguments=dict(arguments),
        )

from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.agents.executions import AgentExecution


class AgentExecutionRepository(ABC):
    """Abstract repository for storing ORION agent executions."""

    @abstractmethod
    def save(self, execution: AgentExecution) -> None:
        """Save an agent execution."""

    @abstractmethod
    def get(self, execution_id: UUID) -> AgentExecution | None:
        """Get an agent execution by ID."""

    @abstractmethod
    def delete(self, execution_id: UUID) -> None:
        """Delete an agent execution."""

    @abstractmethod
    def list_for_agent_task(
        self,
        agent_task_id: UUID,
    ) -> list[AgentExecution]:
        """List all executions for an agent task."""

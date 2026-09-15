from uuid import UUID

from orion.core.agents.execution_repository import AgentExecutionRepository
from orion.core.agents.executions import AgentExecution


class InMemoryAgentExecutionRepository(AgentExecutionRepository):
    """In-memory repository for ORION agent executions."""

    def __init__(self) -> None:
        self._executions: dict[UUID, AgentExecution] = {}

    def save(self, execution: AgentExecution) -> None:
        """Save an agent execution."""
        self._executions[execution.id] = execution

    def get(self, execution_id: UUID) -> AgentExecution | None:
        """Get an agent execution by ID."""
        return self._executions.get(execution_id)

    def delete(self, execution_id: UUID) -> None:
        """Delete an agent execution."""
        self._executions.pop(execution_id, None)

    def list_for_agent_task(
        self,
        agent_task_id: UUID,
    ) -> list[AgentExecution]:
        """List all executions for an agent task."""
        return [
            execution
            for execution in self._executions.values()
            if execution.agent_task_id == agent_task_id
        ]

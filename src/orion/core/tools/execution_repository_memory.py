from uuid import UUID

from orion.core.tools.execution_repository import ToolExecutionRepository
from orion.core.tools.executions import ToolExecution


class InMemoryToolExecutionRepository(ToolExecutionRepository):
    """In-memory tool execution persistence."""

    def __init__(self) -> None:
        self._executions: dict[UUID, ToolExecution] = {}

    def save(self, execution: ToolExecution) -> None:
        self._executions[execution.id] = execution

    def get(self, execution_id: UUID) -> ToolExecution | None:
        return self._executions.get(execution_id)

    def list_for_agent(self, agent_id: UUID) -> list[ToolExecution]:
        return [
            execution
            for execution in self._executions.values()
            if execution.agent_id == agent_id
        ]

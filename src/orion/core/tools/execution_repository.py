from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.tools.executions import ToolExecution


class ToolExecutionRepository(ABC):
    """Persistence boundary for tool execution lifecycle records."""

    @abstractmethod
    def save(self, execution: ToolExecution) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, execution_id: UUID) -> ToolExecution | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_agent(self, agent_id: UUID) -> list[ToolExecution]:
        raise NotImplementedError

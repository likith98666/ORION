from abc import ABC, abstractmethod

from orion.core.tools.definition import ToolDefinition


class ToolRegistry(ABC):
    """Abstract registry for discovering ORION tools."""

    @abstractmethod
    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        raise NotImplementedError

    @abstractmethod
    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool by name."""
        raise NotImplementedError

    @abstractmethod
    def list_tools(self) -> tuple[ToolDefinition, ...]:
        """List all registered tools."""
        raise NotImplementedError

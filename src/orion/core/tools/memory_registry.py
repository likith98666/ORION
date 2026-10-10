from orion.core.tools.definition import ToolDefinition
from orion.core.tools.registry import ToolRegistry


class InMemoryToolRegistry(ToolRegistry):
    """In-memory tool registry for the ORION runtime."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        name = tool.name.strip()

        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered.")

        self._tools[name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name.strip())

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

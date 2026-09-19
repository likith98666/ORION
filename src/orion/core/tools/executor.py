from dataclasses import dataclass
from typing import Any
from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result of executing a registered ORION tool."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None


class ToolExecutor:
    """Executes registered tools after validating agent permissions."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(
        self,
        agent: Agent,
        tool_name: str,
        arguments: dict[str, Any],
        execution_id: UUID | None = None,
    ) -> ToolExecutionResult:
        """Execute a tool for an authorized agent."""

        tool = self._registry.get(tool_name)

        if tool is None:
            raise ValueError(f"Tool '{tool_name}' was not found.")

        if not agent.permission_policy.allows(tool.permission):
            raise PermissionError(
                f"Agent '{agent.name}' is not authorized to use "
                f"tool '{tool.name}'."
            )

        try:
            output = tool.handler(arguments)
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=tool.name,
                success=False,
                error=str(exc),
            )

        return ToolExecutionResult(
            tool_name=tool.name,
            success=True,
            output=output,
        )

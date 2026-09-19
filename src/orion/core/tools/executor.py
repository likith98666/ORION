from dataclasses import dataclass
from typing import Any
from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.tools.execution_repository import ToolExecutionRepository
from orion.core.tools.executions import ToolExecution, ToolExecutionStatus
from orion.core.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result of executing a registered ORION tool."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    execution_id: UUID | None = None


class ToolExecutor:
    """Executes registered tools with lifecycle persistence and authorization."""

    def __init__(
        self,
        registry: ToolRegistry,
        execution_repository: ToolExecutionRepository | None = None,
    ) -> None:
        self._registry = registry
        self._execution_repository = execution_repository

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

        lifecycle = None

        if self._execution_repository is not None:
            lifecycle = ToolExecution.create(
                tool_name=tool.name,
                agent_id=agent.id,
                arguments=arguments,
                execution_id=execution_id,
            )

            self._execution_repository.save(lifecycle)

            lifecycle.status = ToolExecutionStatus.RUNNING
            self._execution_repository.save(lifecycle)

        try:
            output = tool.handler(arguments)

        except Exception as exc:
            if lifecycle is not None:
                lifecycle.status = ToolExecutionStatus.FAILED
                lifecycle.error = str(exc)
                self._execution_repository.save(lifecycle)

            return ToolExecutionResult(
                tool_name=tool.name,
                success=False,
                error=str(exc),
                execution_id=lifecycle.id if lifecycle else None,
            )

        if lifecycle is not None:
            lifecycle.status = ToolExecutionStatus.COMPLETED
            lifecycle.output = output
            self._execution_repository.save(lifecycle)

        return ToolExecutionResult(
            tool_name=tool.name,
            success=True,
            output=output,
            execution_id=lifecycle.id if lifecycle else None,
        )

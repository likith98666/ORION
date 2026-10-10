from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from orion.core.agents.permissions import AgentPermission
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.input_schema import ToolInputSchema


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable metadata and callable implementation for an ORION tool."""

    name: str
    description: str
    permission: AgentPermission
    handler: Callable[[dict[str, Any]], Any]
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    input_schema: ToolInputSchema | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool name cannot be empty.")

        if not self.description.strip():
            raise ValueError("Tool description cannot be empty.")

        if not isinstance(self.risk_level, ToolRiskLevel):
            raise TypeError("Tool risk level must be a ToolRiskLevel.")

        if not isinstance(self.permission, AgentPermission):
            raise TypeError("Tool permission must be an AgentPermission.")

        if not callable(self.handler):
            raise TypeError("Tool handler must be callable.")

        if self.input_schema is not None and not isinstance(
            self.input_schema,
            ToolInputSchema,
        ):
            raise TypeError("Tool input schema must be a ToolInputSchema.")

from dataclasses import dataclass
from typing import Any, Callable

from orion.core.agents.permissions import AgentPermission


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable metadata and callable implementation for an ORION tool."""

    name: str
    description: str
    permission: AgentPermission
    handler: Callable[[dict[str, Any]], Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool name cannot be empty.")

        if not self.description.strip():
            raise ValueError("Tool description cannot be empty.")

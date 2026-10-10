from typing import Any

from orion.core.workspace.models import Workspace


def get_effective_workspace(
    bound_workspace: Workspace | None,
    arguments: dict[str, Any],
) -> Workspace:
    """Retrieve the effective Workspace instance from arguments or closure binding."""
    ws = arguments.get("workspace") or bound_workspace
    if ws is None:
        raise ValueError("No Workspace was provided or bound for repository tool execution.")
    if not isinstance(ws, Workspace):
        raise TypeError(f"Expected Workspace instance, got {type(ws).__name__}.")
    return ws

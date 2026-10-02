from orion.core.tools.definition import ToolDefinition
from orion.core.tools.registry import ToolRegistry
from orion.core.tools.repository.read_tools import (
    build_list_files_tool,
    build_read_file_tool,
    build_search_files_tool,
)
from orion.core.tools.repository.validation_tools import (
    build_run_lint_tool,
    build_run_tests_tool,
    build_run_typecheck_tool,
)
from orion.core.tools.repository.write_tools import (
    build_apply_change_tool,
    build_diff_tool,
    build_write_file_tool,
)
from orion.core.workspace.models import Workspace


def create_repository_tools(workspace: Workspace | None = None) -> list[ToolDefinition]:
    """Create all standard repository tools, optionally bound to a Workspace."""
    return [
        build_list_files_tool(workspace),
        build_read_file_tool(workspace),
        build_search_files_tool(workspace),
        build_diff_tool(workspace),
        build_write_file_tool(workspace),
        build_apply_change_tool(workspace),
        build_run_tests_tool(workspace),
        build_run_lint_tool(workspace),
        build_run_typecheck_tool(workspace),
    ]


def register_repository_tools(
    registry: ToolRegistry,
    workspace: Workspace | None = None,
) -> None:
    """Register all repository tools into an existing ToolRegistry."""
    for tool in create_repository_tools(workspace):
        registry.register(tool)

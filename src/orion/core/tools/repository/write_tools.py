import difflib
import hashlib
from typing import Any

from orion.core.agents.permissions import AgentPermission
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.repository.common import get_effective_workspace
from orion.core.tools.repository.errors import StaleStateError
from orion.core.tools.repository.models import (
    ApplyChangeResult,
    DiffResult,
    WriteFileResult,
)
from orion.core.tools.repository.security import assert_not_protected
from orion.core.workspace.models import Workspace

MAX_WRITE_CONTENT_SIZE = 524288  # 512 KB
DEFAULT_MAX_DIFF_LINES = 500
MAX_DIFF_LINES_LIMIT = 2000


def build_write_file_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the write_file ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=True,
            ),
            ToolInputField(
                name="content",
                input_type=ToolInputType.STRING,
                required=True,
                max_length=MAX_WRITE_CONTENT_SIZE,
            ),
            ToolInputField(
                name="create_parents",
                input_type=ToolInputType.BOOLEAN,
                required=False,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
        max_string_length=MAX_WRITE_CONTENT_SIZE,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        path_str = arguments["path"]
        content = arguments["content"]
        create_parents = bool(arguments.get("create_parents", False))

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_CONTENT_SIZE:
            raise ValueError(
                f"Content size ({len(encoded)} bytes) exceeds maximum limit ({MAX_WRITE_CONTENT_SIZE} bytes)."
            )

        target_file = ws.validate_path(path_str)
        assert_not_protected(target_file)

        if target_file.exists() and target_file.is_dir():
            raise IsADirectoryError(f"Target path is an existing directory: '{path_str}'")

        parent = target_file.parent
        # Validate parent directory remains strictly within workspace boundary
        ws.validate_path(parent)

        if not parent.exists():
            if not create_parents:
                raise FileNotFoundError(
                    f"Parent directory does not exist: '{parent}'. Set create_parents=True to create it."
                )
            parent.mkdir(parents=True, exist_ok=True)

        created = not target_file.exists()
        target_file.write_text(content, encoding="utf-8")
        checksum = hashlib.sha256(encoded).hexdigest()

        return WriteFileResult(
            path=str(ws.relative_path(target_file)),
            bytes_written=len(encoded),
            created=created,
            checksum=checksum,
        ).to_dict()

    return ToolDefinition(
        name="write_file",
        description="Write text content to a repository file within the workspace boundary with strict size limits and parent validation.",
        permission=AgentPermission.WRITE_FILES,
        risk_level=ToolRiskLevel.HIGH,
        input_schema=schema,
        handler=handler,
    )


def build_apply_change_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the apply_change ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=True,
            ),
            ToolInputField(
                name="new_content",
                input_type=ToolInputType.STRING,
                required=True,
                max_length=MAX_WRITE_CONTENT_SIZE,
            ),
            ToolInputField(
                name="expected_content",
                input_type=ToolInputType.STRING,
                required=False,
                nullable=True,
                max_length=MAX_WRITE_CONTENT_SIZE,
            ),
            ToolInputField(
                name="expected_hash",
                input_type=ToolInputType.STRING,
                required=False,
                nullable=True,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
        max_string_length=MAX_WRITE_CONTENT_SIZE,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        path_str = arguments["path"]
        new_content = arguments["new_content"]
        expected_content = arguments.get("expected_content")
        expected_hash = arguments.get("expected_hash")

        encoded_new = new_content.encode("utf-8")
        if len(encoded_new) > MAX_WRITE_CONTENT_SIZE:
            raise ValueError(
                f"New content size ({len(encoded_new)} bytes) exceeds maximum limit ({MAX_WRITE_CONTENT_SIZE} bytes)."
            )

        target_file = ws.validate_path(path_str)
        assert_not_protected(target_file)

        if not target_file.exists():
            raise FileNotFoundError(f"File not found: '{path_str}'")

        if target_file.is_dir():
            raise IsADirectoryError(f"Target path is a directory, not a file: '{path_str}'")

        current_bytes = target_file.read_bytes()
        current_content = target_file.read_text(encoding="utf-8")
        raw_hash = hashlib.sha256(current_bytes).hexdigest()
        text_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
        current_hash = raw_hash

        # Optimistic concurrency / stale-state checks
        if expected_hash is not None and expected_hash.strip():
            target_hash = expected_hash.strip().lower()
            if target_hash != raw_hash.lower() and target_hash != text_hash.lower():
                raise StaleStateError(
                    f"Expected hash '{expected_hash}' does not match actual current hash '{raw_hash}'. "
                    "File has been modified concurrently."
                )

        if expected_content is not None:
            norm_curr = current_content.replace("\r\n", "\n")
            norm_exp = expected_content.replace("\r\n", "\n")
            if norm_curr != norm_exp:
                raise StaleStateError(
                    "Expected content does not match current file content. File has been modified concurrently."
                )

        # Compute diff summary
        curr_lines = current_content.splitlines()
        new_lines = new_content.splitlines()
        diff = list(
            difflib.unified_diff(
                curr_lines,
                new_lines,
                fromfile=f"a/{ws.relative_path(target_file)}",
                tofile=f"b/{ws.relative_path(target_file)}",
                lineterm="",
            )
        )
        lines_added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        diff_summary = "\n".join(diff[:100])

        target_file.write_text(new_content, encoding="utf-8", newline="\n")
        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

        return ApplyChangeResult(
            path=str(ws.relative_path(target_file)),
            previous_hash=current_hash,
            new_hash=new_hash,
            change_applied=True,
            lines_added=lines_added,
            lines_removed=lines_removed,
            diff_summary=diff_summary,
        ).to_dict()

    return ToolDefinition(
        name="apply_change",
        description="Structured SWE modification primitive with optimistic concurrency verification and evidence tracking.",
        permission=AgentPermission.WRITE_FILES,
        risk_level=ToolRiskLevel.HIGH,
        input_schema=schema,
        handler=handler,
    )


def build_diff_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the diff ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=True,
            ),
            ToolInputField(
                name="comparison_content",
                input_type=ToolInputType.STRING,
                required=False,
                nullable=True,
                max_length=MAX_WRITE_CONTENT_SIZE,
            ),
            ToolInputField(
                name="comparison_path",
                input_type=ToolInputType.STRING,
                required=False,
                nullable=True,
            ),
            ToolInputField(
                name="max_diff_lines",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
        max_string_length=MAX_WRITE_CONTENT_SIZE,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        path_str = arguments["path"]
        comparison_content = arguments.get("comparison_content")
        comparison_path = arguments.get("comparison_path")

        if comparison_content is None and comparison_path is None:
            raise ValueError("Either 'comparison_content' or 'comparison_path' must be provided.")

        target_file = ws.validate_path(path_str)
        assert_not_protected(target_file)

        if not target_file.exists():
            raise FileNotFoundError(f"File not found: '{path_str}'")

        if target_file.is_dir():
            raise IsADirectoryError(f"Target path is a directory: '{path_str}'")

        target_text = target_file.read_text(encoding="utf-8")
        max_diff_lines = min(int(arguments.get("max_diff_lines", DEFAULT_MAX_DIFF_LINES)), MAX_DIFF_LINES_LIMIT)

        if comparison_path is not None:
            comp_file = ws.validate_path(comparison_path)
            assert_not_protected(comp_file)
            if not comp_file.exists():
                raise FileNotFoundError(f"Comparison file not found: '{comparison_path}'")
            if comp_file.is_dir():
                raise IsADirectoryError(f"Comparison path is a directory: '{comparison_path}'")
            comp_text = comp_file.read_text(encoding="utf-8")
            from_label = str(ws.relative_path(target_file))
            to_label = str(ws.relative_path(comp_file))
        else:
            comp_text = comparison_content or ""
            from_label = str(ws.relative_path(target_file)) + " (current)"
            to_label = "comparison_content"

        diff_lines = list(
            difflib.unified_diff(
                target_text.splitlines(),
                comp_text.splitlines(),
                fromfile=from_label,
                tofile=to_label,
                lineterm="",
            )
        )

        lines_added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        identical = len(diff_lines) == 0

        truncated = False
        if len(diff_lines) > max_diff_lines:
            diff_lines = diff_lines[:max_diff_lines]
            truncated = True

        return DiffResult(
            path=str(ws.relative_path(target_file)),
            diff="\n".join(diff_lines),
            identical=identical,
            lines_added=lines_added,
            lines_removed=lines_removed,
            truncated=truncated,
        ).to_dict()

    return ToolDefinition(
        name="diff",
        description="Inspect deterministic text diffs between workspace files or contents without git or shell execution.",
        permission=AgentPermission.READ_FILES,
        risk_level=ToolRiskLevel.LOW,
        input_schema=schema,
        handler=handler,
    )

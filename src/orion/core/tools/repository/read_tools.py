import os
from pathlib import Path
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
from orion.core.tools.repository.models import (
    ListFilesResult,
    ReadFileResult,
    SearchFilesResult,
    SearchMatch,
)
from orion.core.tools.repository.security import (
    assert_not_protected,
    is_protected_path,
)
from orion.core.workspace.models import Workspace

MAX_SEARCH_RESULTS_LIMIT = 200
MAX_LIST_ENTRIES_LIMIT = 500
MAX_READ_FILE_SIZE = 1048576  # 1 MB
DEFAULT_MAX_BYTES = 262144  # 256 KB
IGNORED_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
})


def _is_binary_file(file_path: Path) -> bool:
    """Return True if the file contains null bytes or fails UTF-8 decoding."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if b"\0" in chunk:
                return True
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                return True
    except OSError:
        return True
    return False


def build_list_files_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the list_files ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=False,
            ),
            ToolInputField(
                name="recursive",
                input_type=ToolInputType.BOOLEAN,
                required=False,
            ),
            ToolInputField(
                name="max_depth",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="max_entries",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="include_hidden",
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
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        rel_path = arguments.get("path") or "."
        target_dir = ws.validate_path(rel_path)

        if not target_dir.is_dir():
            raise ValueError(f"Target path is not a directory: '{rel_path}'")

        recursive = bool(arguments.get("recursive", False))
        max_depth = min(int(arguments.get("max_depth", 2)), 5)
        max_entries = min(int(arguments.get("max_entries", 100)), MAX_LIST_ENTRIES_LIMIT)
        include_hidden = bool(arguments.get("include_hidden", False))

        entries: list[dict[str, Any]] = []
        truncated = False

        if not recursive:
            try:
                children = sorted(target_dir.iterdir(), key=lambda p: p.name.lower())
            except OSError as e:
                raise ValueError(f"Cannot list directory '{rel_path}': {e}") from e

            for child in children:
                if not include_hidden and child.name.startswith("."):
                    continue
                if is_protected_path(child):
                    continue
                if not ws.is_path_allowed(child):
                    continue

                is_dir = child.is_dir()
                size = None if is_dir else (child.stat().st_size if child.exists() else None)
                rel_to_root = str(ws.relative_path(child))

                entries.append({
                    "name": child.name,
                    "path": rel_to_root,
                    "is_dir": is_dir,
                    "size": size,
                })

                if len(entries) >= max_entries:
                    truncated = True
                    break
        else:
            # Controlled bounded recursive traversal
            base_level = len(target_dir.parts)
            for root, dirs, files in os.walk(target_dir):
                current_root = Path(root)
                current_level = len(current_root.parts) - base_level
                if current_level >= max_depth:
                    dirs.clear()
                    continue

                # Filter directories in-place to avoid traversing into ignored or protected dirs
                dirs[:] = [
                    d for d in dirs
                    if d not in IGNORED_DIRS
                    and (include_hidden or not d.startswith("."))
                    and not is_protected_path(current_root / d)
                    and ws.is_path_allowed(current_root / d)
                ]

                # Process subdirectories
                for d in dirs:
                    d_path = current_root / d
                    entries.append({
                        "name": d,
                        "path": str(ws.relative_path(d_path)),
                        "is_dir": True,
                        "size": None,
                    })
                    if len(entries) >= max_entries:
                        truncated = True
                        break
                if truncated:
                    break

                # Process files
                for f in files:
                    if not include_hidden and f.startswith("."):
                        continue
                    f_path = current_root / f
                    if is_protected_path(f_path):
                        continue
                    if not ws.is_path_allowed(f_path):
                        continue

                    size = f_path.stat().st_size if f_path.exists() else None
                    entries.append({
                        "name": f,
                        "path": str(ws.relative_path(f_path)),
                        "is_dir": False,
                        "size": size,
                    })
                    if len(entries) >= max_entries:
                        truncated = True
                        break
                if truncated:
                    break

        entries.sort(key=lambda e: e["path"])
        return ListFilesResult(
            path=str(ws.relative_path(target_dir)),
            entries=tuple(entries),
            total_count=len(entries),
            truncated=truncated,
        ).to_dict()

    return ToolDefinition(
        name="list_files",
        description=(
            "List files and directories within the workspace boundary with deterministic ordering "
            "and bounded output."
        ),
        permission=AgentPermission.READ_FILES,
        risk_level=ToolRiskLevel.LOW,
        input_schema=schema,
        handler=handler,
    )


def build_read_file_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the read_file ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=True,
            ),
            ToolInputField(
                name="max_bytes",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="max_lines",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="offset_lines",
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
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        path_str = arguments["path"]
        target_file = ws.validate_path(path_str)

        assert_not_protected(target_file)

        if not target_file.exists():
            raise FileNotFoundError(f"File not found: '{path_str}'")

        if target_file.is_dir():
            raise IsADirectoryError(f"Target path is a directory, not a file: '{path_str}'")

        file_size = target_file.stat().st_size
        if file_size > MAX_READ_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowable limit "
                f"({MAX_READ_FILE_SIZE} bytes)."
            )

        if _is_binary_file(target_file):
            raise ValueError(f"Cannot read binary or non-text file '{path_str}'.")

        max_bytes = min(int(arguments.get("max_bytes", DEFAULT_MAX_BYTES)), MAX_READ_FILE_SIZE)
        max_lines = arguments.get("max_lines")
        offset_lines = max(int(arguments.get("offset_lines", 0)), 0)

        with open(target_file, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        sliced_lines = all_lines[offset_lines:]

        truncated = False
        if max_lines is not None and max_lines >= 0:
            if len(sliced_lines) > max_lines:
                sliced_lines = sliced_lines[:max_lines]
                truncated = True

        content = "".join(sliced_lines)
        encoded_len = len(content.encode("utf-8"))
        if encoded_len > max_bytes:
            content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
            truncated = True

        return ReadFileResult(
            path=str(ws.relative_path(target_file)),
            content=content,
            size=file_size,
            total_lines=total_lines,
            lines_read=len(sliced_lines),
            truncated=truncated,
        ).to_dict()

    return ToolDefinition(
        name="read_file",
        description=(
            "Read UTF-8 text content from a repository file within the workspace boundary with "
            "size limits and binary protection."
        ),
        permission=AgentPermission.READ_FILES,
        risk_level=ToolRiskLevel.LOW,
        input_schema=schema,
        handler=handler,
    )


def build_search_files_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the search_files ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="query",
                input_type=ToolInputType.STRING,
                required=True,
            ),
            ToolInputField(
                name="path",
                input_type=ToolInputType.STRING,
                required=False,
            ),
            ToolInputField(
                name="max_results",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="case_sensitive",
                input_type=ToolInputType.BOOLEAN,
                required=False,
            ),
            ToolInputField(
                name="max_file_size",
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
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        query = arguments["query"]
        if not query:
            raise ValueError("Search query cannot be empty.")

        rel_path = arguments.get("path")
        if rel_path is not None and rel_path != ".":
            search_root = ws.validate_path(rel_path)
        else:
            search_root = ws.resolve_path(".")

        if not search_root.is_dir():
            raise ValueError(f"Search root must be a directory: '{rel_path}'")

        max_results = min(int(arguments.get("max_results", 50)), MAX_SEARCH_RESULTS_LIMIT)
        case_sensitive = bool(arguments.get("case_sensitive", False))
        max_file_size = min(
            int(arguments.get("max_file_size", DEFAULT_MAX_BYTES)), MAX_READ_FILE_SIZE
        )

        matches: list[dict[str, Any]] = []
        truncated = False
        target_query = query if case_sensitive else query.lower()

        for root, dirs, files in os.walk(search_root):
            current_root = Path(root)

            # Filter out ignored/protected directories
            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIRS
                and not d.startswith(".")
                and not is_protected_path(current_root / d)
                and ws.is_path_allowed(current_root / d)
            ]

            files_sorted = sorted(files)
            for f in files_sorted:
                if f.startswith("."):
                    continue
                file_path = current_root / f
                if is_protected_path(file_path):
                    continue
                if not ws.is_path_allowed(file_path):
                    continue

                try:
                    st = file_path.stat()
                    if st.st_size > max_file_size:
                        continue
                except OSError:
                    continue

                if _is_binary_file(file_path):
                    continue

                try:
                    with open(file_path, encoding="utf-8", errors="replace") as fh:
                        for line_idx, line in enumerate(fh, 1):
                            comp_line = line if case_sensitive else line.lower()
                            if target_query in comp_line:
                                matches.append(
                                    SearchMatch(
                                        file=str(ws.relative_path(file_path)),
                                        line_number=line_idx,
                                        line_content=line.strip()[:500],
                                    ).to_dict()
                                )
                                if len(matches) >= max_results:
                                    truncated = True
                                    break
                except OSError:
                    continue

                if truncated:
                    break
            if truncated:
                break

        matches.sort(key=lambda m: (m["file"], m["line_number"]))
        return SearchFilesResult(
            query=query,
            matches=tuple(matches),
            total_matches=len(matches),
            truncated=truncated,
        ).to_dict()

    return ToolDefinition(
        name="search_files",
        description=(
            "Search for text matches within workspace files bounded by size, allowed paths, and "
            "result limits."
        ),
        permission=AgentPermission.READ_FILES,
        risk_level=ToolRiskLevel.LOW,
        input_schema=schema,
        handler=handler,
    )

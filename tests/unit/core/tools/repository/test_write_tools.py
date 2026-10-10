import hashlib
from pathlib import Path

import pytest

from orion.core.tools.repository.errors import ProtectedPathError, StaleStateError
from orion.core.tools.repository.write_tools import (
    build_apply_change_tool,
    build_diff_tool,
    build_write_file_tool,
)
from orion.core.workspace.errors import PathNotAllowedError, PathOutsideWorkspaceError
from orion.core.workspace.models import Workspace


class TestWriteFileTool:
    """Tests for write_file repository tool."""

    def test_write_file_new_file(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)
        result = tool.handler({"path": "new_file.txt", "content": "Hello World"})

        assert result["created"] is True
        assert result["bytes_written"] == len(b"Hello World")
        assert (tmp_path / "new_file.txt").read_text(encoding="utf-8") == "Hello World"
        expected_hash = hashlib.sha256(b"Hello World").hexdigest()
        assert result["checksum"] == expected_hash

    def test_write_file_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "exist.txt"
        file.write_text("old", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)
        result = tool.handler({"path": "exist.txt", "content": "updated"})

        assert result["created"] is False
        assert file.read_text(encoding="utf-8") == "updated"

    def test_write_file_create_parents(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)
        result = tool.handler(
            {
                "path": "nested/dir/app.py",
                "content": "code",
                "create_parents": True,
            }
        )

        assert result["created"] is True
        assert (tmp_path / "nested" / "dir" / "app.py").read_text(encoding="utf-8") == "code"

    def test_write_file_missing_parents_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            tool.handler(
                {
                    "path": "missing/dir/app.py",
                    "content": "code",
                    "create_parents": False,
                }
            )

    def test_write_file_traversal_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": "../outside.txt", "content": "malicious"})

    def test_write_file_outside_workspace_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": str(outside), "content": "malicious"})

    def test_write_file_disallowed_path_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        ws = Workspace(repository_root=tmp_path, allowed_paths=["src"])
        tool = build_write_file_tool(ws)

        with pytest.raises(PathNotAllowedError):
            tool.handler({"path": "tests/test_new.py", "content": "test"})

    def test_write_file_protected_path_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)

        with pytest.raises(ProtectedPathError):
            tool.handler({"path": ".env", "content": "STOLEN=1"})

        with pytest.raises(ProtectedPathError):
            tool.handler({"path": "priv.key", "content": "key"})

    def test_write_file_size_limits(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)
        oversized = "a" * (524288 + 1)

        with pytest.raises(ValueError, match="exceeds maximum limit"):
            tool.handler({"path": "big.txt", "content": oversized})

    def test_write_file_directory_target_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "dir").mkdir()
        ws = Workspace(repository_root=tmp_path)
        tool = build_write_file_tool(ws)

        with pytest.raises(IsADirectoryError):
            tool.handler({"path": "dir", "content": "text"})


class TestApplyChangeTool:
    """Tests for apply_change repository tool."""

    def test_apply_change_valid(self, tmp_path: Path) -> None:
        file = tmp_path / "code.py"
        file.write_text("def hello():\n    return 1\n", encoding="utf-8")
        orig_hash = hashlib.sha256(file.read_bytes()).hexdigest()

        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)
        result = tool.handler(
            {
                "path": "code.py",
                "new_content": "def hello():\n    return 2\n",
                "expected_hash": orig_hash,
            }
        )

        assert result["change_applied"] is True
        assert result["previous_hash"] == orig_hash
        assert file.read_text(encoding="utf-8") == "def hello():\n    return 2\n"
        assert result["lines_added"] >= 1
        assert result["lines_removed"] >= 1

    def test_apply_change_stale_hash_rejected(self, tmp_path: Path) -> None:
        file = tmp_path / "code.py"
        file.write_text("v1", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)

        with pytest.raises(StaleStateError, match="Expected hash"):
            tool.handler(
                {
                    "path": "code.py",
                    "new_content": "v2",
                    "expected_hash": "deadbeef1234",
                }
            )

    def test_apply_change_stale_content_rejected(self, tmp_path: Path) -> None:
        file = tmp_path / "code.py"
        file.write_text("actual content", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)

        with pytest.raises(StaleStateError, match="Expected content does not match"):
            tool.handler(
                {
                    "path": "code.py",
                    "new_content": "new",
                    "expected_content": "stale content",
                }
            )

    def test_apply_change_nonexistent_file(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)

        with pytest.raises(FileNotFoundError):
            tool.handler(
                {
                    "path": "missing.py",
                    "new_content": "code",
                }
            )

    def test_apply_change_workspace_escape_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler(
                {
                    "path": "../outside.py",
                    "new_content": "code",
                }
            )

    def test_apply_change_protected_file_rejected(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("FOO=bar", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_apply_change_tool(ws)

        with pytest.raises(ProtectedPathError):
            tool.handler(
                {
                    "path": ".env",
                    "new_content": "FOO=baz",
                }
            )


class TestDiffTool:
    """Tests for diff repository tool."""

    def test_diff_identical_file(self, tmp_path: Path) -> None:
        file = tmp_path / "app.py"
        file.write_text("print('hello')\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_diff_tool(ws)
        result = tool.handler(
            {
                "path": "app.py",
                "comparison_content": "print('hello')\n",
            }
        )

        assert result["identical"] is True
        assert result["lines_added"] == 0
        assert result["lines_removed"] == 0
        assert result["diff"] == ""

    def test_diff_modified_content(self, tmp_path: Path) -> None:
        file = tmp_path / "app.py"
        file.write_text("line1\nline2\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_diff_tool(ws)
        result = tool.handler(
            {
                "path": "app.py",
                "comparison_content": "line1\nline2_modified\n",
            }
        )

        assert result["identical"] is False
        assert result["lines_added"] == 1
        assert result["lines_removed"] == 1
        assert "line2_modified" in result["diff"]

    def test_diff_between_two_workspace_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "file1.txt"
        f1.write_text("apple\nbanana\n", encoding="utf-8")
        f2 = tmp_path / "file2.txt"
        f2.write_text("apple\norange\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_diff_tool(ws)
        result = tool.handler(
            {
                "path": "file1.txt",
                "comparison_path": "file2.txt",
            }
        )

        assert result["identical"] is False
        assert result["lines_added"] == 1
        assert result["lines_removed"] == 1

    def test_diff_bounded_output(self, tmp_path: Path) -> None:
        file = tmp_path / "large_diff.txt"
        file.write_text("\n".join(f"old_{i}" for i in range(50)), encoding="utf-8")
        comp = "\n".join(f"new_{i}" for i in range(50))

        ws = Workspace(repository_root=tmp_path)
        tool = build_diff_tool(ws)
        result = tool.handler(
            {
                "path": "large_diff.txt",
                "comparison_content": comp,
                "max_diff_lines": 10,
            }
        )

        assert result["truncated"] is True
        diff_lines = result["diff"].splitlines()
        assert len(diff_lines) <= 10

    def test_diff_workspace_escape_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_diff_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler(
                {
                    "path": "../outside.txt",
                    "comparison_content": "test",
                }
            )

from pathlib import Path

import pytest

from orion.core.tools.repository.errors import ProtectedPathError
from orion.core.tools.repository.read_tools import (
    build_list_files_tool,
    build_read_file_tool,
    build_search_files_tool,
)
from orion.core.workspace.errors import PathNotAllowedError, PathOutsideWorkspaceError
from orion.core.workspace.models import Workspace


class TestListFilesTool:
    """Tests for list_files repository tool."""

    def test_list_files_valid_directory(self, tmp_path: Path) -> None:
        (tmp_path / "file1.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "file2.py").write_text("print(1)", encoding="utf-8")
        (tmp_path / "sub").mkdir()

        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)
        result = tool.handler({})

        assert result["total_count"] == 3
        names = [e["name"] for e in result["entries"]]
        assert "file1.txt" in names
        assert "file2.py" in names
        assert "sub" in names
        assert result["truncated"] is False

    def test_list_files_nested_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)
        (nested / "mod.py").write_text("x = 1", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)
        result = tool.handler({"path": "src/pkg"})

        assert result["total_count"] == 1
        assert result["entries"][0]["name"] == "mod.py"

    def test_list_files_recursive_bounded(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "a" / "b" / "file.txt").write_text("test", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)
        result = tool.handler({"recursive": True, "max_depth": 3})

        names = [e["name"] for e in result["entries"]]
        assert "a" in names
        assert "b" in names
        assert "file.txt" in names

    def test_list_files_allowed_path(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("main", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "readme.md").write_text("docs", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path, allowed_paths=["src"])
        tool = build_list_files_tool(ws)
        result = tool.handler({"path": "src"})

        assert result["total_count"] == 1
        assert result["entries"][0]["name"] == "main.py"

    def test_list_files_disallowed_path(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "docs").mkdir()

        ws = Workspace(repository_root=tmp_path, allowed_paths=["src"])
        tool = build_list_files_tool(ws)

        with pytest.raises(PathNotAllowedError):
            tool.handler({"path": "docs"})

    def test_list_files_traversal_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": "../outside"})

    def test_list_files_outside_absolute_path_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": str(tmp_path.parent)})

    def test_list_files_bounded_output(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text(f"{i}", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)
        result = tool.handler({"max_entries": 5})

        assert result["total_count"] == 5
        assert result["truncated"] is True

    def test_list_files_omits_secrets(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("code", encoding="utf-8")
        (tmp_path / ".env").write_text("SECRET=123", encoding="utf-8")
        (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
        (tmp_path / "server.key").write_text("key", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_list_files_tool(ws)
        result = tool.handler({})

        names = [e["name"] for e in result["entries"]]
        assert "app.py" in names
        assert ".env" not in names
        assert "credentials.json" not in names
        assert "server.key" not in names


class TestReadFileTool:
    """Tests for read_file repository tool."""

    def test_read_file_valid_text(self, tmp_path: Path) -> None:
        file = tmp_path / "sample.txt"
        file.write_text("Hello, ORION!\nLine 2", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)
        result = tool.handler({"path": "sample.txt"})

        assert result["content"] == "Hello, ORION!\nLine 2"
        assert result["total_lines"] == 2
        assert result["truncated"] is False

    def test_read_file_nonexistent(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(FileNotFoundError):
            tool.handler({"path": "missing.txt"})

    def test_read_file_directory_rejection(self, tmp_path: Path) -> None:
        (tmp_path / "dir").mkdir()
        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(IsADirectoryError):
            tool.handler({"path": "dir"})

    def test_read_file_traversal_rejection(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": "../secret.txt"})

    def test_read_file_outside_workspace(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("outside", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"path": str(outside)})

    def test_read_file_oversized_file(self, tmp_path: Path) -> None:
        large_file = tmp_path / "large.txt"
        # 1 MB + 1 byte
        large_file.write_bytes(b"a" * (1048576 + 1))

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(ValueError, match="exceeds maximum allowable limit"):
            tool.handler({"path": "large.txt"})

    def test_read_file_binary_rejection(self, tmp_path: Path) -> None:
        bin_file = tmp_path / "binary.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03\xff")

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(ValueError, match="Cannot read binary"):
            tool.handler({"path": "binary.bin"})

    def test_read_file_secret_protected(self, tmp_path: Path) -> None:
        secret = tmp_path / ".env"
        secret.write_text("API_KEY=xyz", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)

        with pytest.raises(ProtectedPathError):
            tool.handler({"path": ".env"})

        pem = tmp_path / "cert.pem"
        pem.write_text("cert", encoding="utf-8")
        with pytest.raises(ProtectedPathError):
            tool.handler({"path": "cert.pem"})

    def test_read_file_bounded_lines(self, tmp_path: Path) -> None:
        file = tmp_path / "lines.txt"
        file.write_text("\n".join(f"line {i}" for i in range(20)), encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_read_file_tool(ws)
        result = tool.handler({"path": "lines.txt", "max_lines": 5, "offset_lines": 2})

        assert result["lines_read"] == 5
        assert result["total_lines"] == 20
        assert result["truncated"] is True
        assert "line 2" in result["content"]


class TestSearchFilesTool:
    """Tests for search_files repository tool."""

    def test_search_files_normal(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("def find_me():\n    pass", encoding="utf-8")
        (tmp_path / "other.py").write_text("nothing here", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "find_me"})

        assert result["total_matches"] == 1
        assert result["matches"][0]["file"] == "app.py"
        assert result["matches"][0]["line_number"] == 1
        assert "def find_me" in result["matches"][0]["line_content"]

    def test_search_files_nested(self, tmp_path: Path) -> None:
        sub = tmp_path / "src" / "core"
        sub.mkdir(parents=True)
        (sub / "mod.py").write_text("target_token = 42", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "target_token"})

        assert result["total_matches"] == 1
        assert "mod.py" in result["matches"][0]["file"]

    def test_search_files_bounded_results(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"test_{i}.py").write_text("common_token = True", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "common_token", "max_results": 4})

        assert result["total_matches"] == 4
        assert result["truncated"] is True

    def test_search_files_disallowed_paths(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "code.py").write_text("needle", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.md").write_text("needle", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path, allowed_paths=["src"])
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "needle"})

        assert result["total_matches"] == 1
        assert "src" in result["matches"][0]["file"]

    def test_search_files_traversal_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"query": "token", "path": "../outside"})

    def test_search_files_binary_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "binary.dat").write_bytes(b"query_target\x00\xff")
        (tmp_path / "text.txt").write_text("query_target", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "query_target"})

        assert result["total_matches"] == 1
        assert result["matches"][0]["file"] == "text.txt"

    def test_search_files_secrets_skipped(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("find_token = secret", encoding="utf-8")
        (tmp_path / "secrets.json").write_text('{"find_token": "secret"}', encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_search_files_tool(ws)
        result = tool.handler({"query": "find_token"})

        assert result["total_matches"] == 0

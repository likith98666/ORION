import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from orion.core.tools.repository.validation_tools import (
    build_run_lint_tool,
    build_run_tests_tool,
    build_run_typecheck_tool,
    execute_validation_command,
)
from orion.core.workspace.errors import PathOutsideWorkspaceError
from orion.core.workspace.models import Workspace


class TestValidationTools:
    """Tests for run_tests, run_lint, and run_typecheck validation tools."""

    def test_run_tests_passing(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_sample.py"
        test_file.write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_tests_tool(ws)
        result = tool.handler({"target": "test_sample.py"})

        assert result["operation"] == "test"
        assert result["exit_code"] == 0
        assert result["status"] == "passed"
        assert result["timed_out"] is False
        assert result["workspace_id"] == str(ws.workspace_id)

    def test_run_tests_failing(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_fail():\n    assert 1 == 2\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_tests_tool(ws)
        result = tool.handler({"target": "test_fail.py"})

        assert result["exit_code"] != 0
        assert result["status"] == "failed"
        assert "assert 1 == 2" in result["stdout"] or "assert 1 == 2" in result["stderr"]

    def test_run_tests_target_outside_workspace_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_run_tests_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"target": "../outside_tests.py"})

    def test_run_tests_timeout_handling(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)

        def mock_subprocess_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = execute_validation_command("test", ["mock_cmd"], ws, timeout_seconds=1)

        assert result.timed_out is True
        assert result.status == "timeout"
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    def test_run_lint_passing(self, tmp_path: Path) -> None:
        py_file = tmp_path / "clean.py"
        py_file.write_text("x: int = 10\nprint(x)\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_lint_tool(ws)
        result = tool.handler({"target": "clean.py"})

        assert result["operation"] == "lint"
        assert result["exit_code"] == 0
        assert result["status"] == "passed"

    def test_run_lint_syntax_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_lint_tool(ws)
        result = tool.handler({"target": "bad.py"})

        assert result["exit_code"] != 0
        assert result["status"] == "failed"

    def test_run_typecheck_passing(self, tmp_path: Path) -> None:
        py_file = tmp_path / "typed.py"
        py_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_typecheck_tool(ws)
        result = tool.handler({"target": "typed.py"})

        assert result["operation"] == "typecheck"
        assert result["exit_code"] == 0
        assert result["status"] == "passed"

    def test_run_typecheck_type_error(self, tmp_path: Path) -> None:
        py_file = tmp_path / "wrong.py"
        py_file.write_text("def add(a: int) -> int:\n    return 'not an int'\n", encoding="utf-8")

        ws = Workspace(repository_root=tmp_path)
        tool = build_run_typecheck_tool(ws)
        result = tool.handler({"target": "wrong.py"})

        assert result["exit_code"] != 0
        assert result["status"] == "failed"
        assert (
            "Incompatible return value" in result["stdout"]
            or "Incompatible return value" in result["stderr"]
        )

    def test_run_typecheck_target_outside_workspace_rejected(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        tool = build_run_typecheck_tool(ws)

        with pytest.raises(PathOutsideWorkspaceError):
            tool.handler({"target": "../outside.py"})

    def test_no_shell_execution_enforced(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok"
            mock_run.return_value.stderr = ""

            execute_validation_command("test", ["python", "-m", "pytest"], ws)

            assert mock_run.called
            _, kwargs = mock_run.call_args
            assert kwargs["shell"] is False
            assert kwargs["cwd"] == str(ws.repository_root)

    def test_validation_command_timeout_with_bytes_output(self, tmp_path: Path) -> None:
        import subprocess

        ws = Workspace(repository_root=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["pytest"],
                timeout=10,
                output=b"partial bytes stdout",
                stderr=b"partial bytes stderr",
            )
            result = execute_validation_command("test", ["pytest"], ws)
            assert result.status == "timeout"
            assert "partial bytes stdout" in result.stdout
            assert "partial bytes stderr" in result.stderr

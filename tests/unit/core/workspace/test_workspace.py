import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from orion.core.observability.context import TelemetryContext
from orion.core.security.models import SecurityContext
from orion.core.workspace import (
    ExecutionIdentity,
    InvalidPathError,
    InvalidWorkspaceError,
    PathNotAllowedError,
    PathOutsideWorkspaceError,
    PathSecurityError,
    TaskScope,
    Workspace,
    WorkspaceError,
)


class TestWorkspaceValidCases:
    """Tests for permitted and canonical path resolution within a workspace."""

    def test_repository_root_access(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        resolved_dot = workspace.validate_path(".")
        assert resolved_dot == tmp_path.resolve()

        resolved_root = workspace.validate_path(tmp_path)
        assert resolved_root == tmp_path.resolve()
        assert workspace.is_path_allowed(".") is True

    def test_file_inside_repository(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        test_file = tmp_path / "hello.txt"
        test_file.write_text("content", encoding="utf-8")

        resolved = workspace.validate_path("hello.txt")
        assert resolved == test_file.resolve()
        assert workspace.is_path_allowed("hello.txt") is True

    def test_nested_directory(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        nested_dir = tmp_path / "src" / "core"
        nested_dir.mkdir(parents=True)

        resolved = workspace.validate_path("src/core")
        assert resolved == nested_dir.resolve()
        assert workspace.is_path_allowed("src/core") is True

    def test_nested_file(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        nested_file = tmp_path / "src" / "core" / "main.py"
        nested_file.parent.mkdir(parents=True, exist_ok=True)
        nested_file.write_text("print('test')", encoding="utf-8")

        resolved = workspace.validate_path("src/core/main.py")
        assert resolved == nested_file.resolve()
        assert workspace.is_path_allowed("src/core/main.py") is True

    def test_relative_path_normalization(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        target = tmp_path / "src" / "module.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("code", encoding="utf-8")

        # Resolves internal .. that stays within workspace boundary
        resolved = workspace.resolve_path("src/sub/../module.py")
        assert resolved == target.resolve()
        assert workspace.is_path_allowed("src/sub/../module.py") is True

    def test_explicitly_allowed_path(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        main_py = src_dir / "main.py"
        main_py.write_text("code", encoding="utf-8")

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]", encoding="utf-8")

        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["src", "pyproject.toml"],
        )

        assert workspace.validate_path("src/main.py") == main_py.resolve()
        assert workspace.validate_path("pyproject.toml") == pyproject.resolve()
        assert workspace.is_path_allowed("src/main.py") is True
        assert workspace.is_path_allowed("pyproject.toml") is True

    def test_relative_path_helper(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        src_file = tmp_path / "src" / "app.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("app", encoding="utf-8")

        rel = workspace.relative_path("src/app.py")
        assert rel == Path("src") / "app.py"

    def test_absolute_path_inside_workspace(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf-8")

        resolved = workspace.validate_path(target.resolve())
        assert resolved == target.resolve()


class TestWorkspaceRejectionCases:
    """Tests for rejecting traversal, outside paths, disallowed scope, and invalid configs."""

    def test_single_level_traversal_rejected(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(PathOutsideWorkspaceError) as exc_info:
            workspace.validate_path("../outside.txt")
        assert exc_info.value.requested_path == "../outside.txt"
        assert exc_info.value.workspace_boundary == str(tmp_path.resolve())
        assert workspace.is_path_allowed("../outside.txt") is False

    def test_multilevel_traversal_rejected(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path("../../secret.txt")
        assert workspace.is_path_allowed("../../secret.txt") is False

    def test_traversal_after_nested_path_rejected(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path("src/sub/../../../outside.txt")
        assert workspace.is_path_allowed("src/sub/../../../outside.txt") is False

    def test_absolute_path_outside_workspace_rejected(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        outside_path = tmp_path.parent / "secret_outside.txt"

        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path(outside_path)
        assert workspace.is_path_allowed(outside_path) is False

        # System paths
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path("/etc/passwd")
        assert workspace.is_path_allowed("/etc/passwd") is False

    def test_sibling_directory_prefix_rejected(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        evil_dir = tmp_path / "repo_evil"
        evil_dir.mkdir()
        evil_file = evil_dir / "secret.txt"
        evil_file.write_text("stolen", encoding="utf-8")

        workspace = Workspace(repository_root=repo_dir)

        # Ensure string prefix matching would fail and component containment holds
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path(evil_file)
        assert workspace.is_path_allowed(evil_file) is False

    def test_path_escaping_after_normalization(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "subdir").mkdir()

        workspace = Workspace(repository_root=repo_dir)
        escape_path = "subdir/../../outside.txt"

        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path(escape_path)
        assert workspace.is_path_allowed(escape_path) is False

    def test_disallowed_path_rejected(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_app.py"
        test_file.write_text("test", encoding="utf-8")

        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["src"],
        )

        # File is inside repository_root, but outside task allowed_paths
        with pytest.raises(PathNotAllowedError) as exc_info:
            workspace.validate_path("tests/test_app.py")
        assert exc_info.value.requested_path == "tests/test_app.py"
        assert exc_info.value.workspace_boundary == str(tmp_path.resolve())
        assert workspace.is_path_allowed("tests/test_app.py") is False

    def test_disallowed_file_subpath_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text("{}", encoding="utf-8")

        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["config.json"],
        )

        assert workspace.is_path_allowed("config.json") is True
        # Accessing a child path under a regular file is disallowed
        assert workspace.is_path_allowed("config.json/sub") is False
        with pytest.raises(PathNotAllowedError):
            workspace.validate_path("config.json/sub")

    def test_invalid_workspace_nonexistent_root(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidWorkspaceError):
            Workspace(repository_root=tmp_path / "nonexistent_dir")

    def test_invalid_workspace_root_is_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "regular_file.txt"
        file_path.write_text("file", encoding="utf-8")

        with pytest.raises(InvalidWorkspaceError):
            Workspace(repository_root=file_path)

    def test_invalid_workspace_empty_root(self) -> None:
        with pytest.raises(InvalidWorkspaceError):
            Workspace(repository_root="")

        with pytest.raises(InvalidWorkspaceError):
            Workspace(repository_root="   ")

    def test_invalid_workspace_escaping_allowed_path(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidWorkspaceError):
            Workspace(
                repository_root=tmp_path,
                allowed_paths=["../outside"],
            )

    def test_invalid_workspace_absolute_outside_allowed_path(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside"
        with pytest.raises(InvalidWorkspaceError):
            Workspace(
                repository_root=tmp_path,
                allowed_paths=[outside],
            )

    def test_invalid_workspace_empty_allowed_path_item(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidWorkspaceError):
            Workspace(
                repository_root=tmp_path,
                allowed_paths=[""],
            )

    def test_invalid_workspace_null_byte_allowed_path(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidWorkspaceError):
            Workspace(
                repository_root=tmp_path,
                allowed_paths=["foo\0bar"],
            )

    def test_invalid_workspace_string_allowed_paths_type_error(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError):
            Workspace(
                repository_root=tmp_path,
                allowed_paths="src",  # must be iterable of paths, not a single string
            )

    def test_invalid_path_empty_string(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(InvalidPathError):
            workspace.validate_path("")
        assert workspace.is_path_allowed("") is False

    def test_invalid_path_whitespace(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(InvalidPathError):
            workspace.validate_path("   \t\n")
        assert workspace.is_path_allowed("   \t\n") is False

    def test_invalid_path_null_byte(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(InvalidPathError):
            workspace.validate_path("hello\0world.txt")
        assert workspace.is_path_allowed("hello\0world.txt") is False

    def test_invalid_path_type(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        with pytest.raises(TypeError):
            workspace.validate_path(12345)  # type: ignore[arg-type]
        assert workspace.is_path_allowed(12345) is False  # type: ignore[arg-type]


class TestWorkspaceBoundaryCases:
    """Tests for exact boundary matches and Windows-specific semantics."""

    def test_exact_workspace_boundary(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        assert workspace.validate_path(".") == tmp_path.resolve()
        assert workspace.is_path_allowed(".") is True

    def test_boundary_root_with_restricted_allowed_paths(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["src"],
        )
        # When allowed_paths is restricted to src/, root itself is not in allowed paths
        assert workspace.is_path_allowed(".") is False
        with pytest.raises(PathNotAllowedError):
            workspace.validate_path(".")

    def test_boundary_root_explicitly_in_allowed_paths(self, tmp_path: Path) -> None:
        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["."],
        )
        assert workspace.is_path_allowed(".") is True
        assert workspace.validate_path(".") == tmp_path.resolve()

    def test_windows_slash_normalization(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        file_path = tmp_path / "src" / "pkg" / "mod.py"
        file_path.write_text("x = 1", encoding="utf-8")

        # Mixed slashes
        resolved_mixed = workspace.validate_path("src/pkg\\mod.py")
        assert resolved_mixed == file_path.resolve()


class TestWorkspaceSymlinkAndJunctionEscape:
    """Tests ensuring resolved paths cannot escape the permitted workspace via symlinks."""

    def test_junction_escape_rejected_on_windows(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows directory junction test.")

        import _winapi

        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("classified", encoding="utf-8")

        junction_point = str(repo / "junc_outside")
        _winapi.CreateJunction(str(outside), junction_point)

        workspace = Workspace(repository_root=repo)

        # Path within repo that traverses junction to outside must be rejected
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path("junc_outside/secret.txt")
        assert workspace.is_path_allowed("junc_outside/secret.txt") is False

    def test_internal_junction_permitted_on_windows(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows directory junction test.")

        import _winapi

        repo = tmp_path / "repo"
        repo.mkdir()
        real_src = repo / "real_src"
        real_src.mkdir()
        target_file = real_src / "code.py"
        target_file.write_text("print(1)", encoding="utf-8")

        internal_junc = str(repo / "src_link")
        _winapi.CreateJunction(str(real_src), internal_junc)

        workspace = Workspace(repository_root=repo)
        resolved = workspace.validate_path("src_link/code.py")
        assert resolved == target_file.resolve()
        assert workspace.is_path_allowed("src_link/code.py") is True

    def test_symlink_escape_rejected_if_supported(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("classified", encoding="utf-8")

        symlink_target = repo / "sym_link"
        try:
            os.symlink(outside, symlink_target)
        except OSError:
            pytest.skip("Symlink creation requires administrative privilege or developer mode.")

        workspace = Workspace(repository_root=repo)
        with pytest.raises(PathOutsideWorkspaceError):
            workspace.validate_path("sym_link/secret.txt")
        assert workspace.is_path_allowed("sym_link/secret.txt") is False


class TestWorkspaceIdentityAndScope:
    """Tests for execution identity traceability and task scope."""

    def test_execution_identity_defaults(self, tmp_path: Path) -> None:
        workspace = Workspace(repository_root=tmp_path)
        assert workspace.workspace_id is not None
        assert workspace.id == workspace.workspace_id
        assert workspace.task_id is None
        assert workspace.execution_id is None
        assert workspace.trace_id is None
        assert workspace.request_id is None
        assert isinstance(workspace.execution_identity, ExecutionIdentity)
        assert workspace.execution_identity.workspace_id == workspace.workspace_id

    def test_execution_identity_explicit_uuids(self, tmp_path: Path) -> None:
        ws_id = uuid4()
        t_id = uuid4()
        e_id = uuid4()
        tr_id = uuid4()
        r_id = uuid4()

        workspace = Workspace(
            repository_root=tmp_path,
            workspace_id=ws_id,
            task_id=t_id,
            execution_id=e_id,
            trace_id=tr_id,
            request_id=r_id,
        )

        assert workspace.workspace_id == ws_id
        assert workspace.task_id == t_id
        assert workspace.execution_id == e_id
        assert workspace.trace_id == tr_id
        assert workspace.request_id == r_id

    def test_execution_identity_from_telemetry_context(self, tmp_path: Path) -> None:
        t_id = uuid4()
        e_id = uuid4()
        tr_id = uuid4()
        r_id = uuid4()

        telemetry = TelemetryContext(
            request_id=r_id,
            trace_id=tr_id,
            task_id=t_id,
            execution_id=e_id,
        )

        workspace = Workspace(
            repository_root=tmp_path,
            telemetry_context=telemetry,
        )

        assert workspace.task_id == t_id
        assert workspace.execution_id == e_id
        assert workspace.trace_id == tr_id
        assert workspace.request_id == r_id

    def test_execution_identity_from_security_context(self, tmp_path: Path) -> None:
        a_id = uuid4()
        t_id = uuid4()
        e_id = uuid4()

        security_ctx = SecurityContext(
            agent_id=a_id,
            task_id=t_id,
            execution_id=e_id,
        )

        workspace = Workspace(
            repository_root=tmp_path,
            security_context=security_ctx,
        )

        assert workspace.task_id == t_id
        assert workspace.execution_id == e_id

    def test_task_scope_integration(self, tmp_path: Path) -> None:
        t_id = uuid4()
        scope = TaskScope(
            task_id=t_id,
            description="Autonomous refactor task",
            allowed_paths=("src/core", "tests/unit"),
        )

        workspace = Workspace(
            repository_root=tmp_path,
            task_scope=scope,
        )

        assert workspace.task_scope == scope
        assert workspace.task_id == t_id
        assert len(workspace.allowed_paths) == 2

    def test_with_allowed_paths_creates_new_instance(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "docs").mkdir()

        initial_workspace = Workspace(repository_root=tmp_path)
        narrowed_workspace = initial_workspace.with_allowed_paths(["src"])

        assert narrowed_workspace is not initial_workspace
        assert narrowed_workspace.workspace_id == initial_workspace.workspace_id
        assert len(narrowed_workspace.allowed_paths) == 1
        assert len(initial_workspace.allowed_paths) == 0

    def test_with_task_scope_creates_new_instance(self, tmp_path: Path) -> None:
        initial_workspace = Workspace(repository_root=tmp_path)
        new_scope = TaskScope(description="New task scope")
        updated_workspace = initial_workspace.with_task_scope(new_scope)

        assert updated_workspace is not initial_workspace
        assert updated_workspace.task_scope == new_scope
        assert updated_workspace.workspace_id == initial_workspace.workspace_id


class TestWorkspaceErrorDetails:
    """Tests verifying error structures, attributes, and inheritance hierarchy."""

    def test_error_attributes_and_hierarchy(self, tmp_path: Path) -> None:
        workspace = Workspace(
            repository_root=tmp_path,
            allowed_paths=["src"],
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test.py").write_text("t", encoding="utf-8")

        # Outside workspace error
        with pytest.raises(PathOutsideWorkspaceError) as exc_outside:
            workspace.validate_path("../outside.txt")
        err1 = exc_outside.value
        assert isinstance(err1, PathSecurityError)
        assert isinstance(err1, WorkspaceError)
        assert isinstance(err1, ValueError)
        assert err1.requested_path == "../outside.txt"
        assert err1.workspace_boundary == str(tmp_path.resolve())
        assert "escapes repository root" in err1.reason

        # Not allowed error
        with pytest.raises(PathNotAllowedError) as exc_disallowed:
            workspace.validate_path("tests/test.py")
        err2 = exc_disallowed.value
        assert isinstance(err2, PathSecurityError)
        assert isinstance(err2, WorkspaceError)
        assert isinstance(err2, PermissionError)
        assert err2.requested_path == "tests/test.py"
        assert err2.workspace_boundary == str(tmp_path.resolve())
        assert "not within permitted task scope" in err2.reason

        # Invalid path error
        with pytest.raises(InvalidPathError) as exc_invalid:
            workspace.validate_path("")
        err3 = exc_invalid.value
        assert isinstance(err3, WorkspaceError)
        assert isinstance(err3, ValueError)

        # Invalid workspace error
        with pytest.raises(InvalidWorkspaceError) as exc_ws:
            Workspace(repository_root=tmp_path / "nonexistent")
        err4 = exc_ws.value
        assert isinstance(err4, WorkspaceError)
        assert isinstance(err4, ValueError)

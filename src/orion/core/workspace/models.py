from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from orion.core.observability.context import TelemetryContext
from orion.core.security.models import SecurityContext
from orion.core.workspace.errors import (
    InvalidPathError,
    InvalidWorkspaceError,
    PathNotAllowedError,
    PathOutsideWorkspaceError,
    PathSecurityError,
)


@dataclass(frozen=True)
class TaskScope:
    """Lightweight specification of task-level filesystem scope within a workspace."""

    task_id: UUID | None = None
    description: str = ""
    allowed_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.task_id is not None and not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID or None.")

        if not isinstance(self.description, str):
            raise TypeError("description must be a string.")

        if isinstance(self.allowed_paths, str):
            raise TypeError("allowed_paths must be an iterable of path strings, not a string.")

        if not isinstance(self.allowed_paths, (tuple, list, set, frozenset)):
            raise TypeError("allowed_paths must be an iterable collection.")

        cleaned = tuple(str(p).strip() for p in self.allowed_paths if str(p).strip())
        object.__setattr__(self, "allowed_paths", cleaned)


@dataclass(frozen=True)
class ExecutionIdentity:
    """Traceable execution identity binding linking a workspace to ORION's execution hierarchy."""

    workspace_id: UUID
    task_id: UUID | None = None
    execution_id: UUID | None = None
    trace_id: UUID | None = None
    request_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_id, UUID):
            raise TypeError("workspace_id must be a UUID.")

        for field_name in ("task_id", "execution_id", "trace_id", "request_id"):
            val = getattr(self, field_name)
            if val is not None and not isinstance(val, UUID):
                raise TypeError(f"{field_name} must be a UUID or None.")

    @classmethod
    def from_telemetry_context(
        cls,
        workspace_id: UUID,
        telemetry_context: TelemetryContext,
    ) -> ExecutionIdentity:
        """Create an execution identity binding from an existing TelemetryContext."""
        return cls(
            workspace_id=workspace_id,
            task_id=telemetry_context.task_id,
            execution_id=telemetry_context.execution_id,
            trace_id=telemetry_context.trace_id,
            request_id=telemetry_context.request_id,
        )

    @classmethod
    def from_security_context(
        cls,
        workspace_id: UUID,
        security_context: SecurityContext,
    ) -> ExecutionIdentity:
        """Create an execution identity binding from an existing SecurityContext."""
        return cls(
            workspace_id=workspace_id,
            task_id=security_context.task_id,
            execution_id=security_context.execution_id,
        )


class Workspace:
    """Explicit workspace boundary defining the filesystem boundary of an ORION execution."""

    def __init__(
        self,
        repository_root: str | Path,
        allowed_paths: Iterable[str | Path] | None = None,
        workspace_id: UUID | None = None,
        task_scope: TaskScope | str | None = None,
        execution_identity: ExecutionIdentity | None = None,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        trace_id: UUID | None = None,
        request_id: UUID | None = None,
        telemetry_context: TelemetryContext | None = None,
        security_context: SecurityContext | None = None,
    ) -> None:
        if workspace_id is None:
            if execution_identity is not None:
                workspace_id = execution_identity.workspace_id
            else:
                workspace_id = uuid4()
        elif not isinstance(workspace_id, UUID):
            raise TypeError("workspace_id must be a UUID.")

        if repository_root is None or (
            isinstance(repository_root, str) and not repository_root.strip()
        ):
            raise InvalidWorkspaceError("Repository root cannot be empty.")

        try:
            resolved_root = Path(repository_root).resolve()
        except Exception as e:
            raise InvalidWorkspaceError(
                f"Invalid repository root '{repository_root}': {e}"
            ) from e

        if not resolved_root.exists():
            raise InvalidWorkspaceError(
                f"Repository root does not exist: '{resolved_root}'"
            )
        if not resolved_root.is_dir():
            raise InvalidWorkspaceError(
                f"Repository root is not a directory: '{resolved_root}'"
            )

        if task_scope is None:
            scope_obj = TaskScope(task_id=task_id)
        elif isinstance(task_scope, str):
            scope_obj = TaskScope(task_id=task_id, description=task_scope)
        elif isinstance(task_scope, TaskScope):
            if task_id is not None and task_scope.task_id is None:
                scope_obj = TaskScope(
                    task_id=task_id,
                    description=task_scope.description,
                    allowed_paths=task_scope.allowed_paths,
                )
            else:
                scope_obj = task_scope
        else:
            raise TypeError("task_scope must be a TaskScope, str, or None.")

        if allowed_paths is None:
            raw_allowed: tuple[str | Path, ...] = (
                scope_obj.allowed_paths if scope_obj.allowed_paths else ()
            )
        else:
            if isinstance(allowed_paths, str):
                raise TypeError(
                    "allowed_paths must be an iterable of paths, not a string."
                )
            raw_allowed = tuple(allowed_paths)

        resolved_allowed: list[Path] = []
        for item in raw_allowed:
            if item is None or (isinstance(item, str) and not item.strip()):
                raise InvalidWorkspaceError("Allowed path entries cannot be empty.")
            if "\0" in str(item):
                raise InvalidWorkspaceError(f"Allowed path '{item}' contains null byte.")

            item_path = Path(item)
            is_abs = (
                os.path.isabs(str(item))
                or item_path.is_absolute()
                or bool(item_path.anchor)
            )
            if is_abs:
                resolved_item = item_path.resolve()
            else:
                resolved_item = (resolved_root / item_path).resolve()

            try:
                is_inside = resolved_item.is_relative_to(resolved_root)
            except (ValueError, AttributeError):
                is_inside = False

            if not is_inside:
                raise InvalidWorkspaceError(
                    f"Allowed path '{item}' escapes repository root '{resolved_root}'."
                )
            resolved_allowed.append(resolved_item)

        if execution_identity is not None:
            if not isinstance(execution_identity, ExecutionIdentity):
                raise TypeError("execution_identity must be an ExecutionIdentity.")
            ident = execution_identity
        elif telemetry_context is not None:
            ident = ExecutionIdentity.from_telemetry_context(
                workspace_id=workspace_id,
                telemetry_context=telemetry_context,
            )
        elif security_context is not None:
            ident = ExecutionIdentity.from_security_context(
                workspace_id=workspace_id,
                security_context=security_context,
            )
        else:
            effective_task_id = task_id or scope_obj.task_id
            ident = ExecutionIdentity(
                workspace_id=workspace_id,
                task_id=effective_task_id,
                execution_id=execution_id,
                trace_id=trace_id,
                request_id=request_id,
            )

        self._workspace_id = workspace_id
        self._repository_root = resolved_root
        self._allowed_paths = tuple(resolved_allowed)
        self._task_scope = scope_obj
        self._execution_identity = ident

    @classmethod
    def create(
        cls,
        repository_root: str | Path,
        allowed_paths: Iterable[str | Path] | None = None,
        task_scope: TaskScope | str | None = None,
        execution_identity: ExecutionIdentity | None = None,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        trace_id: UUID | None = None,
        request_id: UUID | None = None,
        telemetry_context: TelemetryContext | None = None,
        security_context: SecurityContext | None = None,
    ) -> Workspace:
        """Create a validated Workspace boundary."""
        return cls(
            repository_root=repository_root,
            allowed_paths=allowed_paths,
            task_scope=task_scope,
            execution_identity=execution_identity,
            task_id=task_id,
            execution_id=execution_id,
            trace_id=trace_id,
            request_id=request_id,
            telemetry_context=telemetry_context,
            security_context=security_context,
        )

    @property
    def workspace_id(self) -> UUID:
        """Return the unique workspace identifier."""
        return self._workspace_id

    @property
    def id(self) -> UUID:
        """Return the unique workspace identifier."""
        return self._workspace_id

    @property
    def repository_root(self) -> Path:
        """Return the canonical repository root path."""
        return self._repository_root

    @property
    def allowed_paths(self) -> tuple[Path, ...]:
        """Return the tuple of canonical allowed paths permitted for this task."""
        return self._allowed_paths

    @property
    def task_scope(self) -> TaskScope:
        """Return the task scope descriptor."""
        return self._task_scope

    @property
    def execution_identity(self) -> ExecutionIdentity:
        """Return the execution identity binding."""
        return self._execution_identity

    @property
    def task_id(self) -> UUID | None:
        """Return the associated task ID, if any."""
        return self._execution_identity.task_id

    @property
    def execution_id(self) -> UUID | None:
        """Return the associated execution ID, if any."""
        return self._execution_identity.execution_id

    @property
    def trace_id(self) -> UUID | None:
        """Return the associated trace ID, if any."""
        return self._execution_identity.trace_id

    @property
    def request_id(self) -> UUID | None:
        """Return the associated request ID, if any."""
        return self._execution_identity.request_id

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a path to its canonical representation within the workspace repository root.

        Handles '.', '..', relative paths, and symlink/junction targets.
        Ensures the canonical path does not escape the repository root boundary.

        Raises:
            TypeError: If path is not a str or Path.
            InvalidPathError: If path is empty, blank, or malformed.
            PathOutsideWorkspaceError: If the resolved path escapes the repository root.
        """
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a str or Path.")

        path_str = str(path)
        if not path_str.strip():
            raise InvalidPathError("Path cannot be empty or blank.")

        if "\0" in path_str:
            raise InvalidPathError("Path contains null byte.")

        try:
            path_obj = Path(path)
            is_abs = (
                os.path.isabs(path_str)
                or path_obj.is_absolute()
                or bool(path_obj.anchor)
            )
            if is_abs:
                resolved = path_obj.resolve()
            else:
                resolved = (self._repository_root / path_obj).resolve()
        except (ValueError, OSError) as e:
            raise InvalidPathError(f"Malformed or invalid path '{path}': {e}") from e

        try:
            is_contained = resolved.is_relative_to(self._repository_root)
        except (ValueError, AttributeError):
            is_contained = False

        if not is_contained:
            raise PathOutsideWorkspaceError(
                requested_path=path_str,
                workspace_boundary=str(self._repository_root),
                reason="Resolved path escapes repository root.",
            )

        return resolved

    def _is_covered_by_allowed_paths(self, resolved_target: Path) -> bool:
        """Check if a resolved target path is permitted under the configured allowed_paths."""
        if not self._allowed_paths:
            return True

        for allowed in self._allowed_paths:
            if resolved_target == allowed:
                return True
            if allowed.is_file():
                continue
            if (
                allowed.suffix
                and not allowed.is_dir()
                and not allowed.name.startswith(".")
            ):
                continue
            try:
                if resolved_target.is_relative_to(allowed):
                    return True
            except (ValueError, AttributeError):
                continue

        return False

    def validate_path(self, path: str | Path) -> Path:
        """Validate that a path is securely within the workspace and permitted by task scope.

        Returns:
            The canonical resolved Path.

        Raises:
            TypeError: If path is not a str or Path.
            InvalidPathError: If path is empty, blank, or malformed.
            PathOutsideWorkspaceError: If path escapes or lies outside the workspace root.
            PathNotAllowedError: If path is within workspace root but not permitted
                by allowed_paths.
        """
        resolved = self.resolve_path(path)

        if not self._is_covered_by_allowed_paths(resolved):
            allowed_repr = [str(p) for p in self._allowed_paths]
            raise PathNotAllowedError(
                requested_path=str(path),
                workspace_boundary=str(self._repository_root),
                reason=f"Path is not within permitted task scope allowed paths: {allowed_repr}",
            )

        return resolved

    def is_path_allowed(self, path: str | Path) -> bool:
        """Check if a path is permitted within this workspace and task scope.

        Returns True if the path resolves safely within repository_root and
        satisfies allowed_paths; False otherwise.
        """
        try:
            self.validate_path(path)
            return True
        except (PathSecurityError, InvalidPathError, TypeError):
            return False

    def relative_path(self, path: str | Path) -> Path:
        """Return the relative path from repository_root for a permitted path."""
        resolved = self.validate_path(path)
        return resolved.relative_to(self._repository_root)

    def with_allowed_paths(
        self,
        allowed_paths: Iterable[str | Path],
    ) -> Workspace:
        """Create a new Workspace instance with narrower allowed paths."""
        return Workspace(
            repository_root=self._repository_root,
            allowed_paths=allowed_paths,
            workspace_id=self._workspace_id,
            task_scope=self._task_scope,
            execution_identity=self._execution_identity,
        )

    def with_task_scope(self, task_scope: TaskScope | str) -> Workspace:
        """Create a new Workspace instance bound to a specific task scope."""
        return Workspace(
            repository_root=self._repository_root,
            allowed_paths=self._allowed_paths,
            workspace_id=self._workspace_id,
            task_scope=task_scope,
            execution_identity=self._execution_identity,
        )

    def __repr__(self) -> str:
        return (
            f"Workspace(id={self._workspace_id}, "
            f"root='{self._repository_root}', "
            f"allowed_paths={len(self._allowed_paths)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Workspace):
            return False
        return (
            self._workspace_id == other._workspace_id
            and self._repository_root == other._repository_root
            and self._allowed_paths == other._allowed_paths
            and self._task_scope == other._task_scope
            and self._execution_identity == other._execution_identity
        )

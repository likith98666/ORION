from orion.core.workspace.errors import WorkspaceError


class RepositoryToolError(WorkspaceError):
    """Base exception for repository tool execution errors."""


class ProtectedPathError(RepositoryToolError, PermissionError):
    """Raised when an operation attempts to access or modify a protected secret file."""


class StaleStateError(RepositoryToolError, ValueError):
    """Raised when apply_change detects optimistic concurrency failure or stale state."""


class ValidationExecutionError(RepositoryToolError, RuntimeError):
    """Raised when a validation command execution fails catastrophically."""

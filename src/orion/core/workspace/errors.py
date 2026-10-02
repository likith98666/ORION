class WorkspaceError(Exception):
    """Base exception for all workspace-related errors in ORION."""


class InvalidWorkspaceError(WorkspaceError, ValueError):
    """Raised when a workspace configuration is invalid or malformed."""


class InvalidPathError(WorkspaceError, ValueError):
    """Raised when a requested path is empty, blank, or structurally invalid."""


class PathSecurityError(WorkspaceError):
    """Base class for workspace path boundary and permission rejections."""

    def __init__(
        self,
        requested_path: str,
        workspace_boundary: str,
        reason: str,
    ) -> None:
        self.requested_path = requested_path
        self.workspace_boundary = workspace_boundary
        self.reason = reason
        super().__init__(
            f"Path security violation: requested='{requested_path}', "
            f"boundary='{workspace_boundary}', reason='{reason}'"
        )


class PathOutsideWorkspaceError(PathSecurityError, ValueError):
    """Raised when a requested path escapes or lies outside the workspace repository root."""


class PathNotAllowedError(PathSecurityError, PermissionError):
    """Raised when a path is within the workspace root but not permitted by task scope."""

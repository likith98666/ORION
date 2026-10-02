"""Typed exceptions for Phase 5 controlled patch application and execution."""

from __future__ import annotations


class Phase5ExecutionError(Exception):
    """Base exception for all Phase 5 execution operations."""


class InvalidStateTransitionError(Phase5ExecutionError):
    """Raised when an illegal lifecycle state transition is attempted."""


class PatchApplicationError(Phase5ExecutionError):
    """Base exception for patch application failures."""


class UnapprovedPatchError(PatchApplicationError):
    """Raised when application is attempted on a patch without valid approval."""


class StaleApprovalError(PatchApplicationError):
    """Raised when an approval is expired or references stale state."""


class RevokedApprovalError(PatchApplicationError):
    """Raised when an approval has been denied, revoked, or rejected."""


class ApprovalIntegrityError(PatchApplicationError):
    """Raised when the patch proposal does not match the approval record or execution context."""


class WorkspaceLockedError(Phase5ExecutionError):
    """Raised when a workspace is already locked by another concurrent execution."""


class PatchRecoveryError(Phase5ExecutionError):
    """Raised when restoring from a recovery point fails."""


class PostApplyIntegrityError(PatchApplicationError):
    """Raised when post-apply verification detects filesystem integrity discrepancies."""


class ControlledExecutionError(Phase5ExecutionError):
    """Raised when controlled test execution encounters an error or policy violation."""

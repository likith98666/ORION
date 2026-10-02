"""Typed exceptions for controlled cognitive SWE operations."""

from __future__ import annotations

from orion.core.swe.errors import SWEWorkflowError
from orion.core.tools.repository.errors import StaleStateError


class CognitiveError(SWEWorkflowError):
    """Base exception for cognitive model analysis and fix formulation errors."""


class InvalidProposalError(CognitiveError):
    """Raised when a model proposal fails structural schema or semantic validation."""


class UnsafeProposalPathError(InvalidProposalError):
    """Raised when a model proposal specifies an unsafe, external, traversal, or protected path."""


class CognitiveModelUnavailableError(CognitiveError):
    """Raised when the cognitive model provider fails or is unreachable and no fallback occurred."""


class PatchSynthesisError(CognitiveError):
    """Base exception for patch synthesis and validation errors."""


class InvalidPatchError(PatchSynthesisError, InvalidProposalError):
    """Raised when a patch proposal fails schema, type, or bounds validation."""


class UnsafePatchPathError(PatchSynthesisError, UnsafeProposalPathError):
    """Raised when a patch proposal contains unsafe or protected filesystem paths."""


class PatchTooLargeError(PatchSynthesisError, ValueError):
    """Raised when a patch exceeds configured size, file count, or changed line limits."""


class PatchSyntaxError(PatchSynthesisError, ValueError):
    """Raised when a patch fails syntax validation for supported languages."""


class StalePatchError(PatchSynthesisError, StaleStateError):
    """Raised when optimistic concurrency fails due to mismatched expected file hashes."""


class UnsupportedPatchOperationError(PatchSynthesisError, ValueError):
    """Raised when a patch proposal requests an unsupported filesystem operation."""


class PatchApprovalRequiredError(PatchSynthesisError, PermissionError):
    """Raised when a patch proposal requires approval before proceeding."""

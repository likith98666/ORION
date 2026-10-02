

class SWEWorkflowError(Exception):
    """Base exception for all SWE workflow operations."""


class WorkflowSequenceError(SWEWorkflowError):
    """Raised when stages are attempted out of sequence or dependencies are unmet."""


class DisallowedStageToolError(SWEWorkflowError):
    """Raised when a tool is invoked that is not permitted in the current workflow stage."""


class DisallowedFileModificationError(DisallowedStageToolError):
    """Raised when a read-only or reasoning stage attempts to modify files."""


class UnverifiedSuccessError(SWEWorkflowError):
    """Raised when an SWE workflow or report claims success without verified evidence."""


class MissingWorkspaceError(SWEWorkflowError):
    """Raised when an SWE workflow or operation lacks a mandatory Workspace binding."""


class FormulationIncompleteError(SWEWorkflowError):
    """Raised when a proposed fix formulation is incomplete or invalid."""

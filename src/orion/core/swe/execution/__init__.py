"""Phase 5 controlled patch application, execution, and verification package."""

from __future__ import annotations

from orion.core.swe.execution.applier import PatchApplicationAuthority
from orion.core.swe.execution.contracts import (
    AppliedOperationRecord,
    ControlledTestResult,
    FileSnapshot,
    PatchApplicationResult,
    PatchRecoveryPoint,
    Phase5ExecutionOutcome,
    PostApplyIntegrityResult,
)
from orion.core.swe.execution.errors import (
    ApprovalIntegrityError,
    ControlledExecutionError,
    InvalidStateTransitionError,
    PatchApplicationError,
    PatchRecoveryError,
    Phase5ExecutionError,
    PostApplyIntegrityError,
    RevokedApprovalError,
    StaleApprovalError,
    UnapprovedPatchError,
    WorkspaceLockedError,
)
from orion.core.swe.execution.lock import WorkspaceLockManager
from orion.core.swe.execution.recovery import PatchRecoveryManager
from orion.core.swe.execution.runner import ControlledExecutionAuthority
from orion.core.swe.execution.selector import (
    TestSelectionResult,
    TestSelectionStrategy,
    TestTargetSelector,
)
from orion.core.swe.execution.states import (
    PatchExecutionLifecycle,
    PatchExecutionState,
    StateTransitionRecord,
)
from orion.core.swe.execution.verifier import PatchVerificationAuthority

__all__ = [
    "AppliedOperationRecord",
    "ApprovalIntegrityError",
    "ControlledExecutionAuthority",
    "ControlledExecutionError",
    "ControlledTestResult",
    "FileSnapshot",
    "InvalidStateTransitionError",
    "PatchApplicationAuthority",
    "PatchApplicationError",
    "PatchApplicationResult",
    "PatchExecutionLifecycle",
    "PatchExecutionState",
    "PatchRecoveryError",
    "PatchRecoveryManager",
    "PatchRecoveryPoint",
    "PatchVerificationAuthority",
    "Phase5ExecutionError",
    "Phase5ExecutionOutcome",
    "PostApplyIntegrityError",
    "PostApplyIntegrityResult",
    "RevokedApprovalError",
    "StaleApprovalError",
    "StateTransitionRecord",
    "TestSelectionResult",
    "TestSelectionStrategy",
    "TestTargetSelector",
    "UnapprovedPatchError",
    "WorkspaceLockManager",
    "WorkspaceLockedError",
]

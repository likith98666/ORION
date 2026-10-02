"""Typed exception hierarchy for Phase 6 Bounded Self-Healing Recovery."""

from __future__ import annotations

from orion.core.swe.errors import SWEWorkflowError


class Phase6RecoveryError(SWEWorkflowError):
    """Base exception for all Phase 6 self-healing recovery errors."""


class InvalidRecoveryTransitionError(Phase6RecoveryError):
    """Raised when an illegal state transition is attempted in RecoveryAttemptLifecycle."""


class BudgetExhaustedError(Phase6RecoveryError):
    """Raised when recovery operations exceed configured budget limits."""


class RecoveryDepthExceededError(Phase6RecoveryError):
    """Raised when the recovery call depth exceeds the hard limit."""


class RecoveryPolicyViolationError(Phase6RecoveryError):
    """Raised when a selected strategy violates authoritative recovery policy."""


class StrategyExecutionError(Phase6RecoveryError):
    """Raised when a recovery strategy execution handler fails."""


class RollbackExecutionError(Phase6RecoveryError):
    """Raised when snapshot rollback fails to restore clean workspace state."""


class UnauthorizedRecoveryError(Phase6RecoveryError):
    """Raised when recovery operations attempt to execute without mandatory approval."""


class UnregisteredStrategyError(Phase6RecoveryError):
    """Raised when an unapproved or dynamically invented recovery strategy is requested."""

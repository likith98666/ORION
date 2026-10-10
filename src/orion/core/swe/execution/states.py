"""Deterministic state machine and lifecycle for Phase 5 patch execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from orion.core.swe.execution.errors import InvalidStateTransitionError


class PatchExecutionState(str, Enum):
    """Explicit lifecycle states for patch application, execution, and verification."""

    PROPOSED = "proposed"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    AUTHORIZED = "authorized"
    APPLYING = "applying"
    APPLIED = "applied"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    PARTIALLY_APPLIED = "partially_applied"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    RECOVERY_FAILED = "recovery_failed"


# Strict deterministic transition graph
VALID_TRANSITIONS: dict[PatchExecutionState, frozenset[PatchExecutionState]] = {
    PatchExecutionState.PROPOSED: frozenset(
        {
            PatchExecutionState.VALIDATED,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.VALIDATED: frozenset(
        {
            PatchExecutionState.PENDING_APPROVAL,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.PENDING_APPROVAL: frozenset(
        {
            PatchExecutionState.AUTHORIZED,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.AUTHORIZED: frozenset(
        {
            PatchExecutionState.APPLYING,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.APPLYING: frozenset(
        {
            PatchExecutionState.APPLIED,
            PatchExecutionState.PARTIALLY_APPLIED,
            PatchExecutionState.RECOVERING,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.APPLIED: frozenset(
        {
            PatchExecutionState.EXECUTING,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.EXECUTING: frozenset(
        {
            PatchExecutionState.VERIFIED,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.PARTIALLY_APPLIED: frozenset(
        {
            PatchExecutionState.RECOVERING,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.RECOVERING: frozenset(
        {
            PatchExecutionState.RECOVERED,
            PatchExecutionState.RECOVERY_FAILED,
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.RECOVERED: frozenset(
        {
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.RECOVERY_FAILED: frozenset(
        {
            PatchExecutionState.FAILED,
        }
    ),
    PatchExecutionState.VERIFIED: frozenset(),  # Terminal state
    PatchExecutionState.FAILED: frozenset(),  # Terminal state
}


@dataclass(frozen=True)
class StateTransitionRecord:
    """Immutable audit record of a state transition."""

    from_state: PatchExecutionState
    to_state: PatchExecutionState
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""


class PatchExecutionLifecycle:
    """State machine managing and auditing deterministic patch execution transitions."""

    def __init__(self, initial_state: PatchExecutionState = PatchExecutionState.PROPOSED) -> None:
        self._current_state = initial_state
        self._history: list[StateTransitionRecord] = []

    @property
    def current_state(self) -> PatchExecutionState:
        """Return the current lifecycle state."""
        return self._current_state

    @property
    def history(self) -> tuple[StateTransitionRecord, ...]:
        """Return the immutable transition history."""
        return tuple(self._history)

    def transition_to(self, new_state: PatchExecutionState, reason: str = "") -> None:
        """Transition to a new state if allowed by the deterministic transition graph.

        Raises:
            InvalidStateTransitionError: If the transition is not permitted.
        """
        allowed = VALID_TRANSITIONS.get(self._current_state, frozenset())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid state transition from '{self._current_state.value}' to "
                f"'{new_state.value}'. Allowed transitions: {[s.value for s in allowed]}"
            )

        record = StateTransitionRecord(
            from_state=self._current_state,
            to_state=new_state,
            reason=reason,
        )
        self._history.append(record)
        self._current_state = new_state

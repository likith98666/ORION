"""Deterministic state machine governing the lifecycle of an individual recovery attempt."""

from __future__ import annotations

from orion.core.swe.recovery.contracts import RecoveryAttemptState, RecoveryStateTransition
from orion.core.swe.recovery.errors import InvalidRecoveryTransitionError

VALID_RECOVERY_TRANSITIONS: dict[RecoveryAttemptState, frozenset[RecoveryAttemptState]] = {
    RecoveryAttemptState.PLANNED: frozenset(
        {
            RecoveryAttemptState.AUTHORIZED,
            RecoveryAttemptState.EXECUTING,
            RecoveryAttemptState.TERMINATED,
        }
    ),
    RecoveryAttemptState.AUTHORIZED: frozenset(
        {
            RecoveryAttemptState.EXECUTING,
            RecoveryAttemptState.TERMINATED,
        }
    ),
    RecoveryAttemptState.EXECUTING: frozenset(
        {
            RecoveryAttemptState.RETESTING,
            RecoveryAttemptState.FAILED,
            RecoveryAttemptState.ROLLED_BACK,
            RecoveryAttemptState.TERMINATED,
        }
    ),
    RecoveryAttemptState.RETESTING: frozenset(
        {
            RecoveryAttemptState.VERIFYING,
            RecoveryAttemptState.FAILED,
            RecoveryAttemptState.ROLLED_BACK,
            RecoveryAttemptState.TERMINATED,
        }
    ),
    RecoveryAttemptState.VERIFYING: frozenset(
        {
            RecoveryAttemptState.SUCCEEDED,
            RecoveryAttemptState.FAILED,
            RecoveryAttemptState.ROLLED_BACK,
            RecoveryAttemptState.TERMINATED,
        }
    ),
    RecoveryAttemptState.SUCCEEDED: frozenset(),  # Terminal
    RecoveryAttemptState.FAILED: frozenset(),  # Terminal for attempt
    RecoveryAttemptState.ROLLED_BACK: frozenset(),  # Terminal for attempt
    RecoveryAttemptState.TERMINATED: frozenset(),  # Terminal for attempt
}


class RecoveryAttemptLifecycle:
    """Audited state machine managing valid deterministic transitions for recovery attempts."""

    def __init__(
        self,
        initial_state: RecoveryAttemptState = RecoveryAttemptState.PLANNED,
    ) -> None:
        self._current_state: RecoveryAttemptState = initial_state
        self._history: list[RecoveryStateTransition] = []

    @property
    def current_state(self) -> RecoveryAttemptState:
        return self._current_state

    @property
    def history(self) -> tuple[RecoveryStateTransition, ...]:
        return tuple(self._history)

    def transition_to(
        self,
        new_state: RecoveryAttemptState,
        reason: str = "",
    ) -> None:
        """Transition to new_state if permitted by the transition graph."""
        if not isinstance(new_state, RecoveryAttemptState):
            raise TypeError("new_state must be a RecoveryAttemptState instance.")

        allowed = VALID_RECOVERY_TRANSITIONS.get(self._current_state, frozenset())
        if new_state not in allowed:
            raise InvalidRecoveryTransitionError(
                f"Invalid recovery state transition from '{self._current_state.value}' "
                f"to '{new_state.value}'. Allowed transitions: {[s.value for s in allowed]}"
            )

        transition = RecoveryStateTransition(
            from_state=self._current_state,
            to_state=new_state,
            reason=reason,
        )
        self._history.append(transition)
        self._current_state = new_state

from uuid import uuid4

import pytest

from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_execution_context import (
    RecoveryExecutionContext,
)
from orion.core.recovery.recovery_strategy import (
    RecoveryDecision,
    RecoveryStrategy,
)


def create_failure() -> Failure:
    return Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message="Primary model failed.",
    )


def create_decision() -> RecoveryDecision:
    return RecoveryDecision(
        strategy=RecoveryStrategy.CHANGE_MODEL,
        reason="An alternative model is available.",
    )


def test_context_defaults_to_initial_execution_state() -> None:
    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
    )

    assert context.attempt_number == 1
    assert context.recovery_attempt_number == 0
    assert context.failure_history == ()
    assert context.recovery_history == ()


def test_context_accepts_failure_and_recovery_history() -> None:
    failure = create_failure()
    decision = create_decision()

    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
        attempt_number=2,
        recovery_attempt_number=1,
        failure_history=(failure,),
        recovery_history=(decision,),
    )

    assert context.failure_history == (failure,)
    assert context.recovery_history == (decision,)


def test_context_rejects_invalid_task_id() -> None:
    with pytest.raises(TypeError, match="task_id must be a UUID"):
        RecoveryExecutionContext(
            task_id="invalid",
            current_execution_id=uuid4(),
        )


def test_context_rejects_invalid_execution_id() -> None:
    with pytest.raises(
        TypeError,
        match="current_execution_id must be a UUID",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id="invalid",
        )


def test_context_rejects_attempt_number_below_one() -> None:
    with pytest.raises(
        ValueError,
        match="attempt_number must be at least 1",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            attempt_number=0,
        )


def test_context_rejects_negative_recovery_attempt_number() -> None:
    with pytest.raises(
        ValueError,
        match="recovery_attempt_number cannot be negative",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            recovery_attempt_number=-1,
        )


def test_context_rejects_recovery_attempts_beyond_completed_attempts() -> None:
    with pytest.raises(
        ValueError,
        match="recovery_attempt_number cannot exceed completed attempts",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            attempt_number=2,
            recovery_attempt_number=2,
        )


def test_context_rejects_non_tuple_failure_history() -> None:
    with pytest.raises(
        TypeError,
        match="failure_history must be a tuple",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            failure_history=[create_failure()],
        )


def test_context_rejects_non_tuple_recovery_history() -> None:
    with pytest.raises(
        TypeError,
        match="recovery_history must be a tuple",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            recovery_history=[create_decision()],
        )


def test_context_rejects_invalid_failure_history_items() -> None:
    with pytest.raises(
        TypeError,
        match="failure_history must contain only Failure instances",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            failure_history=("invalid",),
        )


def test_context_rejects_invalid_recovery_history_items() -> None:
    with pytest.raises(
        TypeError,
        match="recovery_history must contain only RecoveryDecision instances",
    ):
        RecoveryExecutionContext(
            task_id=uuid4(),
            current_execution_id=uuid4(),
            recovery_history=("invalid",),
        )


def test_context_is_immutable() -> None:
    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
    )

    with pytest.raises(AttributeError):
        context.attempt_number = 2

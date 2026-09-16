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


def create_failure(
    message: str = "Primary model failed.",
) -> Failure:
    return Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message=message,
    )


def create_decision() -> RecoveryDecision:
    return RecoveryDecision(
        strategy=RecoveryStrategy.CHANGE_MODEL,
        reason="An alternative model is available.",
    )


def create_context() -> RecoveryExecutionContext:
    return RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
    )


def test_context_defaults_to_initial_execution_state() -> None:
    context = create_context()

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


def test_record_failure_appends_failure_to_history() -> None:
    context = create_context()
    failure = create_failure()

    updated_context = context.record_failure(failure)

    assert updated_context.failure_history == (failure,)
    assert updated_context.recovery_history == ()
    assert updated_context.attempt_number == 1
    assert updated_context.recovery_attempt_number == 0


def test_record_failure_preserves_existing_failure_history() -> None:
    first_failure = create_failure("First model failed.")
    second_failure = create_failure("Second model failed.")

    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
        failure_history=(first_failure,),
    )

    updated_context = context.record_failure(second_failure)

    assert updated_context.failure_history == (
        first_failure,
        second_failure,
    )


def test_record_failure_rejects_invalid_failure() -> None:
    context = create_context()

    with pytest.raises(
        TypeError,
        match="failure must be a Failure instance",
    ):
        context.record_failure("invalid")


def test_record_recovery_appends_decision_to_history() -> None:
    context = create_context()
    decision = create_decision()

    updated_context = context.record_recovery(decision)

    assert updated_context.recovery_history == (decision,)
    assert updated_context.failure_history == ()
    assert updated_context.attempt_number == 1
    assert updated_context.recovery_attempt_number == 0


def test_record_recovery_preserves_existing_recovery_history() -> None:
    first_decision = create_decision()
    second_decision = RecoveryDecision(
        strategy=RecoveryStrategy.RETRY_CURRENT_TASK,
        reason="Retry is appropriate.",
    )

    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=uuid4(),
        recovery_history=(first_decision,),
    )

    updated_context = context.record_recovery(second_decision)

    assert updated_context.recovery_history == (
        first_decision,
        second_decision,
    )


def test_record_recovery_rejects_invalid_decision() -> None:
    context = create_context()

    with pytest.raises(
        TypeError,
        match="decision must be a RecoveryDecision instance",
    ):
        context.record_recovery("invalid")


def test_create_next_attempt_increments_attempt_number() -> None:
    context = create_context()
    failure = create_failure()
    decision = create_decision()

    context = context.record_failure(failure)
    context = context.record_recovery(decision)

    next_execution_id = uuid4()

    next_context = context.create_next_attempt(
        current_execution_id=next_execution_id,
    )

    assert next_context.task_id == context.task_id
    assert next_context.current_execution_id == next_execution_id
    assert next_context.attempt_number == 2
    assert next_context.recovery_attempt_number == 1
    assert next_context.failure_history == (failure,)
    assert next_context.recovery_history == (decision,)


def test_create_next_attempt_preserves_history() -> None:
    first_failure = create_failure("First model failed.")
    second_failure = create_failure("Second model failed.")
    decision = create_decision()

    context = create_context()
    context = context.record_failure(first_failure)
    context = context.record_recovery(decision)
    context = context.create_next_attempt(
        current_execution_id=uuid4(),
    )
    context = context.record_failure(second_failure)

    assert context.failure_history == (
        first_failure,
        second_failure,
    )
    assert context.recovery_history == (decision,)
    assert context.attempt_number == 2
    assert context.recovery_attempt_number == 1


def test_create_next_attempt_requires_new_execution_id() -> None:
    context = create_context()

    with pytest.raises(
        ValueError,
        match="current_execution_id must be different from the previous execution",
    ):
        context.create_next_attempt(
            current_execution_id=context.current_execution_id,
        )


def test_create_next_attempt_rejects_invalid_execution_id() -> None:
    context = create_context()

    with pytest.raises(
        TypeError,
        match="current_execution_id must be a UUID",
    ):
        context.create_next_attempt(
            current_execution_id="invalid",
        )


def test_context_transitions_do_not_mutate_original_context() -> None:
    context = create_context()
    failure = create_failure()
    decision = create_decision()

    failure_context = context.record_failure(failure)
    recovery_context = failure_context.record_recovery(decision)
    next_context = recovery_context.create_next_attempt(
        current_execution_id=uuid4(),
    )

    assert context.attempt_number == 1
    assert context.recovery_attempt_number == 0
    assert context.failure_history == ()
    assert context.recovery_history == ()

    assert failure_context.attempt_number == 1
    assert failure_context.recovery_attempt_number == 0

    assert recovery_context.attempt_number == 1
    assert recovery_context.recovery_attempt_number == 0

    assert next_context.attempt_number == 2
    assert next_context.recovery_attempt_number == 1


def test_multiple_recovery_attempts_progress_correctly() -> None:
    context = create_context()

    first_failure = create_failure("First model failed.")
    first_decision = create_decision()

    context = context.record_failure(first_failure)
    context = context.record_recovery(first_decision)
    context = context.create_next_attempt(
        current_execution_id=uuid4(),
    )

    second_failure = create_failure("Second model failed.")
    second_decision = RecoveryDecision(
        strategy=RecoveryStrategy.RETRY_CURRENT_TASK,
        reason="Retry after transient failure.",
    )

    context = context.record_failure(second_failure)
    context = context.record_recovery(second_decision)
    context = context.create_next_attempt(
        current_execution_id=uuid4(),
    )

    assert context.attempt_number == 3
    assert context.recovery_attempt_number == 2

    assert len(context.failure_history) == 2
    assert len(context.recovery_history) == 2


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
    context = create_context()

    with pytest.raises(AttributeError):
        context.attempt_number = 2

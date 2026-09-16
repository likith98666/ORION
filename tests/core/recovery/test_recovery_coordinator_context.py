from uuid import uuid4

import pytest

from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_action import RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext


def create_failed_execution(
    failure: Failure,
) -> AgentExecution:
    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    execution.status = AgentExecutionStatus.FAILED
    execution.error_message = failure.message
    execution.failure = failure

    return execution


def test_coordinator_uses_recovery_execution_context() -> None:
    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.TIMEOUT,
            message="Execution timed out.",
        )
    )

    context = RecoveryExecutionContext.from_execution(execution)

    result = RecoveryCoordinator().handle_failure(
        execution=execution,
        execution_context=context,
    )

    assert result.action.action_type == RecoveryActionType.RETRY_TASK


def test_coordinator_uses_context_recovery_attempt_number() -> None:
    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.TIMEOUT,
            message="Execution timed out.",
        )
    )

    context = RecoveryExecutionContext(
        task_id=execution.agent_task_id,
        current_execution_id=execution.id,
        attempt_number=2,
        recovery_attempt_number=1,
        failure_history=(execution.failure,),
    )

    result = RecoveryCoordinator().handle_failure(
        execution=execution,
        execution_context=context,
        max_retries=1,
    )

    assert result.action.action_type == RecoveryActionType.ESCALATE_TO_HUMAN


def test_coordinator_rejects_context_for_different_execution() -> None:
    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Model provider failed.",
        )
    )

    different_execution = AgentExecution.create(
        agent_task_id=execution.agent_task_id,
        agent_id=uuid4(),
    )

    context = RecoveryExecutionContext.from_execution(different_execution)

    with pytest.raises(
        ValueError,
        match="does not match the failed execution",
    ):
        RecoveryCoordinator().handle_failure(
            execution=execution,
            execution_context=context,
        )


def test_coordinator_rejects_context_for_different_task() -> None:
    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Model provider failed.",
        )
    )

    context = RecoveryExecutionContext(
        task_id=uuid4(),
        current_execution_id=execution.id,
    )

    with pytest.raises(
        ValueError,
        match="does not match the execution task",
    ):
        RecoveryCoordinator().handle_failure(
            execution=execution,
            execution_context=context,
        )


def test_coordinator_rejects_invalid_execution_context() -> None:
    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Model provider failed.",
        )
    )

    with pytest.raises(
        TypeError,
        match="execution_context must be a RecoveryExecutionContext",
    ):
        RecoveryCoordinator().handle_failure(
            execution=execution,
            execution_context="invalid",  # type: ignore[arg-type]
        )

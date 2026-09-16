from uuid import uuid4

import pytest

from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext


def test_from_execution_creates_context_for_execution() -> None:
    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    context = RecoveryExecutionContext.from_execution(execution)

    assert context.task_id == execution.agent_task_id
    assert context.current_execution_id == execution.id
    assert context.attempt_number == 1
    assert context.recovery_attempt_number == 0
    assert context.failure_history == ()
    assert context.recovery_history == ()


def test_from_failed_execution_records_failure() -> None:
    failure = Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message="Model provider failed.",
    )

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )
    execution.status = AgentExecutionStatus.FAILED
    execution.failure = failure
    execution.error_message = failure.message

    context = RecoveryExecutionContext.from_execution(execution)

    assert context.failure_history == (failure,)


def test_from_execution_rejects_invalid_execution() -> None:
    with pytest.raises(
        TypeError,
        match="execution must be an AgentExecution instance",
    ):
        RecoveryExecutionContext.from_execution("invalid")  # type: ignore[arg-type]

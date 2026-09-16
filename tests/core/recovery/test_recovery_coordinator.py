from uuid import uuid4

import pytest

from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_action import RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator


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


def test_coordinator_recommends_recovery_for_failed_execution() -> None:
    coordinator = RecoveryCoordinator()

    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Model provider failed.",
        )
    )

    result = coordinator.handle_failure(
        execution=execution,
        alternative_models_available=True,
    )

    assert result.action.action_type == RecoveryActionType.CHANGE_MODEL
    assert result.failure.failure_type == FailureType.MODEL_FAILURE
    assert result.failure.message == "Model provider failed."


def test_coordinator_escalates_when_failure_is_unknown() -> None:
    coordinator = RecoveryCoordinator()

    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.UNKNOWN,
            message="Unexpected failure.",
        )
    )

    result = coordinator.handle_failure(
        execution=execution,
    )

    assert result.action.action_type == RecoveryActionType.ESCALATE_TO_HUMAN
    assert result.action.requires_human is True


def test_coordinator_rejects_non_failed_execution() -> None:
    coordinator = RecoveryCoordinator()

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    with pytest.raises(ValueError, match="failed"):
        coordinator.handle_failure(execution=execution)


def test_coordinator_rejects_missing_failure() -> None:
    coordinator = RecoveryCoordinator()

    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    execution.status = AgentExecutionStatus.FAILED
    execution.error_message = "Failure exists, but structured failure is missing."

    with pytest.raises(ValueError, match="failure"):
        coordinator.handle_failure(execution=execution)

from uuid import uuid4

import pytest

from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_action import RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_strategy import RecoveryStrategy


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

    assert result.decision.strategy == RecoveryStrategy.CHANGE_MODEL
    assert "Model provider failed." in result.decision.reason
    assert result.decision.requires_human is False


def test_coordinator_preserves_engine_decision() -> None:
    coordinator = RecoveryCoordinator()

    execution = create_failed_execution(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Provider unavailable.",
        )
    )

    result = coordinator.handle_failure(
        execution=execution,
        alternative_models_available=True,
        remaining_budget=100.0,
        remaining_time_ms=5000.0,
    )

    assert result.decision.strategy == RecoveryStrategy.CHANGE_MODEL
    assert result.action.action_type == RecoveryActionType.CHANGE_MODEL
    assert result.decision.reason.startswith("Failure classified as 'model_failure'")
    assert "Remaining budget: 100.0" in result.decision.reason
    assert "Remaining time: 5000.0 ms" in result.decision.reason


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
    assert result.decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert result.decision.requires_human is True


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

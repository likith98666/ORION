from uuid import uuid4

from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)
from orion.core.recovery.recovery_executor import RecoveryExecutor


def test_executor_rejects_invalid_action() -> None:
    executor = RecoveryExecutor()

    try:
        executor.execute("invalid")
    except TypeError:
        return

    raise AssertionError("Expected TypeError for invalid action.")


def test_executor_accepts_retry_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.RETRY_TASK,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.RETRY_TASK


def test_executor_accepts_change_agent_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_AGENT,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.CHANGE_AGENT


def test_executor_accepts_change_tool_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_TOOL,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.CHANGE_TOOL


def test_executor_accepts_change_model_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_MODEL,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.CHANGE_MODEL


def test_executor_accepts_modify_task_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.MODIFY_TASK,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.MODIFY_TASK


def test_executor_accepts_change_task_order_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_TASK_ORDER,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.CHANGE_TASK_ORDER


def test_executor_accepts_skip_task_action() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.SKIP_TASK,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.SKIP_TASK


def test_executor_accepts_human_escalation() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.ESCALATE_TO_HUMAN,
        requires_human=True,
    )

    result = executor.execute(action)

    assert result.action_type == RecoveryActionType.ESCALATE_TO_HUMAN
    assert result.requires_human is True

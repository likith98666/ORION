from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)
from orion.core.recovery.recovery_strategy import RecoveryStrategy


def test_retry_strategy_creates_retry_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.RETRY_CURRENT_TASK
    )

    assert action.action_type == RecoveryActionType.RETRY_TASK
    assert action.requires_human is False


def test_change_agent_strategy_creates_agent_change_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.CHANGE_AGENT
    )

    assert action.action_type == RecoveryActionType.CHANGE_AGENT
    assert action.requires_human is False


def test_change_tool_strategy_creates_tool_change_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.CHANGE_TOOL
    )

    assert action.action_type == RecoveryActionType.CHANGE_TOOL
    assert action.requires_human is False


def test_change_model_strategy_creates_model_change_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.CHANGE_MODEL
    )

    assert action.action_type == RecoveryActionType.CHANGE_MODEL
    assert action.requires_human is False


def test_modify_task_strategy_creates_modify_task_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.MODIFY_TASK
    )

    assert action.action_type == RecoveryActionType.MODIFY_TASK
    assert action.requires_human is False


def test_change_task_order_strategy_creates_reorder_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.CHANGE_TASK_ORDER
    )

    assert action.action_type == RecoveryActionType.CHANGE_TASK_ORDER
    assert action.requires_human is False


def test_skip_strategy_creates_skip_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.SKIP_NONESSENTIAL_TASK
    )

    assert action.action_type == RecoveryActionType.SKIP_TASK
    assert action.requires_human is False


def test_human_escalation_creates_human_action() -> None:
    action = RecoveryAction.from_strategy(
        RecoveryStrategy.ESCALATE_TO_HUMAN
    )

    assert action.action_type == RecoveryActionType.ESCALATE_TO_HUMAN
    assert action.requires_human is True


def test_action_rejects_invalid_strategy() -> None:
    try:
        RecoveryAction.from_strategy("invalid")
    except TypeError:
        return

    raise AssertionError("Expected TypeError for invalid strategy.")

import pytest

from orion.core.recovery.recovery_strategy import (
    RecoveryDecision,
    RecoveryStrategy,
)


@pytest.mark.parametrize("strategy", list(RecoveryStrategy))
def test_recovery_strategy_supports_all_defined_strategies(
    strategy: RecoveryStrategy,
) -> None:
    decision = RecoveryDecision(
        strategy=strategy,
        reason="Recovery required.",
        requires_human=strategy == RecoveryStrategy.ESCALATE_TO_HUMAN,
    )

    assert decision.strategy == strategy
    assert decision.reason == "Recovery required."


def test_recovery_decision_is_immutable() -> None:
    decision = RecoveryDecision(
        strategy=RecoveryStrategy.RETRY_CURRENT_TASK,
        reason="Temporary failure.",
        requires_human=False,
    )

    with pytest.raises(AttributeError):
        decision.reason = "Changed"  # type: ignore[misc]


def test_recovery_decision_rejects_empty_reason() -> None:
    with pytest.raises(ValueError, match="reason cannot be empty"):
        RecoveryDecision(
            strategy=RecoveryStrategy.RETRY_CURRENT_TASK,
            reason="   ",
            requires_human=False,
        )


def test_recovery_decision_rejects_reason_over_5000_characters() -> None:
    with pytest.raises(ValueError, match="5,000 characters"):
        RecoveryDecision(
            strategy=RecoveryStrategy.RETRY_CURRENT_TASK,
            reason="x" * 5001,
            requires_human=False,
        )


def test_recovery_decision_normalizes_reason() -> None:
    decision = RecoveryDecision(
        strategy=RecoveryStrategy.CHANGE_MODEL,
        reason="  Model provider failed.  ",
        requires_human=False,
    )

    assert decision.reason == "Model provider failed."


def test_escalation_can_require_human_intervention() -> None:
    decision = RecoveryDecision(
        strategy=RecoveryStrategy.ESCALATE_TO_HUMAN,
        reason="Automatic recovery is unsafe.",
        requires_human=True,
    )

    assert decision.requires_human is True

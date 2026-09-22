import pytest

from orion.core.recovery.failure_classifier import FailureClassifier
from orion.core.recovery.failures import FailureType
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.recovery.recovery_strategy import RecoveryStrategy


@pytest.fixture
def engine() -> RecoveryEngine:
    return RecoveryEngine()


@pytest.fixture
def classifier() -> FailureClassifier:
    return FailureClassifier()


@pytest.mark.parametrize(
    ("failure_type", "expected_strategy"),
    [
        (FailureType.AGENT_FAILURE, RecoveryStrategy.CHANGE_AGENT),
        (FailureType.MODEL_FAILURE, RecoveryStrategy.CHANGE_MODEL),
        (FailureType.TOOL_FAILURE, RecoveryStrategy.CHANGE_TOOL),
        (
            FailureType.DEPENDENCY_FAILURE,
            RecoveryStrategy.CHANGE_TASK_ORDER,
        ),
        (FailureType.INVALID_INPUT, RecoveryStrategy.MODIFY_TASK),
        (
            FailureType.CONSTRAINT_VIOLATION,
            RecoveryStrategy.MODIFY_TASK,
        ),
        (FailureType.SECURITY_BLOCK, RecoveryStrategy.ESCALATE_TO_HUMAN),
        (FailureType.BUDGET_EXCEEDED, RecoveryStrategy.CHANGE_MODEL),
        (FailureType.TIMEOUT, RecoveryStrategy.RETRY_CURRENT_TASK),
        (
            FailureType.VERIFICATION_FAILURE,
            RecoveryStrategy.MODIFY_TASK,
        ),
        (FailureType.UNKNOWN, RecoveryStrategy.ESCALATE_TO_HUMAN),
    ],
)
def test_selects_strategy_for_failure_type(
    engine: RecoveryEngine,
    failure_type: FailureType,
    expected_strategy: RecoveryStrategy,
) -> None:

    decision = engine.decide(
        failure=__import__(
            "orion.core.recovery.failures",
            fromlist=["Failure"],
        ).Failure(
            failure_type=failure_type,
            message="Execution failed.",
        )
    )

    assert decision.strategy == expected_strategy


def test_security_block_requires_human_intervention(
    engine: RecoveryEngine,
) -> None:
    from orion.core.recovery.failures import Failure

    decision = engine.decide(
        Failure(
            failure_type=FailureType.SECURITY_BLOCK,
            message="Unsafe action blocked.",
        )
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_unknown_failure_requires_human_intervention(
    engine: RecoveryEngine,
) -> None:
    from orion.core.recovery.failures import Failure

    decision = engine.decide(
        Failure(
            failure_type=FailureType.UNKNOWN,
            message="Unexpected failure.",
        )
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_normal_recovery_does_not_require_human(
    engine: RecoveryEngine,
) -> None:
    from orion.core.recovery.failures import Failure

    decision = engine.decide(
        Failure(
            failure_type=FailureType.MODEL_FAILURE,
            message="Model provider failed.",
        )
    )

    assert decision.strategy == RecoveryStrategy.CHANGE_MODEL
    assert decision.requires_human is False


def test_decision_contains_failure_reason(
    engine: RecoveryEngine,
) -> None:
    from orion.core.recovery.failures import Failure

    failure = Failure(
        failure_type=FailureType.TIMEOUT,
        message="Agent execution timed out.",
    )

    decision = engine.decide(failure)

    assert "Agent execution timed out." in decision.reason


def test_engine_rejects_invalid_failure_input(
    engine: RecoveryEngine,
) -> None:
    with pytest.raises(TypeError, match="Failure"):
        engine.decide("invalid failure")  # type: ignore[arg-type]

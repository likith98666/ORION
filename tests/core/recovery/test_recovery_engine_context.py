from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_context import RecoveryContext
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.recovery.recovery_strategy import RecoveryStrategy


def test_timeout_retries_when_retries_remain() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.TIMEOUT, "Agent timed out."),
        RecoveryContext(retry_count=1, max_retries=3),
    )

    assert decision.strategy == RecoveryStrategy.RETRY_CURRENT_TASK
    assert decision.requires_human is False


def test_timeout_does_not_retry_when_retry_limit_is_reached() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.TIMEOUT, "Agent timed out."),
        RecoveryContext(retry_count=3, max_retries=3),
    )

    assert decision.strategy != RecoveryStrategy.RETRY_CURRENT_TASK


def test_model_failure_changes_model_when_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.MODEL_FAILURE, "Model failed."),
        RecoveryContext(alternative_models_available=True),
    )

    assert decision.strategy == RecoveryStrategy.CHANGE_MODEL


def test_model_failure_escalates_when_no_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.MODEL_FAILURE, "Model failed."),
        RecoveryContext(alternative_models_available=False),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_tool_failure_changes_tool_when_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.TOOL_FAILURE, "Tool failed."),
        RecoveryContext(alternative_tools_available=True),
    )

    assert decision.strategy == RecoveryStrategy.CHANGE_TOOL


def test_tool_failure_escalates_when_no_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.TOOL_FAILURE, "Tool failed."),
        RecoveryContext(alternative_tools_available=False),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_agent_failure_changes_agent_when_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.AGENT_FAILURE, "Agent failed."),
        RecoveryContext(alternative_agents_available=True),
    )

    assert decision.strategy == RecoveryStrategy.CHANGE_AGENT


def test_agent_failure_escalates_when_no_alternative_exists() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.AGENT_FAILURE, "Agent failed."),
        RecoveryContext(alternative_agents_available=False),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_budget_exceeded_does_not_retry() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.BUDGET_EXCEEDED, "Budget exhausted."),
        RecoveryContext(
            alternative_models_available=True,
            remaining_budget=0.0,
        ),
    )

    assert decision.strategy != RecoveryStrategy.RETRY_CURRENT_TASK


def test_security_block_always_escalates() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.SECURITY_BLOCK, "Unsafe operation blocked."),
        RecoveryContext(
            alternative_agents_available=True,
            alternative_tools_available=True,
            alternative_models_available=True,
        ),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_unknown_failure_escalates() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.UNKNOWN, "Unexpected failure."),
        RecoveryContext(
            alternative_agents_available=True,
            alternative_tools_available=True,
            alternative_models_available=True,
        ),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True


def test_verification_failure_retries_when_retries_remain() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.VERIFICATION_FAILURE, "Output missing requirements."),
        RecoveryContext(retry_count=0, max_retries=3),
    )

    assert decision.strategy == RecoveryStrategy.RETRY_CURRENT_TASK
    assert decision.requires_human is False


def test_verification_failure_changes_model_when_retries_exhausted() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.VERIFICATION_FAILURE, "Output missing requirements."),
        RecoveryContext(
            retry_count=3,
            max_retries=3,
            alternative_models_available=True,
        ),
    )

    assert decision.strategy == RecoveryStrategy.CHANGE_MODEL
    assert decision.requires_human is False


def test_verification_failure_escalates_when_retries_exhausted_and_no_alternative_model() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        Failure(FailureType.VERIFICATION_FAILURE, "Output missing requirements."),
        RecoveryContext(
            retry_count=3,
            max_retries=3,
            alternative_models_available=False,
        ),
    )

    assert decision.strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
    assert decision.requires_human is True

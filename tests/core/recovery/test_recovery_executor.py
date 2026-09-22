from orion.config.model_config import ModelConfig
from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)
from orion.core.recovery.recovery_executor import (
    RecoveryExecutionResult,
    RecoveryExecutor,
)


def test_change_model_requires_an_alternative_model() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_MODEL,
    )

    result = executor.execute(
        action,
        model_config=ModelConfig(provider_name="primary"),
        alternative_model_configs=(),
    )

    assert isinstance(result, RecoveryExecutionResult)
    assert result.action == action
    assert result.applied is False
    assert result.selected_model is None
    assert "alternative model" in result.message.lower()


def test_change_model_selects_an_alternative_model() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_MODEL,
    )

    primary = ModelConfig(provider_name="primary")
    alternative = ModelConfig(provider_name="alternate")

    result = executor.execute(
        action,
        model_config=primary,
        alternative_model_configs=(alternative,),
    )

    assert isinstance(result, RecoveryExecutionResult)
    assert result.action == action
    assert result.applied is True
    assert result.selected_model == alternative
    assert result.message


def test_change_model_does_not_return_the_current_model() -> None:
    executor = RecoveryExecutor()

    action = RecoveryAction(
        action_type=RecoveryActionType.CHANGE_MODEL,
    )

    primary = ModelConfig(provider_name="primary")
    same_model = ModelConfig(provider_name="primary")
    alternative = ModelConfig(provider_name="alternate")

    result = executor.execute(
        action,
        model_config=primary,
        alternative_model_configs=(same_model, alternative),
    )

    assert isinstance(result, RecoveryExecutionResult)
    assert result.applied is True
    assert result.selected_model == alternative

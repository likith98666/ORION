from dataclasses import dataclass

from orion.config.model_config import ModelConfig

from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)


@dataclass(frozen=True)
class RecoveryExecutionResult:
    """Outcome of applying a recovery action."""

    action: RecoveryAction
    applied: bool
    selected_model: ModelConfig | None = None
    message: str = ""


class RecoveryExecutor:
    """Executes validated recovery actions."""

    def execute(
        self,
        action: RecoveryAction,
        *,
        model_config: ModelConfig | None = None,
        alternative_model_configs: tuple[ModelConfig, ...] = (),
    ) -> RecoveryExecutionResult:
        """Execute a recovery action and return its structured outcome."""

        if not isinstance(action, RecoveryAction):
            raise TypeError(
                "action must be a RecoveryAction instance."
            )

        if action.action_type == RecoveryActionType.CHANGE_MODEL:
            return self._change_model(
                action=action,
                model_config=model_config,
                alternative_model_configs=alternative_model_configs,
            )

        handlers = {
            RecoveryActionType.RETRY_TASK: self._retry_task,
            RecoveryActionType.CHANGE_AGENT: self._change_agent,
            RecoveryActionType.CHANGE_TOOL: self._change_tool,
            RecoveryActionType.MODIFY_TASK: self._modify_task,
            RecoveryActionType.CHANGE_TASK_ORDER: self._change_task_order,
            RecoveryActionType.SKIP_TASK: self._skip_task,
            RecoveryActionType.ESCALATE_TO_HUMAN: self._escalate_to_human,
        }

        return handlers[action.action_type](action)

    def _retry_task(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Task retry requested.",
        )

    def _change_agent(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Agent change requested.",
        )

    def _change_tool(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Tool change requested.",
        )

    def _change_model(
        self,
        action: RecoveryAction,
        model_config: ModelConfig | None,
        alternative_model_configs: tuple[ModelConfig, ...],
    ) -> RecoveryExecutionResult:
        if model_config is None:
            return RecoveryExecutionResult(
                action=action,
                applied=False,
                message="Current model configuration is required for model recovery.",
            )

        for alternative in alternative_model_configs:
            if alternative.provider_name != model_config.provider_name:
                return RecoveryExecutionResult(
                    action=action,
                    applied=True,
                    selected_model=alternative,
                    message=(
                        f"Changed model from '{model_config.provider_name}' "
                        f"to '{alternative.provider_name}'."
                    ),
                )

        return RecoveryExecutionResult(
            action=action,
            applied=False,
            message="No alternative model configuration is available.",
        )

    def _modify_task(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Task modification requested.",
        )

    def _change_task_order(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Task-order change requested.",
        )

    def _skip_task(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Task skip requested.",
        )

    def _escalate_to_human(
        self,
        action: RecoveryAction,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            action=action,
            applied=True,
            message="Human escalation requested.",
        )

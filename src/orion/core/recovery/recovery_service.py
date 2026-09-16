from orion.config.model_config import ModelConfig
from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.executions import AgentExecution
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)
from orion.core.recovery.recovery_executor import RecoveryExecutor


class RecoveryService:
    """Coordinates concrete recovery operations for failed agent tasks."""

    def __init__(
        self,
        agent_task_service: AgentTaskService,
        agent_executor: AgentExecutor,
        recovery_executor: RecoveryExecutor | None = None,
    ) -> None:
        self._agent_task_service = agent_task_service
        self._agent_executor = agent_executor
        self._recovery_executor = recovery_executor or RecoveryExecutor()

    def retry_task(
        self,
        task: AgentTask,
        model_config: ModelConfig,
    ) -> AgentExecution:
        """Retry a failed agent task using a new execution attempt."""

        if not isinstance(task, AgentTask):
            raise TypeError("task must be an AgentTask instance.")

        if not isinstance(model_config, ModelConfig):
            raise TypeError("model_config must be a ModelConfig instance.")

        if task.status != AgentTaskStatus.FAILED:
            raise ValueError(
                "Only failed agent tasks can be retried."
            )

        updated_task = self._agent_task_service.update_status(
            task.id,
            AgentTaskStatus.RUNNING,
        )

        return self._agent_executor.execute(
            updated_task,
            model_config,
        )

    def change_model_and_retry(
        self,
        task: AgentTask,
        current_model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...] = (),
    ) -> AgentExecution:
        """Change the model configuration and retry a failed agent task."""

        if not isinstance(task, AgentTask):
            raise TypeError("task must be an AgentTask instance.")

        if not isinstance(current_model_config, ModelConfig):
            raise TypeError(
                "current_model_config must be a ModelConfig instance."
            )

        if not isinstance(alternative_model_configs, tuple):
            raise TypeError(
                "alternative_model_configs must be a tuple of ModelConfig instances."
            )

        if any(
            not isinstance(config, ModelConfig)
            for config in alternative_model_configs
        ):
            raise TypeError(
                "alternative_model_configs must contain only ModelConfig instances."
            )

        if task.status != AgentTaskStatus.FAILED:
            raise ValueError(
                "Only failed agent tasks can change model and retry."
            )

        action = RecoveryAction(
            action_type=RecoveryActionType.CHANGE_MODEL,
        )

        recovery_result = self._recovery_executor.execute(
            action,
            model_config=current_model_config,
            alternative_model_configs=alternative_model_configs,
        )

        if not recovery_result.applied:
            raise ValueError(
                "Model recovery could not be applied: "
                f"{recovery_result.message}"
            )

        if recovery_result.selected_model is None:
            raise ValueError(
                "Model recovery was applied without selecting an alternative model."
            )

        return self.retry_task(
            task,
            recovery_result.selected_model,
        )

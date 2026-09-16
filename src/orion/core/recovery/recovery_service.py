from orion.config.model_config import ModelConfig
from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.executions import AgentExecution
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


class RecoveryService:
    """Coordinates concrete recovery operations for failed agent tasks."""

    def __init__(
        self,
        agent_task_service: AgentTaskService,
        agent_executor: AgentExecutor,
    ) -> None:
        self._agent_task_service = agent_task_service
        self._agent_executor = agent_executor

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

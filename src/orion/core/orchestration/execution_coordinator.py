from orion.config.model_config import ModelConfig
from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


class ExecutionCoordinator:
    """Coordinates execution of assigned agent tasks."""

    def __init__(self, agent_executor: AgentExecutor) -> None:
        self._agent_executor = agent_executor

    def execute_task(
        self,
        task: AgentTask,
        model_config: ModelConfig,
    ) -> AgentExecution:
        if task.status != AgentTaskStatus.ASSIGNED:
            raise ValueError(
                f"Only assigned agent tasks can be executed: {task.status.value}"
            )

        return self._agent_executor.execute(task, model_config)

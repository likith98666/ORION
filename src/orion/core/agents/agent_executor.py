from orion.config.model_config import ModelConfig
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.repository import AgentRepository
from orion.core.agents.tasks import AgentTask
from orion.models.contracts import ModelRequest
from orion.models.runtime.runtime import ModelRuntime


class AgentExecutor:
    """Executes an assigned ORION agent task using the model runtime."""

    def __init__(
        self,
        agent_repository: AgentRepository,
        execution_service: AgentExecutionService,
        model_runtime: ModelRuntime,
    ) -> None:
        self._agent_repository = agent_repository
        self._execution_service = execution_service
        self._model_runtime = model_runtime

    def execute(
        self,
        task: AgentTask,
        model_config: ModelConfig,
    ):
        """Execute an assigned agent task."""

        if task.assigned_agent_id is None:
            raise ValueError(
                f"Agent task '{task.id}' has no assigned agent."
            )

        agent = self._agent_repository.get(task.assigned_agent_id)

        if agent is None:
            raise ValueError(
                f"Agent '{task.assigned_agent_id}' was not found."
            )

        execution = self._execution_service.create_execution(
            agent_task_id=task.id,
            agent_id=agent.id,
        )

        request = ModelRequest(
            prompt=task.description,
            metadata={
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "agent_task_id": str(task.id),
            },
        )

        try:
            response = self._model_runtime.generate(
                model_config,
                request,
            )

            return self._execution_service.complete_execution(
                execution_id=execution.id,
                output=response.text,
                model_name=response.model_name,
                provider_name=response.provider_name,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
            )

        except Exception as exc:
            return self._execution_service.fail_execution(
                execution_id=execution.id,
                error_message=str(exc),
            )

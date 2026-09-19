from typing import Any

from orion.config.model_config import ModelConfig
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.repository import AgentRepository
from orion.core.agents.tasks import AgentTask
from orion.core.recovery.failure_classifier import FailureClassifier
from orion.core.tools.executor import ToolExecutionResult, ToolExecutor
from orion.models.contracts import ModelRequest
from orion.models.runtime.runtime import ModelRuntime


class AgentExecutor:
    """Executes assigned ORION agent tasks and authorized tool calls."""

    def __init__(
        self,
        agent_repository: AgentRepository,
        execution_service: AgentExecutionService,
        model_runtime: ModelRuntime,
        failure_classifier: FailureClassifier | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self._agent_repository = agent_repository
        self._execution_service = execution_service
        self._model_runtime = model_runtime
        self._failure_classifier = (
            failure_classifier or FailureClassifier()
        )
        self._tool_executor = tool_executor

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
            failure = self._failure_classifier.classify(exc)

            return self._execution_service.fail_execution(
                execution_id=execution.id,
                failure=failure,
            )

    def execute_tool(
        self,
        task: AgentTask,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a registered tool on behalf of an assigned agent."""

        if self._tool_executor is None:
            raise ValueError(
                "Tool executor is required for tool execution."
            )

        if task.assigned_agent_id is None:
            raise ValueError(
                f"Agent task '{task.id}' has no assigned agent."
            )

        agent = self._agent_repository.get(task.assigned_agent_id)

        if agent is None:
            raise ValueError(
                f"Agent '{task.assigned_agent_id}' was not found."
            )

        return self._tool_executor.execute(
            agent=agent,
            tool_name=tool_name,
            arguments=arguments,
        )

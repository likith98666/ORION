import uuid

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.executions import AgentExecutionStatus
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.repository import AgentRepository
from orion.core.agents.tasks import AgentTask
from orion.models.contracts import ModelResponse
from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.runtime.runtime import ModelRuntime
from orion.models.selection.selector import ModelSelector


class InMemoryAgentRepository(AgentRepository):
    def __init__(self) -> None:
        self._agents: dict[uuid.UUID, Agent] = {}

    def save(self, agent: Agent) -> None:
        self._agents[agent.id] = agent

    def get(self, agent_id: uuid.UUID) -> Agent | None:
        return self._agents.get(agent_id)

    def delete(self, agent_id: uuid.UUID) -> None:
        self._agents.pop(agent_id, None)

    def list_all(self) -> list[Agent]:
        return list(self._agents.values())


class FailingModelRuntime:
    def generate(self, config, request):
        raise RuntimeError("Model provider unavailable.")


class FixedModelRuntime:
    def generate(self, config, request):
        return ModelResponse(
            text="Fixed response.",
            model_name="test-model",
            provider_name="test-provider",
            input_tokens=42,
            output_tokens=21,
            latency_ms=123.4,
        )


def create_runtime() -> ModelRuntime:
    registry = ModelProviderRegistry()

    registry.register(MockModelProvider())
    registry.register(AlternateModelProvider())

    selector = ModelSelector(registry)

    return ModelRuntime(selector)


def create_agent() -> Agent:
    return Agent.create(
        name="Researcher",
        description="Research specialist.",
        capabilities=frozenset({AgentCapability.RESEARCH}),
        permission_policy=AgentPermissionPolicy.create(frozenset()),
    )


def create_executor(
    model_runtime=None,
) -> tuple[
    AgentExecutor,
    InMemoryAgentRepository,
    InMemoryAgentExecutionRepository,
]:
    agent_repository = InMemoryAgentRepository()

    execution_repository = InMemoryAgentExecutionRepository()
    execution_service = AgentExecutionService(execution_repository)

    executor = AgentExecutor(
        agent_repository=agent_repository,
        execution_service=execution_service,
        model_runtime=model_runtime or create_runtime(),
    )

    return (
        executor,
        agent_repository,
        execution_repository,
    )


def create_task(agent: Agent) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid.uuid4(),
        description="Research autonomous agents.",
        required_capability=AgentCapability.RESEARCH,
    )
    task.assigned_agent_id = agent.id

    return task


def test_executor_completes_assigned_task() -> None:
    (
        executor,
        agent_repository,
        execution_repository,
    ) = create_executor()

    agent = create_agent()
    agent_repository.save(agent)

    task = create_task(agent)

    execution = executor.execute(
        task,
        ModelConfig(provider_name="mock"),
    )

    assert execution.status == AgentExecutionStatus.COMPLETED
    assert execution.output == ("Mock response for: Research autonomous agents.")
    assert execution.agent_task_id == task.id
    assert execution.agent_id == agent.id
    assert execution.provider_name == "mock"
    assert execution.model_name == "mock-model"
    assert execution.completed_at is not None

    stored = execution_repository.get(execution.id)

    assert stored is not None
    assert stored.status == AgentExecutionStatus.COMPLETED


def test_executor_propagates_model_metadata() -> None:
    (
        executor,
        agent_repository,
        _,
    ) = create_executor(FixedModelRuntime())

    agent = create_agent()
    agent_repository.save(agent)

    task = create_task(agent)

    execution = executor.execute(
        task,
        ModelConfig(provider_name="test"),
    )

    assert execution.status == AgentExecutionStatus.COMPLETED
    assert execution.output == "Fixed response."
    assert execution.model_name == "test-model"
    assert execution.provider_name == "test-provider"
    assert execution.input_tokens == 42
    assert execution.output_tokens == 21
    assert execution.latency_ms == 123.4


def test_executor_marks_execution_failed_when_model_fails() -> None:
    (
        executor,
        agent_repository,
        execution_repository,
    ) = create_executor(FailingModelRuntime())

    agent = create_agent()
    agent_repository.save(agent)

    task = create_task(agent)

    execution = executor.execute(
        task,
        ModelConfig(provider_name="test"),
    )

    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error_message == "Model provider unavailable."
    assert execution.completed_at is not None

    stored = execution_repository.get(execution.id)

    assert stored is not None
    assert stored.status == AgentExecutionStatus.FAILED


def test_executor_requires_assigned_agent() -> None:
    (
        executor,
        _,
        _,
    ) = create_executor()

    task = AgentTask.create(
        task_id=uuid.uuid4(),
        description="Research autonomous agents.",
        required_capability=AgentCapability.RESEARCH,
    )

    with pytest.raises(ValueError, match="no assigned agent"):
        executor.execute(
            task,
            ModelConfig(provider_name="mock"),
        )


def test_executor_fails_when_agent_does_not_exist() -> None:
    (
        executor,
        _,
        _,
    ) = create_executor()

    task = AgentTask.create(
        task_id=uuid.uuid4(),
        description="Research autonomous agents.",
        required_capability=AgentCapability.RESEARCH,
    )
    task.assigned_agent_id = uuid.uuid4()

    with pytest.raises(ValueError, match="was not found"):
        executor.execute(
            task,
            ModelConfig(provider_name="mock"),
        )


def test_executor_preserves_classified_model_failure() -> None:
    class ModelFailureRuntime:
        def generate(self, config, request):
            from orion.models.errors import ModelProviderUnavailableError

            raise ModelProviderUnavailableError("Model provider unavailable.")

    (
        executor,
        agent_repository,
        _,
    ) = create_executor(ModelFailureRuntime())

    agent = create_agent()
    agent_repository.save(agent)

    task = create_task(agent)

    execution = executor.execute(
        task,
        ModelConfig(provider_name="test"),
    )

    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.failure is not None
    assert execution.failure.failure_type.value == "model_failure"
    assert execution.failure.message == "Model provider unavailable."

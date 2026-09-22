from __future__ import annotations

import uuid

from orion.config.model_config import ModelConfig
from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.repository import AgentRepository
from orion.core.agents.tasks import AgentTask
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.models import (
    MemoryImportance,
    MemoryRecord,
    MemoryType,
)
from orion.core.memory.retrieval_models import MemoryRetrievalResult
from orion.models.contracts import ModelResponse


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


class CapturingModelRuntime:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, config, request):
        self.requests.append(request)
        return ModelResponse(
            text="Captured response.",
            model_name="test-model",
            provider_name="test-provider",
            input_tokens=10,
            output_tokens=5,
            latency_ms=20.0,
        )


def create_agent() -> Agent:
    return Agent.create(
        name="Researcher",
        description="Research specialist.",
        capabilities=frozenset({AgentCapability.RESEARCH}),
        permission_policy=AgentPermissionPolicy.create(frozenset()),
    )


def create_task(agent: Agent) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid.uuid4(),
        description="Research autonomous agents.",
        required_capability=AgentCapability.RESEARCH,
    )
    task.assigned_agent_id = agent.id
    return task


def create_context(task: AgentTask, agent: Agent) -> ExecutionMemoryContext:
    memory = MemoryRecord.create(
        memory_type=MemoryType.LONG_TERM,
        content="Previous research found that hierarchical planning improves task decomposition.",
        importance=MemoryImportance.HIGH,
        task_id=task.id,
        agent_id=agent.id,
        source_execution_id=uuid.uuid4(),
    )

    result = MemoryRetrievalResult(
        memory=memory,
        score=0.91,
        reasons=("semantic_match",),
    )

    return ExecutionMemoryContext(
        task_id=task.id,
        agent_id=agent.id,
        memories=(result,),
    )


def test_executor_formats_memory_context_into_model_request() -> None:
    agent_repository = InMemoryAgentRepository()
    execution_repository = InMemoryAgentExecutionRepository()
    execution_service = AgentExecutionService(execution_repository)
    runtime = CapturingModelRuntime()

    executor = AgentExecutor(
        agent_repository=agent_repository,
        execution_service=execution_service,
        model_runtime=runtime,
    )

    agent = create_agent()
    agent_repository.save(agent)

    task = create_task(agent)
    memory_context = create_context(task, agent)

    execution = executor.execute(
        task,
        ModelConfig(provider_name="test"),
        memory_context=memory_context,
    )

    assert execution.output == "Captured response."
    assert len(runtime.requests) == 1

    request = runtime.requests[0]

    assert "Research autonomous agents." in request.prompt
    assert "RETRIEVED DATA" in request.prompt
    assert "hierarchical planning improves task decomposition" in request.prompt
    assert "Source execution:" in request.prompt
    assert request.metadata is not None
    assert request.metadata["memory_context_count"] == 1

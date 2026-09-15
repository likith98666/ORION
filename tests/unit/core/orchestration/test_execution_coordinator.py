from uuid import uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.agents.capabilities import AgentCapability
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator


class FakeAgentExecutor:
    def __init__(self, execution: AgentExecution) -> None:
        self.execution = execution
        self.calls: list[tuple[AgentTask, ModelConfig]] = []

    def execute(
        self,
        task: AgentTask,
        model_config: ModelConfig,
    ) -> AgentExecution:
        self.calls.append((task, model_config))
        return self.execution


def create_assigned_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Execute the assigned task.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def test_execute_task_delegates_to_agent_executor() -> None:
    task = create_assigned_task()
    model_config = ModelConfig(provider_name="mock")

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    executor = FakeAgentExecutor(execution)
    coordinator = ExecutionCoordinator(executor)

    result = coordinator.execute_task(task, model_config)

    assert result is execution
    assert executor.calls == [(task, model_config)]


def test_execute_task_preserves_model_config() -> None:
    task = create_assigned_task()
    model_config = ModelConfig(
        provider_name="mock",
        temperature=0.7,
        max_tokens=512,
    )

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    executor = FakeAgentExecutor(execution)
    coordinator = ExecutionCoordinator(executor)

    coordinator.execute_task(task, model_config)

    assert executor.calls[0][1] is model_config


def test_execute_task_rejects_pending_task() -> None:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Execute the assigned task.",
        required_capability=AgentCapability.REASONING,
    )
    model_config = ModelConfig(provider_name="mock")

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=uuid4(),
    )

    executor = FakeAgentExecutor(execution)
    coordinator = ExecutionCoordinator(executor)

    with pytest.raises(
        ValueError,
        match="Only assigned agent tasks can be executed",
    ):
        coordinator.execute_task(task, model_config)

    assert executor.calls == []


def test_execute_task_rejects_completed_task() -> None:
    task = create_assigned_task()
    task.status = AgentTaskStatus.COMPLETED

    model_config = ModelConfig(provider_name="mock")

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    executor = FakeAgentExecutor(execution)
    coordinator = ExecutionCoordinator(executor)

    with pytest.raises(
        ValueError,
        match="Only assigned agent tasks can be executed",
    ):
        coordinator.execute_task(task, model_config)

    assert executor.calls == []

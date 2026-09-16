from uuid import UUID, uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.recovery.recovery_service import RecoveryService


class FakeAgentTaskService:
    def __init__(self, task: AgentTask) -> None:
        self.task = task
        self.status_updates: list[tuple[UUID, AgentTaskStatus]] = []

    def get_task(self, task_id):
        if task_id == self.task.id:
            return self.task
        return None

    def update_status(self, task_id, status):
        self.status_updates.append((task_id, status))
        self.task.status = status
        return self.task


class FakeAgentExecutor:
    def __init__(self, execution: AgentExecution) -> None:
        self.execution = execution
        self.calls: list[tuple[AgentTask, ModelConfig]] = []

    def execute(self, task: AgentTask, model_config: ModelConfig) -> AgentExecution:
        self.calls.append((task, model_config))
        return self.execution


def create_failed_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Retry this task.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.FAILED
    return task


def test_retry_task_moves_failed_task_to_running() -> None:
    task = create_failed_task()

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    agent_task_service = FakeAgentTaskService(task)
    agent_executor = FakeAgentExecutor(execution)
    service = RecoveryService(
        agent_task_service=agent_task_service,
        agent_executor=agent_executor,
    )

    model_config = ModelConfig(provider_name="mock")

    result = service.retry_task(
        task=task,
        model_config=model_config,
    )

    assert task.status == AgentTaskStatus.RUNNING
    assert agent_task_service.status_updates == [
        (task.id, AgentTaskStatus.RUNNING),
    ]
    assert agent_executor.calls == [(task, model_config)]
    assert result is execution


def test_retry_task_rejects_non_failed_task() -> None:
    task = create_failed_task()
    task.status = AgentTaskStatus.COMPLETED

    agent_task_service = FakeAgentTaskService(task)
    agent_executor = FakeAgentExecutor(
        AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
    )

    service = RecoveryService(
        agent_task_service=agent_task_service,
        agent_executor=agent_executor,
    )

    with pytest.raises(
        ValueError,
        match="Only failed agent tasks can be retried",
    ):
        service.retry_task(
            task=task,
            model_config=ModelConfig(provider_name="mock"),
        )

    assert agent_task_service.status_updates == []
    assert agent_executor.calls == []

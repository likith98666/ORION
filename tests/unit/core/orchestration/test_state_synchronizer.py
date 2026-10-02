from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.state_synchronizer import StateSynchronizer
from orion.core.planning.steps import PlanStep, PlanStepStatus


def create_agent_task(
    plan_step_id,
) -> AgentTask:
    return AgentTask.create(
        task_id=uuid4(),
        plan_step_id=plan_step_id,
        description="Research the topic.",
        required_capability=AgentCapability.RESEARCH,
    )


def create_plan_step() -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="Research the topic.",
        required_capability=AgentCapability.RESEARCH,
    )


def create_execution(
    agent_task_id,
    status: AgentExecutionStatus,
) -> AgentExecution:
    return AgentExecution(
        id=uuid4(),
        agent_task_id=agent_task_id,
        agent_id=uuid4(),
        status=status,
    )


class FakeAgentTaskService:
    def __init__(self, task: AgentTask | None = None) -> None:
        self.task = task
        self.updated_statuses = []

    def get_task(self, task_id):
        if self.task is not None and self.task.id == task_id:
            return self.task
        return None

    def update_status(self, task_id, status):
        self.updated_statuses.append((task_id, status))
        self.task.status = status
        return self.task


def create_synchronizer(task_service):
    return StateSynchronizer(task_service=task_service)


def test_completed_execution_completes_agent_task_and_plan_step():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.RUNNING
    execution = create_execution(task.id, AgentExecutionStatus.COMPLETED)

    synchronizer = create_synchronizer(FakeAgentTaskService(task))

    synchronizer.synchronize(execution, [plan_step])

    assert task.status == AgentTaskStatus.COMPLETED
    assert plan_step.status == PlanStepStatus.COMPLETED


def test_failed_execution_fails_agent_task_and_plan_step():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.RUNNING
    execution = create_execution(task.id, AgentExecutionStatus.FAILED)

    synchronizer = create_synchronizer(FakeAgentTaskService(task))

    synchronizer.synchronize(execution, [plan_step])

    assert task.status == AgentTaskStatus.FAILED
    assert plan_step.status == PlanStepStatus.FAILED


def test_running_execution_marks_agent_task_and_plan_step_running():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.ASSIGNED
    execution = create_execution(task.id, AgentExecutionStatus.RUNNING)

    synchronizer = create_synchronizer(FakeAgentTaskService(task))

    synchronizer.synchronize(execution, [plan_step])

    assert task.status == AgentTaskStatus.RUNNING
    assert plan_step.status == PlanStepStatus.RUNNING


def test_missing_agent_task_raises_error():
    plan_step = create_plan_step()
    execution = create_execution(uuid4(), AgentExecutionStatus.COMPLETED)

    synchronizer = create_synchronizer(FakeAgentTaskService())

    with pytest.raises(ValueError, match="Agent task not found"):
        synchronizer.synchronize(execution, [plan_step])


def test_missing_plan_step_raises_error():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.RUNNING
    execution = create_execution(task.id, AgentExecutionStatus.COMPLETED)

    synchronizer = create_synchronizer(FakeAgentTaskService(task))

    with pytest.raises(ValueError, match="Plan step not found"):
        synchronizer.synchronize(execution, [])


def test_synchronization_preserves_unrelated_plan_steps():
    target_step = create_plan_step()
    unrelated_step = create_plan_step()

    task = create_agent_task(target_step.id)
    task.status = AgentTaskStatus.RUNNING
    execution = create_execution(task.id, AgentExecutionStatus.COMPLETED)

    synchronizer = create_synchronizer(FakeAgentTaskService(task))

    synchronizer.synchronize(
        execution,
        [target_step, unrelated_step],
    )

    assert target_step.status == PlanStepStatus.COMPLETED
    assert unrelated_step.status == PlanStepStatus.PENDING


def test_synchronize_completed_task_is_idempotent():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.COMPLETED
    execution = create_execution(task.id, AgentExecutionStatus.COMPLETED)

    fake_service = FakeAgentTaskService(task)
    synchronizer = create_synchronizer(fake_service)

    synchronizer.synchronize(execution, [plan_step])

    assert task.status == AgentTaskStatus.COMPLETED
    assert plan_step.status == PlanStepStatus.COMPLETED
    assert fake_service.updated_statuses == []


def test_synchronize_failed_task_is_idempotent():
    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.FAILED
    execution = create_execution(task.id, AgentExecutionStatus.FAILED)

    fake_service = FakeAgentTaskService(task)
    synchronizer = create_synchronizer(fake_service)

    synchronizer.synchronize(execution, [plan_step])

    assert task.status == AgentTaskStatus.FAILED
    assert plan_step.status == PlanStepStatus.FAILED
    assert fake_service.updated_statuses == []


def test_synchronize_completed_task_with_failed_execution_is_rejected():
    from orion.core.agents.memory_task_repository import InMemoryAgentTaskRepository
    from orion.core.agents.task_service import AgentTaskService

    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.COMPLETED

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    real_task_service = AgentTaskService(task_repo)

    execution = create_execution(task.id, AgentExecutionStatus.FAILED)
    synchronizer = create_synchronizer(real_task_service)

    with pytest.raises(ValueError, match="Invalid agent task transition: completed -> failed"):
        synchronizer.synchronize(execution, [plan_step])


def test_synchronize_completed_task_with_running_execution_is_rejected():
    from orion.core.agents.memory_task_repository import InMemoryAgentTaskRepository
    from orion.core.agents.task_service import AgentTaskService

    plan_step = create_plan_step()
    task = create_agent_task(plan_step.id)
    task.status = AgentTaskStatus.COMPLETED

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    real_task_service = AgentTaskService(task_repo)

    execution = create_execution(task.id, AgentExecutionStatus.RUNNING)
    synchronizer = create_synchronizer(real_task_service)

    with pytest.raises(ValueError, match="Invalid agent task transition: completed -> running"):
        synchronizer.synchronize(execution, [plan_step])

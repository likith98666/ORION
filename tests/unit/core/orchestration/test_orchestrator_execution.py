from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTaskStatus
from orion.core.orchestration.execution_loop import ExecutionLoopResult
from orion.core.orchestration.orchestrator import (
    OrchestrationExecutionResult,
    Orchestrator,
)
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep


class FakeAgentTaskService:
    def __init__(self) -> None:
        self.created_tasks = []

    def create_task(
        self,
        task_id,
        plan_step_id,
        description,
        required_capability,
    ):
        task = type(
            "FakeAgentTask",
            (),
            {
                "id": uuid4(),
                "task_id": task_id,
                "plan_step_id": plan_step_id,
                "description": description,
                "required_capability": required_capability,
                "status": AgentTaskStatus.PENDING,
                "assigned_agent_id": uuid4(),
            },
        )()

        self.created_tasks.append(task)

        return task


class FakeAssignmentService:
    def __init__(self) -> None:
        self.assigned_tasks = []

    def assign_task(self, task):
        task.status = AgentTaskStatus.ASSIGNED
        self.assigned_tasks.append(task)
        return task


class FakeExecutionLoop:
    def __init__(self) -> None:
        self.calls = []

    def execute(
        self,
        tasks,
        model_config,
        plan_steps=None,
        alternative_model_configs=(),
    ):
        self.calls.append(
            {
                "tasks": tasks,
                "model_config": model_config,
                "plan_steps": plan_steps,
                "alternative_model_configs": alternative_model_configs,
            }
        )

        executions = tuple(
            AgentExecution.create(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
            )
            for task in tasks
        )

        return ExecutionLoopResult(
            executions=executions,
        )


def create_step() -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="Research the topic.",
        required_capability=AgentCapability.RESEARCH,
    )


def create_orchestrator(execution_loop=None):
    return Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=FakeAgentTaskService(),
        assignment_service=FakeAssignmentService(),
        execution_loop=execution_loop,
    )


def test_orchestrate_and_execute_runs_ready_tasks():
    execution_loop = FakeExecutionLoop()
    orchestrator = create_orchestrator(execution_loop)

    task_id = uuid4()
    model_config = ModelConfig(provider_name="mock")

    result = orchestrator.orchestrate_and_execute(
        task_id=task_id,
        plan_steps=[create_step()],
        model_config=model_config,
    )

    assert isinstance(result, OrchestrationExecutionResult)
    assert len(result.orchestration.agent_tasks) == 1
    assert len(result.execution.executions) == 1


def test_orchestrate_and_execute_passes_assigned_tasks_to_execution_loop():
    execution_loop = FakeExecutionLoop()
    orchestrator = create_orchestrator(execution_loop)

    model_config = ModelConfig(provider_name="mock")

    result = orchestrator.orchestrate_and_execute(
        task_id=uuid4(),
        plan_steps=[create_step()],
        model_config=model_config,
    )

    call = execution_loop.calls[0]

    assert call["tasks"] == list(result.orchestration.agent_tasks)
    assert call["model_config"] is model_config


def test_orchestrate_and_execute_passes_plan_steps_to_execution_loop():
    execution_loop = FakeExecutionLoop()
    orchestrator = create_orchestrator(execution_loop)

    plan_steps = [create_step()]
    model_config = ModelConfig(provider_name="mock")

    result = orchestrator.orchestrate_and_execute(
        task_id=uuid4(),
        plan_steps=plan_steps,
        model_config=model_config,
    )

    assert result.execution.executions
    assert len(execution_loop.calls) == 1
    assert execution_loop.calls[0]["plan_steps"] == plan_steps


def test_orchestrate_and_execute_preserves_orchestration_result():
    execution_loop = FakeExecutionLoop()
    orchestrator = create_orchestrator(execution_loop)

    result = orchestrator.orchestrate_and_execute(
        task_id=uuid4(),
        plan_steps=[create_step()],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.orchestration.ready_steps[0].description == (
        "Research the topic."
    )


def test_orchestrate_and_execute_returns_empty_execution_for_no_ready_tasks():
    execution_loop = FakeExecutionLoop()
    orchestrator = create_orchestrator(execution_loop)

    completed_step = create_step()
    completed_step.status = completed_step.status.COMPLETED

    result = orchestrator.orchestrate_and_execute(
        task_id=uuid4(),
        plan_steps=[completed_step],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.orchestration.agent_tasks == ()
    assert result.execution.executions == ()
    assert execution_loop.calls[0]["tasks"] == []
    assert execution_loop.calls[0]["plan_steps"] == [completed_step]


def test_orchestrate_and_execute_requires_execution_loop():
    orchestrator = create_orchestrator()

    with __import__("pytest").raises(
        ValueError,
        match="Execution loop is required",
    ):
        orchestrator.orchestrate_and_execute(
            task_id=uuid4(),
            plan_steps=[create_step()],
            model_config=ModelConfig(provider_name="mock"),
        )

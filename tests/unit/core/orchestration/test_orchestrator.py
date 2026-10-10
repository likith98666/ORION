from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.tasks import AgentTaskStatus
from orion.core.orchestration.execution_loop import ExecutionLoopResult
from orion.core.orchestration.orchestrator import Orchestrator
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep, PlanStepStatus


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
        self.created_tasks.append(
            (
                task_id,
                plan_step_id,
                description,
                required_capability,
            )
        )

        return type(
            "FakeAgentTask",
            (),
            {
                "id": uuid4(),
                "task_id": task_id,
                "plan_step_id": plan_step_id,
                "description": description,
                "required_capability": required_capability,
                "status": AgentTaskStatus.PENDING,
                "assigned_agent_id": None,
            },
        )()


class FakeAssignmentService:
    def __init__(self) -> None:
        self.assigned_tasks = []

    def assign_task(self, task):
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

        return ExecutionLoopResult(executions=())


def create_step(
    plan_id,
    order,
    description,
    capability,
    dependencies=frozenset(),
):
    return PlanStep.create(
        plan_id=plan_id,
        order=order,
        description=description,
        required_capability=capability,
        dependencies=dependencies,
    )


def test_orchestrator_creates_tasks_for_ready_steps():
    task_id = uuid4()
    plan_id = uuid4()

    first_step = create_step(
        plan_id=plan_id,
        order=1,
        description="Research the topic.",
        capability=AgentCapability.RESEARCH,
    )

    second_step = create_step(
        plan_id=plan_id,
        order=2,
        description="Analyze the findings.",
        capability=AgentCapability.DATA_ANALYSIS,
    )

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=FakeAgentTaskService(),
        assignment_service=FakeAssignmentService(),
    )

    result = orchestrator.orchestrate(
        task_id=task_id,
        plan_steps=[
            first_step,
            second_step,
        ],
    )

    assert len(result.ready_steps) == 2
    assert len(result.agent_tasks) == 2


def test_orchestrator_creates_tasks_only_for_ready_steps():
    task_id = uuid4()
    plan_id = uuid4()

    completed_step = create_step(
        plan_id=plan_id,
        order=1,
        description="Research the topic.",
        capability=AgentCapability.RESEARCH,
    )
    completed_step.status = PlanStepStatus.COMPLETED

    dependent_step = create_step(
        plan_id=plan_id,
        order=2,
        description="Analyze the findings.",
        capability=AgentCapability.DATA_ANALYSIS,
        dependencies=frozenset({completed_step.id}),
    )

    pending_step = create_step(
        plan_id=plan_id,
        order=3,
        description="Write the report.",
        capability=AgentCapability.WRITING,
        dependencies=frozenset({dependent_step.id}),
    )

    task_service = FakeAgentTaskService()
    assignment_service = FakeAssignmentService()

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=task_service,
        assignment_service=assignment_service,
    )

    result = orchestrator.orchestrate(
        task_id=task_id,
        plan_steps=[
            completed_step,
            dependent_step,
            pending_step,
        ],
    )

    assert len(result.ready_steps) == 1
    assert result.ready_steps[0].id == dependent_step.id
    assert len(result.agent_tasks) == 1

    assert task_service.created_tasks[0] == (
        task_id,
        dependent_step.id,
        "Analyze the findings.",
        AgentCapability.DATA_ANALYSIS,
    )


def test_orchestrator_passes_task_and_step_identity_to_task_service():
    task_id = uuid4()
    plan_id = uuid4()

    step = create_step(
        plan_id=plan_id,
        order=1,
        description="Perform research.",
        capability=AgentCapability.RESEARCH,
    )

    task_service = FakeAgentTaskService()
    assignment_service = FakeAssignmentService()

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=task_service,
        assignment_service=assignment_service,
    )

    orchestrator.orchestrate(
        task_id=task_id,
        plan_steps=[step],
    )

    assert task_service.created_tasks == [
        (
            task_id,
            step.id,
            "Perform research.",
            AgentCapability.RESEARCH,
        )
    ]


def test_orchestrator_assigns_every_created_task():
    task_id = uuid4()
    plan_id = uuid4()

    first_step = create_step(
        plan_id=plan_id,
        order=1,
        description="Research.",
        capability=AgentCapability.RESEARCH,
    )

    second_step = create_step(
        plan_id=plan_id,
        order=2,
        description="Analyze.",
        capability=AgentCapability.DATA_ANALYSIS,
    )

    task_service = FakeAgentTaskService()
    assignment_service = FakeAssignmentService()

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=task_service,
        assignment_service=assignment_service,
    )

    result = orchestrator.orchestrate(
        task_id=task_id,
        plan_steps=[
            first_step,
            second_step,
        ],
    )

    assert len(assignment_service.assigned_tasks) == 2
    assert assignment_service.assigned_tasks == list(result.agent_tasks)


def test_orchestrator_returns_empty_result_when_no_steps_are_ready():
    task_id = uuid4()
    plan_id = uuid4()

    completed_step = create_step(
        plan_id=plan_id,
        order=1,
        description="Already completed.",
        capability=AgentCapability.RESEARCH,
    )
    completed_step.status = PlanStepStatus.COMPLETED

    task_service = FakeAgentTaskService()
    assignment_service = FakeAssignmentService()

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=task_service,
        assignment_service=assignment_service,
    )

    result = orchestrator.orchestrate(
        task_id=task_id,
        plan_steps=[completed_step],
    )

    assert result.ready_steps == ()
    assert result.agent_tasks == ()
    assert task_service.created_tasks == []
    assert assignment_service.assigned_tasks == []


def test_orchestrate_and_execute_passes_plan_steps_to_execution_loop():
    task_id = uuid4()
    plan_id = uuid4()

    step = create_step(
        plan_id=plan_id,
        order=1,
        description="Research the topic.",
        capability=AgentCapability.RESEARCH,
    )

    task_service = FakeAgentTaskService()
    assignment_service = FakeAssignmentService()
    execution_loop = FakeExecutionLoop()

    model_config = ModelConfig(
        provider_name="test-provider",
        temperature=0.0,
    )

    orchestrator = Orchestrator(
        scheduler=PlanScheduler(),
        agent_task_service=task_service,
        assignment_service=assignment_service,
        execution_loop=execution_loop,
    )

    result = orchestrator.orchestrate_and_execute(
        task_id=task_id,
        plan_steps=[step],
        model_config=model_config,
    )

    assert result.execution.executions == ()

    assert len(execution_loop.calls) == 1
    assert execution_loop.calls[0]["tasks"] == list(result.orchestration.agent_tasks)
    assert execution_loop.calls[0]["model_config"] is model_config
    assert execution_loop.calls[0]["plan_steps"] == [step]

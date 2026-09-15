from uuid import uuid4

from orion.core.agents.assignment_service import AgentAssignmentService
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTaskStatus
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep, PlanStepStatus
from orion.core.orchestration.orchestrator import Orchestrator


class FakeAgentTaskService:
    def __init__(self) -> None:
        self.created_tasks = []

    def create_task(
        self,
        task_id,
        description,
        required_capability,
    ):
        self.created_tasks.append(
            (
                task_id,
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
        [
            first_step,
            second_step,
        ]
    )

    assert len(result.ready_steps) == 2
    assert len(result.agent_tasks) == 2


def test_orchestrator_creates_tasks_only_for_ready_steps():
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
        [
            completed_step,
            dependent_step,
            pending_step,
        ]
    )

    assert len(result.ready_steps) == 1
    assert result.ready_steps[0].id == dependent_step.id
    assert len(result.agent_tasks) == 1

    assert task_service.created_tasks[0] == (
        plan_id,
        "Analyze the findings.",
        AgentCapability.DATA_ANALYSIS,
    )


def test_orchestrator_passes_step_information_to_task_service():
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

    orchestrator.orchestrate([step])

    assert task_service.created_tasks == [
        (
            plan_id,
            "Perform research.",
            AgentCapability.RESEARCH,
        )
    ]


def test_orchestrator_assigns_every_created_task():
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
        [
            first_step,
            second_step,
        ]
    )

    assert len(assignment_service.assigned_tasks) == 2
    assert assignment_service.assigned_tasks == list(
        result.agent_tasks
    )


def test_orchestrator_returns_empty_result_when_no_steps_are_ready():
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

    result = orchestrator.orchestrate([completed_step])

    assert result.ready_steps == ()
    assert result.agent_tasks == ()
    assert task_service.created_tasks == []
    assert assignment_service.assigned_tasks == []
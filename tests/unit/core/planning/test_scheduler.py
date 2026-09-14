from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep, PlanStepStatus


def create_step(
    order: int,
    description: str,
    dependencies: frozenset | None = None,
) -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=order,
        description=description,
        required_capability=AgentCapability.RESEARCH,
        dependencies=dependencies,
    )


def test_step_without_dependencies_is_ready() -> None:
    scheduler = PlanScheduler()

    step = create_step(
        order=1,
        description="Collect information",
    )

    ready_steps = scheduler.get_ready_steps([step])

    assert ready_steps == [step]


def test_step_with_completed_dependency_is_ready() -> None:
    scheduler = PlanScheduler()

    dependency = create_step(
        order=1,
        description="Collect information",
    )
    dependency.status = PlanStepStatus.COMPLETED

    step = create_step(
        order=2,
        description="Analyze information",
        dependencies=frozenset({dependency.id}),
    )

    ready_steps = scheduler.get_ready_steps(
        [dependency, step]
    )

    assert ready_steps == [step]


def test_step_with_pending_dependency_is_not_ready() -> None:
    scheduler = PlanScheduler()

    dependency = create_step(
        order=1,
        description="Collect information",
    )

    step = create_step(
        order=2,
        description="Analyze information",
        dependencies=frozenset({dependency.id}),
    )

    ready_steps = scheduler.get_ready_steps(
        [dependency, step]
    )

    assert ready_steps == [dependency]


def test_step_with_multiple_dependencies_requires_all_completed() -> None:
    scheduler = PlanScheduler()

    first_dependency = create_step(
        order=1,
        description="Collect first dataset",
    )

    second_dependency = create_step(
        order=2,
        description="Collect second dataset",
    )
    second_dependency.status = PlanStepStatus.COMPLETED

    step = create_step(
        order=3,
        description="Combine datasets",
        dependencies=frozenset(
            {
                first_dependency.id,
                second_dependency.id,
            }
        ),
    )

    ready_steps = scheduler.get_ready_steps(
        [first_dependency, second_dependency, step]
    )

    assert ready_steps == [first_dependency]


def test_step_becomes_ready_after_all_dependencies_complete() -> None:
    scheduler = PlanScheduler()

    first_dependency = create_step(
        order=1,
        description="Collect first dataset",
    )
    first_dependency.status = PlanStepStatus.COMPLETED

    second_dependency = create_step(
        order=2,
        description="Collect second dataset",
    )
    second_dependency.status = PlanStepStatus.COMPLETED

    step = create_step(
        order=3,
        description="Combine datasets",
        dependencies=frozenset(
            {
                first_dependency.id,
                second_dependency.id,
            }
        ),
    )

    ready_steps = scheduler.get_ready_steps(
        [first_dependency, second_dependency, step]
    )

    assert ready_steps == [step]


def test_completed_steps_are_not_returned_as_ready() -> None:
    scheduler = PlanScheduler()

    step = create_step(
        order=1,
        description="Collect information",
    )
    step.status = PlanStepStatus.COMPLETED

    assert scheduler.get_ready_steps([step]) == []


def test_running_steps_are_not_returned_as_ready() -> None:
    scheduler = PlanScheduler()

    step = create_step(
        order=1,
        description="Collect information",
    )
    step.status = PlanStepStatus.RUNNING

    assert scheduler.get_ready_steps([step]) == []


def test_ready_steps_are_sorted_by_order() -> None:
    scheduler = PlanScheduler()

    first_step = create_step(
        order=1,
        description="First step",
    )

    second_step = create_step(
        order=2,
        description="Second step",
    )

    third_step = create_step(
        order=3,
        description="Third step",
    )

    ready_steps = scheduler.get_ready_steps(
        [third_step, first_step, second_step]
    )

    assert ready_steps == [
        first_step,
        second_step,
        third_step,
    ]


def test_empty_step_list_returns_empty_list() -> None:
    scheduler = PlanScheduler()

    assert scheduler.get_ready_steps([]) == []
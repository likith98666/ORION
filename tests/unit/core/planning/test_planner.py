from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.planner import PlannedStep, Planner


def test_create_plan_creates_plan_from_planned_steps() -> None:
    planner = Planner()

    task_id = uuid4()

    steps = [
        PlannedStep(
            order=1,
            description="Collect market information",
            required_capability=AgentCapability.RESEARCH,
        ),
        PlannedStep(
            order=2,
            description="Analyze market information",
            required_capability=AgentCapability.DATA_ANALYSIS,
            dependencies=frozenset({1}),
        ),
    ]

    plan, plan_steps = planner.create_plan(
        task_id=task_id,
        objective="Research the AI education market",
        steps=steps,
    )

    assert plan.task_id == task_id
    assert plan.objective == "Research the AI education market"
    assert len(plan_steps) == 2


def test_create_plan_preserves_step_order_and_details() -> None:
    planner = Planner()

    plan, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Analyze a dataset",
        steps=[
            PlannedStep(
                order=1,
                description="Load the dataset",
                required_capability=AgentCapability.DATA_ANALYSIS,
            ),
            PlannedStep(
                order=2,
                description="Analyze the dataset",
                required_capability=AgentCapability.DATA_ANALYSIS,
                dependencies=frozenset({1}),
            ),
        ],
    )

    assert plan_steps[0].order == 1
    assert plan_steps[0].description == "Load the dataset"
    assert (
        plan_steps[0].required_capability
        == AgentCapability.DATA_ANALYSIS
    )

    assert plan_steps[1].order == 2
    assert plan_steps[1].description == "Analyze the dataset"
    assert (
        plan_steps[1].required_capability
        == AgentCapability.DATA_ANALYSIS
    )


def test_create_plan_resolves_dependencies_by_step_order() -> None:
    planner = Planner()

    _, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Research and analyze information",
        steps=[
            PlannedStep(
                order=1,
                description="Research information",
                required_capability=AgentCapability.RESEARCH,
            ),
            PlannedStep(
                order=2,
                description="Analyze information",
                required_capability=AgentCapability.DATA_ANALYSIS,
                dependencies=frozenset({1}),
            ),
        ],
    )

    first_step = plan_steps[0]
    second_step = plan_steps[1]

    assert second_step.dependencies == frozenset({first_step.id})


def test_create_plan_resolves_multiple_dependencies() -> None:
    planner = Planner()

    _, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Combine multiple research sources",
        steps=[
            PlannedStep(
                order=1,
                description="Research source one",
                required_capability=AgentCapability.RESEARCH,
            ),
            PlannedStep(
                order=2,
                description="Research source two",
                required_capability=AgentCapability.RESEARCH,
            ),
            PlannedStep(
                order=3,
                description="Combine research findings",
                required_capability=AgentCapability.REASONING,
                dependencies=frozenset({1, 2}),
            ),
        ],
    )

    first_step = plan_steps[0]
    second_step = plan_steps[1]
    third_step = plan_steps[2]

    assert third_step.dependencies == frozenset(
        {
            first_step.id,
            second_step.id,
        }
    )


def test_create_plan_step_without_dependencies_has_empty_dependencies() -> None:
    planner = Planner()

    _, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Perform research",
        steps=[
            PlannedStep(
                order=1,
                description="Research information",
                required_capability=AgentCapability.RESEARCH,
            ),
        ],
    )

    assert plan_steps[0].dependencies == frozenset()


def test_create_plan_ignores_unknown_dependency_orders() -> None:
    planner = Planner()

    _, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Perform research",
        steps=[
            PlannedStep(
                order=1,
                description="Research information",
                required_capability=AgentCapability.RESEARCH,
                dependencies=frozenset({999}),
            ),
        ],
    )

    assert plan_steps[0].dependencies == frozenset()


def test_create_plan_supports_empty_step_list() -> None:
    planner = Planner()

    plan, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Create an empty plan",
        steps=[],
    )

    assert plan.objective == "Create an empty plan"
    assert plan_steps == []


def test_create_plan_preserves_plan_id_on_all_steps() -> None:
    planner = Planner()

    plan, plan_steps = planner.create_plan(
        task_id=uuid4(),
        objective="Execute multiple steps",
        steps=[
            PlannedStep(
                order=1,
                description="First step",
                required_capability=AgentCapability.RESEARCH,
            ),
            PlannedStep(
                order=2,
                description="Second step",
                required_capability=AgentCapability.WRITING,
            ),
        ],
    )

    assert all(step.plan_id == plan.id for step in plan_steps)


def test_create_plan_rejects_invalid_step_order() -> None:
    planner = Planner()

    with pytest.raises(ValueError, match="Plan step order must be at least 1"):
        planner.create_plan(
            task_id=uuid4(),
            objective="Invalid plan",
            steps=[
                PlannedStep(
                    order=0,
                    description="Invalid step",
                    required_capability=AgentCapability.RESEARCH,
                ),
            ],
        )
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.models import (
    GeneratedPlan,
    GeneratedPlanStep,
)


def test_generated_plan_step_stores_step_details() -> None:
    step = GeneratedPlanStep(
        order=1,
        description="Research the target market",
        required_capability=AgentCapability.RESEARCH,
        dependencies=frozenset(),
    )

    assert step.order == 1
    assert step.description == "Research the target market"
    assert step.required_capability == AgentCapability.RESEARCH
    assert step.dependencies == frozenset()


def test_generated_plan_step_stores_dependencies() -> None:
    step = GeneratedPlanStep(
        order=3,
        description="Analyze research findings",
        required_capability=AgentCapability.DATA_ANALYSIS,
        dependencies=frozenset({1, 2}),
    )

    assert step.dependencies == frozenset({1, 2})


def test_generated_plan_create_creates_valid_plan() -> None:
    task_id = uuid4()

    steps = (
        GeneratedPlanStep(
            order=1,
            description="Research information",
            required_capability=AgentCapability.RESEARCH,
        ),
    )

    plan = GeneratedPlan.create(
        task_id=task_id,
        objective="Research the AI market",
        steps=steps,
    )

    assert plan.task_id == task_id
    assert plan.objective == "Research the AI market"
    assert plan.steps == steps


def test_generated_plan_strips_objective_whitespace() -> None:
    plan = GeneratedPlan.create(
        task_id=uuid4(),
        objective="  Research the AI market  ",
        steps=(
            GeneratedPlanStep(
                order=1,
                description="Research information",
                required_capability=AgentCapability.RESEARCH,
            ),
        ),
    )

    assert plan.objective == "Research the AI market"


def test_generated_plan_rejects_empty_objective() -> None:
    with pytest.raises(
        ValueError,
        match="Generated plan objective cannot be empty.",
    ):
        GeneratedPlan.create(
            task_id=uuid4(),
            objective="   ",
            steps=(
                GeneratedPlanStep(
                    order=1,
                    description="Research information",
                    required_capability=AgentCapability.RESEARCH,
                ),
            ),
        )


def test_generated_plan_rejects_objective_over_10000_characters() -> None:
    with pytest.raises(
        ValueError,
        match="Generated plan objective cannot exceed 10,000 characters.",
    ):
        GeneratedPlan.create(
            task_id=uuid4(),
            objective="x" * 10_001,
            steps=(
                GeneratedPlanStep(
                    order=1,
                    description="Research information",
                    required_capability=AgentCapability.RESEARCH,
                ),
            ),
        )


def test_generated_plan_rejects_empty_steps() -> None:
    with pytest.raises(
        ValueError,
        match="Generated plan must contain at least one step.",
    ):
        GeneratedPlan.create(
            task_id=uuid4(),
            objective="Research the AI market",
            steps=(),
        )


def test_generated_plan_preserves_multiple_steps() -> None:
    steps = (
        GeneratedPlanStep(
            order=1,
            description="Collect information",
            required_capability=AgentCapability.RESEARCH,
        ),
        GeneratedPlanStep(
            order=2,
            description="Analyze information",
            required_capability=AgentCapability.DATA_ANALYSIS,
            dependencies=frozenset({1}),
        ),
        GeneratedPlanStep(
            order=3,
            description="Write the report",
            required_capability=AgentCapability.WRITING,
            dependencies=frozenset({2}),
        ),
    )

    plan = GeneratedPlan.create(
        task_id=uuid4(),
        objective="Complete a research report",
        steps=steps,
    )

    assert len(plan.steps) == 3
    assert plan.steps[0].order == 1
    assert plan.steps[1].dependencies == frozenset({1})
    assert plan.steps[2].dependencies == frozenset({2})


def test_generated_plan_is_immutable() -> None:
    plan = GeneratedPlan.create(
        task_id=uuid4(),
        objective="Research the AI market",
        steps=(
            GeneratedPlanStep(
                order=1,
                description="Research information",
                required_capability=AgentCapability.RESEARCH,
            ),
        ),
    )

    with pytest.raises(AttributeError):
        plan.objective = "Changed objective"  # type: ignore[misc]

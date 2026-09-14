from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.steps import PlanStep, PlanStepStatus


def test_create_plan_step() -> None:
    plan_id = uuid4()

    step = PlanStep.create(
        plan_id=plan_id,
        order=1,
        description="Research AI education platforms",
        required_capability=AgentCapability.RESEARCH,
    )

    assert step.plan_id == plan_id
    assert step.order == 1
    assert step.description == "Research AI education platforms"
    assert step.required_capability == AgentCapability.RESEARCH
    assert step.dependencies == frozenset()
    assert step.status == PlanStepStatus.PENDING
    assert step.id is not None


def test_create_plan_step_trims_description() -> None:
    step = PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="  Research AI platforms  ",
        required_capability=AgentCapability.RESEARCH,
    )

    assert step.description == "Research AI platforms"


def test_create_plan_step_rejects_invalid_order() -> None:
    with pytest.raises(
        ValueError,
        match="Plan step order must be at least 1",
    ):
        PlanStep.create(
            plan_id=uuid4(),
            order=0,
            description="Research AI platforms",
            required_capability=AgentCapability.RESEARCH,
        )


def test_create_plan_step_rejects_empty_description() -> None:
    with pytest.raises(
        ValueError,
        match="Plan step description cannot be empty",
    ):
        PlanStep.create(
            plan_id=uuid4(),
            order=1,
            description="   ",
            required_capability=AgentCapability.RESEARCH,
        )


def test_create_plan_step_rejects_description_over_limit() -> None:
    with pytest.raises(
        ValueError,
        match="Plan step description cannot exceed 5,000 characters",
    ):
        PlanStep.create(
            plan_id=uuid4(),
            order=1,
            description="x" * 5_001,
            required_capability=AgentCapability.RESEARCH,
        )


def test_create_plan_step_with_dependency() -> None:
    previous_step_id = uuid4()

    step = PlanStep.create(
        plan_id=uuid4(),
        order=2,
        description="Analyze the research findings",
        required_capability=AgentCapability.DATA_ANALYSIS,
        dependencies=frozenset({previous_step_id}),
    )

    assert step.dependencies == frozenset({previous_step_id})


def test_create_plan_step_with_multiple_dependencies() -> None:
    first_step_id = uuid4()
    second_step_id = uuid4()

    step = PlanStep.create(
        plan_id=uuid4(),
        order=3,
        description="Prepare the final report",
        required_capability=AgentCapability.WRITING,
        dependencies=frozenset(
            {
                first_step_id,
                second_step_id,
            }
        ),
    )

    assert step.dependencies == frozenset(
        {
            first_step_id,
            second_step_id,
        }
    )


def test_plan_step_dependencies_are_frozenset() -> None:
    dependency_id = uuid4()

    step = PlanStep.create(
        plan_id=uuid4(),
        order=2,
        description="Analyze research",
        required_capability=AgentCapability.DATA_ANALYSIS,
        dependencies=frozenset({dependency_id}),
    )

    assert isinstance(step.dependencies, frozenset)
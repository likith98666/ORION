from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.generation.models import (
    GeneratedPlan,
    GeneratedPlanStep,
)


class TestPlanGenerator(PlanGenerator):
    """Concrete test implementation of the plan generator interface."""

    def generate(
        self,
        task_id,
        objective,
    ):
        return GeneratedPlan.create(
            task_id=task_id,
            objective=objective,
            steps=(
                GeneratedPlanStep(
                    order=1,
                    description="Research the objective",
                    required_capability=AgentCapability.RESEARCH,
                ),
            ),
        )


def test_plan_generator_can_be_implemented() -> None:
    generator = TestPlanGenerator()

    task_id = uuid4()

    plan = generator.generate(
        task_id=task_id,
        objective="Research the AI market",
    )

    assert isinstance(plan, GeneratedPlan)
    assert plan.task_id == task_id
    assert plan.objective == "Research the AI market"
    assert len(plan.steps) == 1


def test_plan_generator_returns_structured_plan() -> None:
    generator = TestPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Analyze a dataset",
    )

    assert plan.steps[0].order == 1
    assert plan.steps[0].description == "Research the objective"
    assert (
        plan.steps[0].required_capability
        == AgentCapability.RESEARCH
    )


def test_plan_generator_is_abstract() -> None:
    with pytest.raises(TypeError):
        PlanGenerator()  # type: ignore[abstract]


def test_plan_generator_requires_generate_implementation() -> None:
    class IncompleteGenerator(PlanGenerator):
        pass

    with pytest.raises(TypeError):
        IncompleteGenerator()  # type: ignore[abstract]
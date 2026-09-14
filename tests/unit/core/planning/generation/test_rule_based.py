from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.models import GeneratedPlan
from orion.core.planning.generation.rule_based import RuleBasedPlanGenerator


def test_generate_research_plan() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Research the AI education market",
    )

    assert isinstance(plan, GeneratedPlan)
    assert len(plan.steps) == 3

    assert plan.steps[0].required_capability == AgentCapability.RESEARCH
    assert plan.steps[1].required_capability == AgentCapability.REASONING
    assert plan.steps[2].required_capability == AgentCapability.WRITING

    assert plan.steps[0].dependencies == frozenset()
    assert plan.steps[1].dependencies == frozenset({1})
    assert plan.steps[2].dependencies == frozenset({2})


def test_generate_investigation_plan() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Investigate competing AI platforms",
    )

    assert len(plan.steps) == 3
    assert plan.steps[0].required_capability == AgentCapability.RESEARCH


def test_generate_data_analysis_plan() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Analyze the customer dataset",
    )

    assert len(plan.steps) == 3

    assert (
        plan.steps[0].required_capability
        == AgentCapability.DATA_ANALYSIS
    )
    assert (
        plan.steps[1].required_capability
        == AgentCapability.DATA_ANALYSIS
    )
    assert plan.steps[2].required_capability == AgentCapability.WRITING

    assert plan.steps[1].dependencies == frozenset({1})
    assert plan.steps[2].dependencies == frozenset({2})


def test_generate_software_plan() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Improve the software repository",
    )

    assert len(plan.steps) == 3

    assert plan.steps[0].required_capability == AgentCapability.REASONING
    assert (
        plan.steps[1].required_capability
        == AgentCapability.CODE_EXECUTION
    )
    assert (
        plan.steps[2].required_capability
        == AgentCapability.VERIFICATION
    )

    assert plan.steps[1].dependencies == frozenset({1})
    assert plan.steps[2].dependencies == frozenset({2})


def test_generate_general_plan_for_unrecognized_objective() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Prepare a project outcome",
    )

    assert len(plan.steps) == 3

    assert plan.steps[0].required_capability == AgentCapability.REASONING
    assert plan.steps[1].required_capability == AgentCapability.REASONING
    assert plan.steps[2].required_capability == AgentCapability.WRITING


def test_generate_strips_objective_whitespace() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="  Research the AI market  ",
    )

    assert plan.objective == "Research the AI market"


def test_generate_rejects_empty_objective() -> None:
    generator = RuleBasedPlanGenerator()

    with pytest.raises(
        ValueError,
        match="Plan generation objective cannot be empty.",
    ):
        generator.generate(
            task_id=uuid4(),
            objective="   ",
        )


def test_generate_preserves_task_id() -> None:
    generator = RuleBasedPlanGenerator()
    task_id = uuid4()

    plan = generator.generate(
        task_id=task_id,
        objective="Analyze a dataset",
    )

    assert plan.task_id == task_id


def test_generate_assigns_sequential_step_orders() -> None:
    generator = RuleBasedPlanGenerator()

    plan = generator.generate(
        task_id=uuid4(),
        objective="Research a topic",
    )

    assert [step.order for step in plan.steps] == [1, 2, 3]
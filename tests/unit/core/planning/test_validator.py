from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.steps import PlanStep
from orion.core.planning.validator import PlanValidator


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


def test_valid_plan() -> None:
    step_one = create_step(
        order=1,
        description="Research AI platforms",
    )

    step_two = create_step(
        order=2,
        description="Analyze research",
        dependencies=frozenset({step_one.id}),
    )

    result = PlanValidator().validate(
        [step_one, step_two]
    )

    assert result.valid is True
    assert result.errors == ()


def test_detects_duplicate_orders() -> None:
    step_one = create_step(
        order=1,
        description="Research AI platforms",
    )

    step_two = create_step(
        order=1,
        description="Analyze research",
    )

    result = PlanValidator().validate(
        [step_one, step_two]
    )

    assert result.valid is False
    assert "Duplicate plan step order: 1." in result.errors


def test_detects_missing_dependency() -> None:
    missing_step_id = uuid4()

    step = create_step(
        order=1,
        description="Analyze research",
        dependencies=frozenset({missing_step_id}),
    )

    result = PlanValidator().validate([step])

    assert result.valid is False
    assert any(
        "depends on missing step" in error
        for error in result.errors
    )


def test_detects_self_dependency() -> None:
    step = create_step(
        order=1,
        description="Research AI platforms",
    )

    step.dependencies = frozenset({step.id})

    result = PlanValidator().validate([step])

    assert result.valid is False
    assert any(
        "cannot depend on itself" in error
        for error in result.errors
    )


def test_detects_circular_dependency() -> None:
    step_one = create_step(
        order=1,
        description="Research AI platforms",
    )

    step_two = create_step(
        order=2,
        description="Analyze research",
        dependencies=frozenset({step_one.id}),
    )

    step_one.dependencies = frozenset({step_two.id})

    result = PlanValidator().validate(
        [step_one, step_two]
    )

    assert result.valid is False
    assert "Plan contains a circular dependency." in result.errors
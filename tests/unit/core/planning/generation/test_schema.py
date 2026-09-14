import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.schema import (
    PlanResponseSchema,
    PlanStepSchema,
)


def test_plan_response_from_valid_dict() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Collect relevant information",
                "required_capability": "research",
                "dependencies": [],
            },
            {
                "order": 2,
                "description": "Analyze the information",
                "required_capability": "reasoning",
                "dependencies": [1],
            },
        ]
    }

    result = PlanResponseSchema.from_dict(data)

    assert len(result.steps) == 2
    assert result.steps[0] == PlanStepSchema(
        order=1,
        description="Collect relevant information",
        required_capability=AgentCapability.RESEARCH,
        dependencies=frozenset(),
    )
    assert result.steps[1].required_capability == AgentCapability.REASONING
    assert result.steps[1].dependencies == frozenset({1})


def test_plan_response_strips_step_description() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "  Research the market  ",
                "required_capability": "research",
                "dependencies": [],
            }
        ]
    }

    result = PlanResponseSchema.from_dict(data)

    assert result.steps[0].description == "Research the market"


def test_plan_response_requires_object() -> None:
    with pytest.raises(
        ValueError,
        match="Plan response must be a JSON object.",
    ):
        PlanResponseSchema.from_dict([])  # type: ignore[arg-type]


def test_plan_response_requires_steps_list() -> None:
    with pytest.raises(
        ValueError,
        match="Plan response must contain a 'steps' list.",
    ):
        PlanResponseSchema.from_dict({})


def test_plan_response_requires_at_least_one_step() -> None:
    with pytest.raises(
        ValueError,
        match="Plan response must contain at least one step.",
    ):
        PlanResponseSchema.from_dict({"steps": []})


def test_step_must_be_object() -> None:
    with pytest.raises(
        ValueError,
        match="Each plan step must be a JSON object.",
    ):
        PlanResponseSchema.from_dict({"steps": ["invalid"]})


def test_step_order_must_be_positive_integer() -> None:
    data = {
        "steps": [
            {
                "order": 0,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [],
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step order must be greater than zero.",
    ):
        PlanResponseSchema.from_dict(data)


def test_step_orders_must_be_unique() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [],
            },
            {
                "order": 1,
                "description": "Analyze",
                "required_capability": "reasoning",
                "dependencies": [],
            },
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step orders must be unique.",
    ):
        PlanResponseSchema.from_dict(data)


def test_description_cannot_be_empty() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "   ",
                "required_capability": "research",
                "dependencies": [],
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step description cannot be empty.",
    ):
        PlanResponseSchema.from_dict(data)


def test_unknown_capability_is_rejected() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "magic_super_agent",
                "dependencies": [],
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Unknown agent capability: magic_super_agent",
    ):
        PlanResponseSchema.from_dict(data)


def test_dependencies_must_be_list() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": 1,
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step dependencies must be a list.",
    ):
        PlanResponseSchema.from_dict(data)


def test_unknown_dependency_is_rejected() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [99],
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step 1 references unknown dependency 99.",
    ):
        PlanResponseSchema.from_dict(data)


def test_self_dependency_is_rejected() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [1],
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="Plan step 1 cannot depend on itself.",
    ):
        PlanResponseSchema.from_dict(data)


def test_duplicate_dependencies_are_normalized() -> None:
    data = {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [],
            },
            {
                "order": 2,
                "description": "Analyze",
                "required_capability": "reasoning",
                "dependencies": [1, 1],
            },
        ]
    }

    result = PlanResponseSchema.from_dict(data)

    assert result.steps[1].dependencies == frozenset({1})


def test_dependency_order_can_reference_later_step() -> None:
    data = {
        "steps": [
            {
                "order": 2,
                "description": "Analyze",
                "required_capability": "reasoning",
                "dependencies": [1],
            },
            {
                "order": 1,
                "description": "Research",
                "required_capability": "research",
                "dependencies": [],
            },
        ]
    }

    result = PlanResponseSchema.from_dict(data)

    assert result.steps[0].dependencies == frozenset({1})
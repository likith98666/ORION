from uuid import uuid4

import pytest

from orion.core.planning.models import Plan, PlanStatus


def test_create_plan() -> None:
    task_id = uuid4()

    plan = Plan.create(
        task_id=task_id,
        objective="Research AI education platforms",
    )

    assert plan.task_id == task_id
    assert plan.objective == "Research AI education platforms"
    assert plan.status == PlanStatus.DRAFT
    assert plan.id is not None


def test_create_plan_trims_objective() -> None:
    plan = Plan.create(
        task_id=uuid4(),
        objective="  Research AI platforms  ",
    )

    assert plan.objective == "Research AI platforms"


def test_create_plan_rejects_empty_objective() -> None:
    with pytest.raises(ValueError, match="Plan objective cannot be empty"):
        Plan.create(
            task_id=uuid4(),
            objective="   ",
        )


def test_create_plan_rejects_objective_over_limit() -> None:
    with pytest.raises(
        ValueError,
        match="Plan objective cannot exceed 10,000 characters",
    ):
        Plan.create(
            task_id=uuid4(),
            objective="x" * 10_001,
        )

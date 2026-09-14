from uuid import uuid4

import pytest

from orion.core.planning.models import Plan
from orion.core.planning.repository import PlanRepository


def test_plan_repository_is_abstract() -> None:
    with pytest.raises(TypeError):
        PlanRepository()  # type: ignore[abstract]


def test_plan_repository_requires_save() -> None:
    class IncompleteRepository(PlanRepository):
        def get(self, plan_id):
            return None

        def delete(self, plan_id):
            pass

        def list_for_task(self, task_id):
            return []

    with pytest.raises(TypeError):
        IncompleteRepository()  # type: ignore[abstract]


def test_plan_repository_contract_can_be_implemented() -> None:
    class TestRepository(PlanRepository):
        def __init__(self) -> None:
            self.plans: dict = {}

        def save(self, plan: Plan) -> None:
            self.plans[plan.id] = plan

        def get(self, plan_id):
            return self.plans.get(plan_id)

        def delete(self, plan_id):
            self.plans.pop(plan_id, None)

        def list_for_task(self, task_id):
            return [
                plan
                for plan in self.plans.values()
                if plan.task_id == task_id
            ]

    repository = TestRepository()
    task_id = uuid4()

    plan = Plan.create(
        task_id=task_id,
        objective="Research AI platforms",
    )

    repository.save(plan)

    assert repository.get(plan.id) == plan
    assert repository.list_for_task(task_id) == [plan]

    repository.delete(plan.id)

    assert repository.get(plan.id) is None
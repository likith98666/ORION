from uuid import uuid4

from orion.core.planning.memory_repository import InMemoryPlanRepository
from orion.core.planning.models import Plan


def test_save_and_get_plan() -> None:
    repository = InMemoryPlanRepository()

    task_id = uuid4()

    plan = Plan.create(
        task_id=task_id,
        objective="Research AI education platforms",
    )

    repository.save(plan)

    assert repository.get(plan.id) == plan


def test_get_missing_plan_returns_none() -> None:
    repository = InMemoryPlanRepository()

    assert repository.get(uuid4()) is None


def test_save_replaces_existing_plan() -> None:
    repository = InMemoryPlanRepository()

    task_id = uuid4()

    plan = Plan.create(
        task_id=task_id,
        objective="Research AI platforms",
    )

    repository.save(plan)

    plan.objective = "Research AI education platforms"

    repository.save(plan)

    assert repository.get(plan.id) == plan
    assert repository.get(plan.id).objective == (
        "Research AI education platforms"
    )


def test_delete_plan() -> None:
    repository = InMemoryPlanRepository()

    plan = Plan.create(
        task_id=uuid4(),
        objective="Research AI platforms",
    )

    repository.save(plan)
    repository.delete(plan.id)

    assert repository.get(plan.id) is None


def test_delete_missing_plan_does_not_fail() -> None:
    repository = InMemoryPlanRepository()

    repository.delete(uuid4())


def test_list_plans_for_task() -> None:
    repository = InMemoryPlanRepository()

    task_id = uuid4()
    other_task_id = uuid4()

    first_plan = Plan.create(
        task_id=task_id,
        objective="Research AI platforms",
    )

    second_plan = Plan.create(
        task_id=task_id,
        objective="Analyze AI market trends",
    )

    other_plan = Plan.create(
        task_id=other_task_id,
        objective="Unrelated task",
    )

    repository.save(first_plan)
    repository.save(second_plan)
    repository.save(other_plan)

    plans = repository.list_for_task(task_id)

    assert plans == [first_plan, second_plan]


def test_list_plans_for_task_returns_empty_list_when_none_exist() -> None:
    repository = InMemoryPlanRepository()

    assert repository.list_for_task(uuid4()) == []
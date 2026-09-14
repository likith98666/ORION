from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.models import Plan
from orion.core.planning.service import PlanService
from orion.core.planning.steps import PlanStep
from orion.core.planning.validator import PlanValidator


def test_create_plan_persists_plan() -> None:
    service = PlanService()

    task_id = uuid4()

    plan = service.create_plan(
        task_id=task_id,
        objective="Research AI education platforms",
    )

    assert plan.task_id == task_id
    assert plan.objective == "Research AI education platforms"
    assert service.get_plan(plan.id) == plan


def test_create_plan_trims_objective() -> None:
    service = PlanService()

    plan = service.create_plan(
        task_id=uuid4(),
        objective="  Research AI platforms  ",
    )

    assert plan.objective == "Research AI platforms"


def test_get_missing_plan_returns_none() -> None:
    service = PlanService()

    assert service.get_plan(uuid4()) is None


def test_delete_plan() -> None:
    service = PlanService()

    plan = service.create_plan(
        task_id=uuid4(),
        objective="Research AI platforms",
    )

    service.delete_plan(plan.id)

    assert service.get_plan(plan.id) is None


def test_list_plans_for_task() -> None:
    service = PlanService()

    task_id = uuid4()

    first_plan = service.create_plan(
        task_id=task_id,
        objective="Research AI platforms",
    )

    second_plan = service.create_plan(
        task_id=task_id,
        objective="Analyze AI market trends",
    )

    plans = service.list_plans_for_task(task_id)

    assert plans == [first_plan, second_plan]


def test_validate_steps_returns_valid_result() -> None:
    service = PlanService()

    plan = Plan.create(
        task_id=uuid4(),
        objective="Research AI platforms",
    )

    step = PlanStep.create(
        plan_id=plan.id,
        order=1,
        description="Collect relevant information",
        required_capability=AgentCapability.RESEARCH,
    )

    result = service.validate_steps([step])

    assert result.valid is True
    assert result.errors == ()


def test_validate_steps_returns_validation_errors() -> None:
    service = PlanService()

    plan = Plan.create(
        task_id=uuid4(),
        objective="Research AI platforms",
    )

    first_step = PlanStep.create(
        plan_id=plan.id,
        order=1,
        description="Collect information",
        required_capability=AgentCapability.RESEARCH,
    )

    second_step = PlanStep.create(
        plan_id=plan.id,
        order=1,
        description="Analyze information",
        required_capability=AgentCapability.DATA_ANALYSIS,
    )

    result = service.validate_steps(
        [first_step, second_step]
    )

    assert result.valid is False
    assert "Duplicate plan step order: 1." in result.errors


def test_custom_repository_and_validator_are_used() -> None:
    class SpyRepository:
        def __init__(self) -> None:
            self.saved_plan: Plan | None = None

        def save(self, plan: Plan) -> None:
            self.saved_plan = plan

        def get(self, plan_id):
            if (
                self.saved_plan is not None
                and self.saved_plan.id == plan_id
            ):
                return self.saved_plan

            return None

        def delete(self, plan_id) -> None:
            self.saved_plan = None

        def list_for_task(self, task_id):
            if (
                self.saved_plan is not None
                and self.saved_plan.task_id == task_id
            ):
                return [self.saved_plan]

            return []

    class SpyValidator(PlanValidator):
        def __init__(self) -> None:
            self.called = False

        def validate(self, steps):
            self.called = True
            return super().validate(steps)

    repository = SpyRepository()
    validator = SpyValidator()

    service = PlanService(
        repository=repository,
        validator=validator,
    )

    plan = service.create_plan(
        task_id=uuid4(),
        objective="Test custom dependencies",
    )

    assert repository.saved_plan == plan

    service.validate_steps([])

    assert validator.called is True
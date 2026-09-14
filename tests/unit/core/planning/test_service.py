from uuid import UUID, uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.generation.models import (
    GeneratedPlan,
    GeneratedPlanStep,
)
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

        def get(self, plan_id: UUID) -> Plan | None:
            if (
                self.saved_plan is not None
                and self.saved_plan.id == plan_id
            ):
                return self.saved_plan

            return None

        def delete(self, plan_id: UUID) -> None:
            self.saved_plan = None

        def list_for_task(self, task_id: UUID) -> list[Plan]:
            if (
                self.saved_plan is not None
                and self.saved_plan.task_id == task_id
            ):
                return [self.saved_plan]

            return []

    class SpyValidator(PlanValidator):
        def __init__(self) -> None:
            self.called = False

        def validate(self, steps: list[PlanStep]):
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


def test_generate_plan_requires_generator() -> None:
    service = PlanService()

    with pytest.raises(
        RuntimeError,
        match="Plan generation requires a configured PlanGenerator.",
    ):
        service.generate_plan(
            task_id=uuid4(),
            objective="Research AI platforms",
        )


def test_generate_plan_creates_and_persists_plan() -> None:
    task_id = uuid4()

    class FakeGenerator(PlanGenerator):
        def generate(
            self,
            task_id: UUID,
            objective: str,
        ) -> GeneratedPlan:
            return GeneratedPlan.create(
                task_id=task_id,
                objective=objective,
                steps=(
                    GeneratedPlanStep(
                        order=1,
                        description="Collect research data",
                        required_capability=AgentCapability.RESEARCH,
                    ),
                    GeneratedPlanStep(
                        order=2,
                        description="Analyze collected data",
                        required_capability=AgentCapability.DATA_ANALYSIS,
                        dependencies=frozenset({1}),
                    ),
                ),
            )

    service = PlanService(
        generator=FakeGenerator(),
    )

    plan, steps = service.generate_plan(
        task_id=task_id,
        objective="Research AI platforms",
    )

    assert plan.task_id == task_id
    assert plan.objective == "Research AI platforms"
    assert service.get_plan(plan.id) == plan

    assert len(steps) == 2
    assert steps[0].plan_id == plan.id
    assert steps[0].order == 1
    assert steps[0].description == "Collect research data"
    assert steps[0].required_capability == AgentCapability.RESEARCH

    assert steps[1].plan_id == plan.id
    assert steps[1].order == 2
    assert steps[1].description == "Analyze collected data"
    assert steps[1].required_capability == AgentCapability.DATA_ANALYSIS
    assert steps[1].dependencies == frozenset({steps[0].id})


def test_generate_plan_passes_task_and_objective_to_generator() -> None:
    task_id = uuid4()
    received_task_id: UUID | None = None
    received_objective: str | None = None

    class SpyGenerator(PlanGenerator):
        def generate(
            self,
            task_id: UUID,
            objective: str,
        ) -> GeneratedPlan:
            nonlocal received_task_id
            nonlocal received_objective

            received_task_id = task_id
            received_objective = objective

            return GeneratedPlan.create(
                task_id=task_id,
                objective=objective,
                steps=(
                    GeneratedPlanStep(
                        order=1,
                        description="Perform research",
                        required_capability=AgentCapability.RESEARCH,
                    ),
                ),
            )

    service = PlanService(
        generator=SpyGenerator(),
    )

    service.generate_plan(
        task_id=task_id,
        objective="  Research AI platforms  ",
    )

    assert received_task_id == task_id
    assert received_objective == "Research AI platforms"


def test_generate_plan_validates_generated_steps() -> None:
    class InvalidGenerator(PlanGenerator):
        def generate(
            self,
            task_id: UUID,
            objective: str,
        ) -> GeneratedPlan:
            return GeneratedPlan.create(
                task_id=task_id,
                objective=objective,
                steps=(
                    GeneratedPlanStep(
                        order=1,
                        description="First step",
                        required_capability=AgentCapability.RESEARCH,
                    ),
                    GeneratedPlanStep(
                        order=1,
                        description="Duplicate step",
                        required_capability=AgentCapability.DATA_ANALYSIS,
                    ),
                ),
            )

    service = PlanService(
        generator=InvalidGenerator(),
    )

    with pytest.raises(
        ValueError,
        match="Generated plan failed validation.",
    ):
        service.generate_plan(
            task_id=uuid4(),
            objective="Test invalid generated plan",
        )


def test_generate_plan_preserves_multiple_dependencies() -> None:
    class DependencyGenerator(PlanGenerator):
        def generate(
            self,
            task_id: UUID,
            objective: str,
        ) -> GeneratedPlan:
            return GeneratedPlan.create(
                task_id=task_id,
                objective=objective,
                steps=(
                    GeneratedPlanStep(
                        order=1,
                        description="Research",
                        required_capability=AgentCapability.RESEARCH,
                    ),
                    GeneratedPlanStep(
                        order=2,
                        description="Analyze",
                        required_capability=AgentCapability.DATA_ANALYSIS,
                    ),
                    GeneratedPlanStep(
                        order=3,
                        description="Write report",
                        required_capability=AgentCapability.WRITING,
                        dependencies=frozenset({1, 2}),
                    ),
                ),
            )

    service = PlanService(
        generator=DependencyGenerator(),
    )

    _, steps = service.generate_plan(
        task_id=uuid4(),
        objective="Research and report",
    )

    assert steps[2].dependencies == frozenset(
        {
            steps[0].id,
            steps[1].id,
        }
    )
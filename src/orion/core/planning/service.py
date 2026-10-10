from uuid import UUID

from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.memory_repository import InMemoryPlanRepository
from orion.core.planning.models import Plan
from orion.core.planning.repository import PlanRepository
from orion.core.planning.steps import PlanStep
from orion.core.planning.validator import PlanValidationResult, PlanValidator


class PlanService:
    """Application service for managing ORION execution plans."""

    def __init__(
        self,
        repository: PlanRepository | None = None,
        validator: PlanValidator | None = None,
        generator: PlanGenerator | None = None,
    ) -> None:
        self._repository = repository or InMemoryPlanRepository()
        self._validator = validator or PlanValidator()
        self._generator = generator

    def create_plan(
        self,
        task_id: UUID,
        objective: str,
    ) -> Plan:
        """Create and persist a new execution plan."""

        plan = Plan.create(
            task_id=task_id,
            objective=objective,
        )

        self._repository.save(plan)

        return plan

    def generate_plan(
        self,
        task_id: UUID,
        objective: str,
    ) -> tuple[Plan, list[PlanStep]]:
        """Generate, validate, persist, and return an execution plan."""

        if self._generator is None:
            raise RuntimeError("Plan generation requires a configured PlanGenerator.")

        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Plan generation objective cannot be empty.")

        generated_plan = self._generator.generate(
            task_id=task_id,
            objective=cleaned_objective,
        )

        if generated_plan.task_id != task_id:
            raise ValueError("Generated plan task ID does not match the requested task ID.")

        plan = Plan.create(
            task_id=task_id,
            objective=generated_plan.objective,
        )

        step_ids_by_order: dict[int, UUID] = {}
        plan_steps: list[PlanStep] = []

        for generated_step in generated_plan.steps:
            step = PlanStep.create(
                plan_id=plan.id,
                order=generated_step.order,
                description=generated_step.description,
                required_capability=generated_step.required_capability,
            )

            step_ids_by_order[generated_step.order] = step.id
            plan_steps.append(step)

        for plan_step, generated_step in zip(
            plan_steps,
            generated_plan.steps,
            strict=True,
        ):
            try:
                plan_step.dependencies = frozenset(
                    step_ids_by_order[dependency_order]
                    for dependency_order in generated_step.dependencies
                )
            except KeyError as exc:
                raise ValueError("Generated plan contains an unknown dependency.") from exc

        validation_result = self.validate_steps(plan_steps)

        if not validation_result.valid:
            raise ValueError("Generated plan failed validation.")

        self._repository.save(plan)

        return plan, plan_steps

    def get_plan(
        self,
        plan_id: UUID,
    ) -> Plan | None:
        """Retrieve a plan by ID."""

        return self._repository.get(plan_id)

    def delete_plan(
        self,
        plan_id: UUID,
    ) -> None:
        """Delete a plan by ID."""

        self._repository.delete(plan_id)

    def list_plans_for_task(
        self,
        task_id: UUID,
    ) -> list[Plan]:
        """List all plans belonging to a task."""

        return self._repository.list_for_task(task_id)

    def validate_steps(
        self,
        steps: list[PlanStep],
    ) -> PlanValidationResult:
        """Validate the structural integrity of plan steps."""

        return self._validator.validate(steps)

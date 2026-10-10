from dataclasses import dataclass
from uuid import UUID

from orion.core.planning.steps import PlanStep


@dataclass(frozen=True)
class PlanValidationResult:
    """Result of validating an ORION execution plan."""

    valid: bool
    errors: tuple[str, ...] = ()


class PlanValidator:
    """Validates the structural integrity of an ORION execution plan."""

    def validate(
        self,
        steps: list[PlanStep],
    ) -> PlanValidationResult:
        """Validate plan steps and their dependencies."""

        errors: list[str] = []

        step_ids = {step.id for step in steps}

        errors.extend(self._validate_duplicate_orders(steps))
        errors.extend(
            self._validate_missing_dependencies(
                steps,
                step_ids,
            )
        )
        errors.extend(self._validate_self_dependencies(steps))
        errors.extend(self._validate_cycles(steps))

        return PlanValidationResult(
            valid=not errors,
            errors=tuple(errors),
        )

    def _validate_duplicate_orders(
        self,
        steps: list[PlanStep],
    ) -> list[str]:
        errors: list[str] = []
        orders: set[int] = set()

        for step in steps:
            if step.order in orders:
                errors.append(f"Duplicate plan step order: {step.order}.")
            orders.add(step.order)

        return errors

    def _validate_missing_dependencies(
        self,
        steps: list[PlanStep],
        step_ids: set[UUID],
    ) -> list[str]:
        errors: list[str] = []

        for step in steps:
            for dependency_id in step.dependencies:
                if dependency_id not in step_ids:
                    errors.append(f"Plan step {step.id} depends on missing step {dependency_id}.")

        return errors

    def _validate_self_dependencies(
        self,
        steps: list[PlanStep],
    ) -> list[str]:
        errors: list[str] = []

        for step in steps:
            if step.id in step.dependencies:
                errors.append(f"Plan step {step.id} cannot depend on itself.")

        return errors

    def _validate_cycles(
        self,
        steps: list[PlanStep],
    ) -> list[str]:
        step_map = {step.id: step for step in steps}
        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        for step in steps:
            if step.id in visited:
                continue

            if self._has_cycle(
                step.id,
                step_map,
                visiting,
                visited,
            ):
                return ["Plan contains a circular dependency."]

        return []

    def _has_cycle(
        self,
        step_id: UUID,
        step_map: dict[UUID, PlanStep],
        visiting: set[UUID],
        visited: set[UUID],
    ) -> bool:
        if step_id in visiting:
            return True

        if step_id in visited:
            return False

        visiting.add(step_id)

        step = step_map.get(step_id)

        if step is not None:
            for dependency_id in step.dependencies:
                if self._has_cycle(
                    dependency_id,
                    step_map,
                    visiting,
                    visited,
                ):
                    return True

        visiting.remove(step_id)
        visited.add(step_id)

        return False

from dataclasses import dataclass
from typing import Any

from orion.core.agents.capabilities import AgentCapability


@dataclass(frozen=True)
class PlanStepSchema:
    """Validated schema for one LLM-generated planning step."""

    order: int
    description: str
    required_capability: AgentCapability
    dependencies: frozenset[int]


@dataclass(frozen=True)
class PlanResponseSchema:
    """Validated schema for an LLM-generated execution plan."""

    steps: tuple[PlanStepSchema, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanResponseSchema":
        """Create a validated plan response schema from decoded JSON."""

        if not isinstance(data, dict):
            raise ValueError("Plan response must be a JSON object.")

        raw_steps = data.get("steps")

        if not isinstance(raw_steps, list):
            raise ValueError("Plan response must contain a 'steps' list.")

        if not raw_steps:
            raise ValueError("Plan response must contain at least one step.")

        steps: list[PlanStepSchema] = []

        for raw_step in raw_steps:
            steps.append(cls._parse_step(raw_step))

        cls._validate_orders(steps)
        cls._validate_dependencies(steps)

        return cls(steps=tuple(steps))

    @staticmethod
    def _parse_step(raw_step: Any) -> PlanStepSchema:
        """Parse and validate one generated plan step."""

        if not isinstance(raw_step, dict):
            raise ValueError("Each plan step must be a JSON object.")

        order = raw_step.get("order")
        description = raw_step.get("description")
        required_capability = raw_step.get("required_capability")
        dependencies = raw_step.get("dependencies", [])

        if not isinstance(order, int) or isinstance(order, bool):
            raise ValueError("Plan step order must be an integer.")

        if order <= 0:
            raise ValueError("Plan step order must be greater than zero.")

        if not isinstance(description, str):
            raise ValueError("Plan step description must be a string.")

        cleaned_description = description.strip()

        if not cleaned_description:
            raise ValueError("Plan step description cannot be empty.")

        if len(cleaned_description) > 5_000:
            raise ValueError("Plan step description cannot exceed 5,000 characters.")

        if not isinstance(required_capability, str):
            raise ValueError("Plan step required_capability must be a string.")

        try:
            capability = AgentCapability(required_capability)
        except ValueError as exc:
            raise ValueError(f"Unknown agent capability: {required_capability}") from exc

        if not isinstance(dependencies, list):
            raise ValueError("Plan step dependencies must be a list.")

        parsed_dependencies: set[int] = set()

        for dependency in dependencies:
            if not isinstance(dependency, int) or isinstance(dependency, bool):
                raise ValueError("Plan step dependency orders must be integers.")

            if dependency <= 0:
                raise ValueError("Plan step dependency orders must be greater than zero.")

            parsed_dependencies.add(dependency)

        return PlanStepSchema(
            order=order,
            description=cleaned_description,
            required_capability=capability,
            dependencies=frozenset(parsed_dependencies),
        )

    @staticmethod
    def _validate_orders(steps: list[PlanStepSchema]) -> None:
        """Ensure every step has a unique execution order."""

        orders = [step.order for step in steps]

        if len(orders) != len(set(orders)):
            raise ValueError("Plan step orders must be unique.")

    @staticmethod
    def _validate_dependencies(
        steps: list[PlanStepSchema],
    ) -> None:
        """Validate dependency references and prevent self-dependencies."""

        valid_orders = {step.order for step in steps}

        for step in steps:
            for dependency in step.dependencies:
                if dependency not in valid_orders:
                    raise ValueError(
                        f"Plan step {step.order} references unknown dependency {dependency}."
                    )

                if dependency == step.order:
                    raise ValueError(f"Plan step {step.order} cannot depend on itself.")

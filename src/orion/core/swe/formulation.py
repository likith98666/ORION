from dataclasses import dataclass
from typing import Any

from orion.core.swe.errors import FormulationIncompleteError


@dataclass(frozen=True)
class ProposedFixPlan:
    """Structured change plan produced during the FORMULATE_FIX stage."""

    target_files: tuple[str, ...]
    intended_modification: str
    expected_behavior: str
    validation_strategy: str
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.target_files:
            raise FormulationIncompleteError(
                "Proposed fix plan must specify at least one target file."
            )
        for target in self.target_files:
            if not isinstance(target, str) or not target.strip():
                raise FormulationIncompleteError(
                    "Target file paths must be non-empty strings."
                )

        if not self.intended_modification or not self.intended_modification.strip():
            raise FormulationIncompleteError(
                "Proposed fix plan must specify intended modification."
            )

        if not self.expected_behavior or not self.expected_behavior.strip():
            raise FormulationIncompleteError(
                "Proposed fix plan must specify expected behavior."
            )

        if not self.validation_strategy or not self.validation_strategy.strip():
            raise FormulationIncompleteError(
                "Proposed fix plan must specify validation strategy."
            )

        if not isinstance(self.constraints, (tuple, list)):
            raise FormulationIncompleteError(
                "Constraints must be an iterable sequence of strings."
            )
        cleaned_constraints = tuple(str(c).strip() for c in self.constraints if str(c).strip())
        object.__setattr__(self, "constraints", cleaned_constraints)

    def to_dict(self) -> dict[str, Any]:
        """Convert formulation plan to serializable dictionary."""
        return {
            "target_files": list(self.target_files),
            "intended_modification": self.intended_modification,
            "expected_behavior": self.expected_behavior,
            "validation_strategy": self.validation_strategy,
            "constraints": list(self.constraints),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProposedFixPlan":
        """Reconstruct formulation plan from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary.")
        return cls(
            target_files=tuple(data.get("target_files", ())),
            intended_modification=data.get("intended_modification", ""),
            expected_behavior=data.get("expected_behavior", ""),
            validation_strategy=data.get("validation_strategy", ""),
            constraints=tuple(data.get("constraints", ())),
        )

"""Pre-execution simulation verifying safety, blast radius, and risk in V5."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RecoverySimulationResult:
    """Evaluated risk profile of a simulated recovery action."""

    simulation_id: UUID
    action_type: str
    predicted_risk: str  # "low", "medium", "high", "critical"
    expected_files_changed: tuple[str, ...]
    expected_tests_impacted: tuple[str, ...]
    estimated_duration_seconds: float
    is_safe_to_execute: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert simulation result to dictionary."""
        return {
            "simulation_id": str(self.simulation_id),
            "action_type": self.action_type,
            "predicted_risk": self.predicted_risk,
            "expected_files_changed": list(self.expected_files_changed),
            "expected_tests_impacted": list(self.expected_tests_impacted),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "is_safe_to_execute": self.is_safe_to_execute,
            "reasons": list(self.reasons),
        }


class RecoverySimulator:
    """Simulates recovery operations before execution to prevent catastrophic workspace damage."""

    FORBIDDEN_FILE_PATTERNS: tuple[str, ...] = (
        ".git/",
        ".github/",
        "pyproject.toml",  # protect core configuration from blind automated recovery
        ".env",
        "/etc/",
        "c:\\windows",
    )

    def simulate(
        self,
        action_type: str,
        target_files: Sequence[str],
        estimated_duration_seconds: float = 5.0,
        max_duration_budget: float = 60.0,
        past_failed_strategies: Sequence[str] | None = None,
    ) -> RecoverySimulationResult:
        """Run pre-execution simulation on a candidate recovery action."""
        reasons: list[str] = []
        is_safe = True
        predicted_risk = "low"

        # Check 1: Budget bounds
        if estimated_duration_seconds > max_duration_budget:
            is_safe = False
            predicted_risk = "high"
            reasons.append(
                f"Estimated duration ({estimated_duration_seconds}s) exceeds "
                f"budget of {max_duration_budget}s."
            )

        # Check 2: File protection
        for f in target_files:
            f_lower = f.lower().replace("\\", "/")
            for forbidden in self.FORBIDDEN_FILE_PATTERNS:
                if forbidden in f_lower:
                    is_safe = False
                    predicted_risk = "critical"
                    reasons.append(f"Target file '{f}' violates protected path rule '{forbidden}'.")

        # Check 3: Repetition of identical failed strategy
        if past_failed_strategies and action_type in past_failed_strategies:
            predicted_risk = "high" if predicted_risk == "low" else predicted_risk
            reasons.append(
                f"Strategy '{action_type}' previously failed in this mission; elevated risk."
            )

        # Check 4: Blast radius file count
        if len(target_files) > 5:
            predicted_risk = "high" if predicted_risk != "critical" else "critical"
            reasons.append(f"Large change surface: {len(target_files)} files targeted.")

        if is_safe and not reasons:
            reasons.append("Simulation passed: blast radius within safe operational bounds.")

        # Predict impacted tests
        impacted_tests = tuple(
            f"tests/test_{f.split('/')[-1]}"
            for f in target_files
            if not f.startswith("tests/")
        )

        return RecoverySimulationResult(
            simulation_id=uuid4(),
            action_type=action_type,
            predicted_risk=predicted_risk,
            expected_files_changed=tuple(target_files),
            expected_tests_impacted=impacted_tests,
            estimated_duration_seconds=estimated_duration_seconds,
            is_safe_to_execute=is_safe,
            reasons=tuple(reasons),
        )

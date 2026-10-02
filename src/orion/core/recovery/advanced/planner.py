"""Adaptive recovery planner selecting optimal repair strategies in V5."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from orion.core.recovery.advanced.memory import AdaptiveRecoveryMemory
from orion.core.recovery.advanced.simulation import RecoverySimulationResult, RecoverySimulator
from orion.core.recovery.advanced.taxonomy import FailureCategory, FailureDiagnosis
from orion.core.swe.recovery.budget import RecoveryBudget


class RecoveryStrategyType(str, Enum):
    """The 6 strategic recovery paths available to ORION V5 self-healing."""

    RESTORE_SNAPSHOT = "restore_snapshot"
    TARGETED_PATCH_REPAIR = "targeted_patch_repair"
    DEPENDENCY_REINSTALL = "dependency_reinstall"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    ISOLATE_TEST_CASE = "isolate_test_case"
    ABORT_AND_ESCALATE = "abort_and_escalate"


@dataclass(frozen=True)
class AdaptiveRecoveryPlan:
    """Actionable self-healing plan evaluated for safety and blast radius."""

    plan_id: UUID
    diagnosis: FailureDiagnosis
    strategy: RecoveryStrategyType
    simulation: RecoverySimulationResult
    target_files: tuple[str, ...]
    requires_snapshot: bool
    budget_timeout_seconds: float
    attempt_number: int

    def to_dict(self) -> dict[str, Any]:
        """Convert recovery plan to dictionary."""
        return {
            "plan_id": str(self.plan_id),
            "diagnosis": self.diagnosis.to_dict(),
            "strategy": self.strategy.value,
            "simulation": self.simulation.to_dict(),
            "target_files": list(self.target_files),
            "requires_snapshot": self.requires_snapshot,
            "budget_timeout_seconds": self.budget_timeout_seconds,
            "attempt_number": self.attempt_number,
        }


class AdaptiveRecoveryPlanner:
    """Selects and plans recovery strategies using diagnosis, memory, and safety simulation."""

    def __init__(
        self,
        memory: AdaptiveRecoveryMemory | None = None,
        simulator: RecoverySimulator | None = None,
        max_attempts: int = 3,
        budget: RecoveryBudget | None = None,
    ) -> None:
        self.memory = memory or AdaptiveRecoveryMemory()
        self.simulator = simulator or RecoverySimulator()
        self.max_attempts = max_attempts
        self.budget = budget

    def select_strategy(
        self,
        diagnosis: FailureDiagnosis,
        attempt_number: int,
        failed_strategies: Sequence[str] | None = None,
    ) -> RecoveryStrategyType:
        """Deterministically choose the best strategy according to category and prior failures."""
        if attempt_number > self.max_attempts or (self.budget and self.budget.is_exhausted):
            return RecoveryStrategyType.ABORT_AND_ESCALATE

        failed = set(failed_strategies or [])

        # Security failures always immediately escalate
        if diagnosis.category == FailureCategory.SECURITY_FAILURE:
            return RecoveryStrategyType.ABORT_AND_ESCALATE

        # Primary mapping candidates based on taxonomy
        candidates: list[RecoveryStrategyType] = []
        cat = diagnosis.category

        if cat in (
            FailureCategory.SYNTAX_FAILURE,
            FailureCategory.TYPE_FAILURE,
            FailureCategory.ASSERTION_FAILURE,
        ):
            candidates = [
                RecoveryStrategyType.TARGETED_PATCH_REPAIR,
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]
        elif cat == FailureCategory.IMPORT_FAILURE:
            candidates = [
                RecoveryStrategyType.TARGETED_PATCH_REPAIR,
                RecoveryStrategyType.DEPENDENCY_REINSTALL,
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]
        elif cat == FailureCategory.DEPENDENCY_FAILURE:
            candidates = [
                RecoveryStrategyType.DEPENDENCY_REINSTALL,
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]
        elif cat in (
            FailureCategory.TIMEOUT,
            FailureCategory.ENVIRONMENT_FAILURE,
            FailureCategory.RESOURCE_FAILURE,
        ):
            candidates = [
                RecoveryStrategyType.RETRY_WITH_BACKOFF,
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]
        elif cat in (
            FailureCategory.PATCH_CONFLICT,
            FailureCategory.STALE_STATE,
            FailureCategory.TEST_REGRESSION,
        ):
            candidates = [
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.TARGETED_PATCH_REPAIR,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]
        else:
            candidates = [
                RecoveryStrategyType.TARGETED_PATCH_REPAIR,
                RecoveryStrategyType.RESTORE_SNAPSHOT,
                RecoveryStrategyType.ABORT_AND_ESCALATE,
            ]

        for cand in candidates:
            if cand.value not in failed:
                return cand

        return RecoveryStrategyType.ABORT_AND_ESCALATE

    def create_plan(
        self,
        diagnosis: FailureDiagnosis,
        attempt_number: int = 1,
        target_files: Sequence[str] | None = None,
        timeout_budget_seconds: float = 30.0,
    ) -> AdaptiveRecoveryPlan:
        """Create a fully verified recovery plan with pre-execution safety simulation."""
        if target_files is not None:
            files = tuple(target_files)
        elif diagnosis.target_file:
            files = (diagnosis.target_file,)
        else:
            files = ()

        past_failed = self.memory.get_failed_strategies_for_failure(diagnosis.category)
        strategy = self.select_strategy(diagnosis, attempt_number, past_failed)

        # Simulation
        simulation = self.simulator.simulate(
            action_type=strategy.value,
            target_files=files,
            estimated_duration_seconds=5.0 * attempt_number,
            max_duration_budget=timeout_budget_seconds,
            past_failed_strategies=past_failed,
        )

        # If simulation flagged as unsafe or budget is exhausted, escalate to abort
        final_strategy = strategy
        if self.budget and self.budget.is_exhausted:
            final_strategy = RecoveryStrategyType.ABORT_AND_ESCALATE
        elif (
            not simulation.is_safe_to_execute
            and strategy != RecoveryStrategyType.ABORT_AND_ESCALATE
        ):
            final_strategy = RecoveryStrategyType.ABORT_AND_ESCALATE

        requires_snapshot = final_strategy in (
            RecoveryStrategyType.TARGETED_PATCH_REPAIR,
            RecoveryStrategyType.RESTORE_SNAPSHOT,
            RecoveryStrategyType.DEPENDENCY_REINSTALL,
        )

        return AdaptiveRecoveryPlan(
            plan_id=uuid4(),
            diagnosis=diagnosis,
            strategy=final_strategy,
            simulation=simulation,
            target_files=files,
            requires_snapshot=requires_snapshot,
            budget_timeout_seconds=timeout_budget_seconds,
            attempt_number=attempt_number,
        )

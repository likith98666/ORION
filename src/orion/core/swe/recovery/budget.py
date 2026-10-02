"""Strict, auditable budget tracking for bounded self-healing recovery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from orion.core.swe.recovery.errors import BudgetExhaustedError, RecoveryDepthExceededError
from orion.core.swe.recovery.strategies import RecoveryStrategy


@dataclass(frozen=True)
class BudgetSnapshot:
    """Immutable audit point of recovery budget consumption."""

    total_attempts: int
    max_total_attempts: int
    remaining_attempts: int
    patch_regenerations: int
    max_patch_regenerations: int
    remaining_regenerations: int
    model_changes: int
    max_model_changes: int
    remaining_model_changes: int
    test_retries: int
    max_test_retries: int
    remaining_test_retries: int
    elapsed_seconds: float
    max_execution_seconds: float
    remaining_seconds: float
    affected_files_count: int
    max_affected_files_total: int
    recovery_depth: int
    max_recovery_depth: int
    is_exhausted: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_attempts": self.total_attempts,
            "max_total_attempts": self.max_total_attempts,
            "remaining_attempts": self.remaining_attempts,
            "patch_regenerations": self.patch_regenerations,
            "max_patch_regenerations": self.max_patch_regenerations,
            "remaining_regenerations": self.remaining_regenerations,
            "model_changes": self.model_changes,
            "max_model_changes": self.max_model_changes,
            "remaining_model_changes": self.remaining_model_changes,
            "test_retries": self.test_retries,
            "max_test_retries": self.max_test_retries,
            "remaining_test_retries": self.remaining_test_retries,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "max_execution_seconds": self.max_execution_seconds,
            "remaining_seconds": round(self.remaining_seconds, 2),
            "affected_files_count": self.affected_files_count,
            "max_affected_files_total": self.max_affected_files_total,
            "recovery_depth": self.recovery_depth,
            "max_recovery_depth": self.max_recovery_depth,
            "is_exhausted": self.is_exhausted,
            "timestamp": self.timestamp.isoformat(),
        }


class RecoveryBudget:
    """Authoritative tracker enforcing deterministic resource bounds on self-healing."""

    def __init__(
        self,
        max_total_attempts: int = 3,
        max_patch_regenerations: int = 2,
        max_model_changes: int = 1,
        max_test_retries: int = 2,
        max_execution_seconds: float = 300.0,
        max_affected_files_total: int = 10,
        max_recovery_depth: int = 3,
    ) -> None:
        if max_total_attempts <= 0:
            raise ValueError("max_total_attempts must be positive.")
        if max_recovery_depth <= 0:
            raise ValueError("max_recovery_depth must be positive.")
        if max_execution_seconds <= 0:
            raise ValueError("max_execution_seconds must be positive.")

        self._max_total_attempts = max_total_attempts
        self._max_patch_regenerations = max_patch_regenerations
        self._max_model_changes = max_model_changes
        self._max_test_retries = max_test_retries
        self._max_execution_seconds = max_execution_seconds
        self._max_affected_files_total = max_affected_files_total
        self._max_recovery_depth = max_recovery_depth

        self._total_attempts: int = 0
        self._patch_regenerations: int = 0
        self._model_changes: int = 0
        self._test_retries: int = 0
        self._elapsed_seconds: float = 0.0
        self._affected_files: set[str] = set()
        self._recovery_depth: int = 0

    @property
    def total_attempts(self) -> int:
        return self._total_attempts

    @property
    def remaining_attempts(self) -> int:
        return max(0, self._max_total_attempts - self._total_attempts)

    @property
    def remaining_regenerations(self) -> int:
        return max(0, self._max_patch_regenerations - self._patch_regenerations)

    @property
    def remaining_test_retries(self) -> int:
        return max(0, self._max_test_retries - self._test_retries)

    @property
    def recovery_depth(self) -> int:
        return self._recovery_depth

    @property
    def is_exhausted(self) -> bool:
        """Return True if any limiting budget metric has reached or exceeded its ceiling."""
        if self._total_attempts >= self._max_total_attempts:
            return True
        if self._recovery_depth >= self._max_recovery_depth:
            return True
        if self._elapsed_seconds >= self._max_execution_seconds:
            return True
        if len(self._affected_files) >= self._max_affected_files_total:
            return True
        return False

    def can_attempt(self, strategy: RecoveryStrategy | str | None = None) -> bool:
        """Check whether another recovery attempt is permitted."""
        if self.is_exhausted:
            return False

        if strategy is None:
            return True

        strat = RecoveryStrategy(strategy) if isinstance(strategy, str) else strategy

        if strat in (RecoveryStrategy.REGENERATE_PATCH, RecoveryStrategy.MODIFY_PATCH):
            return self._patch_regenerations < self._max_patch_regenerations
        elif strat == RecoveryStrategy.CHANGE_MODEL:
            return self._model_changes < self._max_model_changes
        elif strat == RecoveryStrategy.RETRY_TEST:
            return self._test_retries < self._max_test_retries
        elif strat in (
            RecoveryStrategy.ROLLBACK,
            RecoveryStrategy.REFRESH_WORKSPACE_STATE,
            RecoveryStrategy.TERMINATE,
        ):
            return True

        return False

    def consume(
        self,
        strategy: RecoveryStrategy | str,
        duration_seconds: float = 0.0,
        affected_files: Sequence[str] = (),
        increment_depth: bool = True,
    ) -> BudgetSnapshot:
        """Consume budget for the specified strategy execution.

        Raises BudgetExhaustedError or RecoveryDepthExceededError if bounds are breached.
        """
        strat = RecoveryStrategy(strategy) if isinstance(strategy, str) else strategy

        # Check total attempts ceiling
        if self._total_attempts >= self._max_total_attempts:
            raise BudgetExhaustedError(
                f"Recovery budget exhausted: maximum total attempts "
                f"({self._max_total_attempts}) reached."
            )

        # Check recovery depth ceiling
        if increment_depth and self._recovery_depth >= self._max_recovery_depth:
            raise RecoveryDepthExceededError(
                f"Recovery depth exceeded: maximum depth ({self._max_recovery_depth}) reached."
            )

        # Check strategy-specific bounds
        if strat in (RecoveryStrategy.REGENERATE_PATCH, RecoveryStrategy.MODIFY_PATCH):
            if self._patch_regenerations >= self._max_patch_regenerations:
                raise BudgetExhaustedError(
                    f"Recovery budget exhausted: maximum patch regenerations "
                    f"({self._max_patch_regenerations}) reached."
                )
            self._patch_regenerations += 1

        elif strat == RecoveryStrategy.CHANGE_MODEL:
            if self._model_changes >= self._max_model_changes:
                raise BudgetExhaustedError(
                    f"Recovery budget exhausted: maximum model changes "
                    f"({self._max_model_changes}) reached."
                )
            self._model_changes += 1

        elif strat == RecoveryStrategy.RETRY_TEST:
            if self._test_retries >= self._max_test_retries:
                raise BudgetExhaustedError(
                    f"Recovery budget exhausted: maximum test retries "
                    f"({self._max_test_retries}) reached."
                )
            self._test_retries += 1

        # Increment general usage
        self._total_attempts += 1
        if increment_depth:
            self._recovery_depth += 1
        self._elapsed_seconds += max(0.0, duration_seconds)

        for f in affected_files:
            if f and f.strip():
                self._affected_files.add(f.strip())

        # Check file ceiling
        if len(self._affected_files) > self._max_affected_files_total:
            raise BudgetExhaustedError(
                f"Recovery budget exhausted: total affected files ({len(self._affected_files)}) "
                f"exceeds ceiling ({self._max_affected_files_total})."
            )

        return self.create_snapshot()

    def create_snapshot(self) -> BudgetSnapshot:
        """Produce an immutable snapshot of current budget state."""
        return BudgetSnapshot(
            total_attempts=self._total_attempts,
            max_total_attempts=self._max_total_attempts,
            remaining_attempts=max(0, self._max_total_attempts - self._total_attempts),
            patch_regenerations=self._patch_regenerations,
            max_patch_regenerations=self._max_patch_regenerations,
            remaining_regenerations=max(
                0, self._max_patch_regenerations - self._patch_regenerations
            ),
            model_changes=self._model_changes,
            max_model_changes=self._max_model_changes,
            remaining_model_changes=max(0, self._max_model_changes - self._model_changes),
            test_retries=self._test_retries,
            max_test_retries=self._max_test_retries,
            remaining_test_retries=max(0, self._max_test_retries - self._test_retries),
            elapsed_seconds=self._elapsed_seconds,
            max_execution_seconds=self._max_execution_seconds,
            remaining_seconds=max(0.0, self._max_execution_seconds - self._elapsed_seconds),
            affected_files_count=len(self._affected_files),
            max_affected_files_total=self._max_affected_files_total,
            recovery_depth=self._recovery_depth,
            max_recovery_depth=self._max_recovery_depth,
            is_exhausted=self.is_exhausted,
        )

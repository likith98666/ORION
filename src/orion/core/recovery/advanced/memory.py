"""Adaptive recovery memory tracking strategy effectiveness across attempts in V5."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from orion.core.recovery.advanced.taxonomy import FailureCategory, FailureDiagnosis


@dataclass(frozen=True)
class RecoveryCycleRecord:
    """Historical record of an individual recovery cycle."""

    cycle_id: UUID
    attempt_number: int
    diagnosis: FailureDiagnosis
    strategy_name: str
    success: bool
    duration_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert cycle record to dictionary."""
        return {
            "cycle_id": str(self.cycle_id),
            "attempt_number": self.attempt_number,
            "diagnosis": self.diagnosis.to_dict(),
            "strategy_name": self.strategy_name,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


class AdaptiveRecoveryMemory:
    """Tracks historical recovery attempts and computes empirical strategy success rates."""

    def __init__(self, max_history: int = 500) -> None:
        self.max_history = max_history
        self._history: list[RecoveryCycleRecord] = []

    def record_attempt(
        self,
        attempt_number: int,
        diagnosis: FailureDiagnosis,
        strategy_name: str,
        success: bool,
        duration_seconds: float,
        notes: str = "",
    ) -> RecoveryCycleRecord:
        """Record an executed recovery attempt."""
        record = RecoveryCycleRecord(
            cycle_id=uuid4(),
            attempt_number=attempt_number,
            diagnosis=diagnosis,
            strategy_name=strategy_name,
            success=success,
            duration_seconds=duration_seconds,
            notes=notes,
        )
        if len(self._history) >= self.max_history:
            self._history.pop(0)

        self._history.append(record)
        return record

    def get_failed_strategies_for_failure(
        self, category: FailureCategory
    ) -> list[str]:
        """Return list of strategy names that previously failed for the given failure category."""
        return [
            rec.strategy_name
            for rec in self._history
            if rec.diagnosis.category == category and not rec.success
        ]

    def get_strategy_metrics(self) -> dict[str, dict[str, Any]]:
        """Calculate empirical success rate and mean duration for every attempted strategy."""
        metrics: dict[str, dict[str, Any]] = {}
        for rec in self._history:
            s_name = rec.strategy_name
            if s_name not in metrics:
                metrics[s_name] = {
                    "total_attempts": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "total_duration": 0.0,
                }
            metrics[s_name]["total_attempts"] += 1
            metrics[s_name]["total_duration"] += rec.duration_seconds
            if rec.success:
                metrics[s_name]["succeeded"] += 1
            else:
                metrics[s_name]["failed"] += 1

        summary: dict[str, dict[str, Any]] = {}
        for s_name, data in metrics.items():
            tot = data["total_attempts"]
            succ = data["succeeded"]
            rate = round(succ / tot, 2) if tot > 0 else 0.0
            mean_dur = round(data["total_duration"] / tot, 2) if tot > 0 else 0.0
            summary[s_name] = {
                "attempts": tot,
                "success_rate": rate,
                "mean_duration_seconds": mean_dur,
            }

        return summary

    def clear(self) -> None:
        """Clear all recovery cycle records."""
        self._history.clear()

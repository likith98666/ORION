"""Structured failure analysis and multi-dimensional aggregation for benchmark failures."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from orion.core.evaluation.models import BenchmarkTask, TaskRunResult


@dataclass(frozen=True)
class BenchmarkFailureRecord:
    """Detailed forensic record of an individual benchmark task failure."""

    task_id: str
    benchmark_name: str
    failure_stage: str
    failure_category: str
    root_execution_event: str
    recovery_attempts: int
    strategy_selected: str | None
    strategy_result: str | None
    rollback_performed: bool
    final_termination_reason: str
    orion_version: str = "6.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize failure record to dictionary."""
        return {
            "task_id": self.task_id,
            "benchmark_name": self.benchmark_name,
            "failure_stage": self.failure_stage,
            "failure_category": self.failure_category,
            "root_execution_event": self.root_execution_event,
            "recovery_attempts": self.recovery_attempts,
            "strategy_selected": self.strategy_selected,
            "strategy_result": self.strategy_result,
            "rollback_performed": self.rollback_performed,
            "final_termination_reason": self.final_termination_reason,
            "orion_version": self.orion_version,
        }


@dataclass(frozen=True)
class FailureAnalysisReport:
    """Aggregated analysis of failures across categories, stages, and strategies."""

    total_failures: int
    failures_by_category: dict[str, int]
    failures_by_stage: dict[str, int]
    failures_by_strategy: dict[str, int]
    failures_by_benchmark: dict[str, int]
    failures_by_version: dict[str, int]
    records: tuple[BenchmarkFailureRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize failure analysis report to dictionary."""
        return {
            "total_failures": self.total_failures,
            "aggregations": {
                "by_category": dict(self.failures_by_category),
                "by_stage": dict(self.failures_by_stage),
                "by_strategy": dict(self.failures_by_strategy),
                "by_benchmark": dict(self.failures_by_benchmark),
                "by_version": dict(self.failures_by_version),
            },
            "records": [r.to_dict() for r in self.records],
        }

    @classmethod
    def from_results(
        cls,
        results: Sequence[TaskRunResult],
        task_lookup: dict[str, BenchmarkTask] | None = None,
        version: str = "6.0.0",
    ) -> FailureAnalysisReport:
        """Construct a structured failure analysis report from executed benchmark results."""
        tasks = task_lookup or {}
        failure_records: list[BenchmarkFailureRecord] = []

        by_cat: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_strat: dict[str, int] = {}
        by_bench: dict[str, int] = {}
        by_ver: dict[str, int] = {}

        for r in results:
            if r.status != "PASS":
                task_meta = tasks.get(r.task_id)
                b_name = task_meta.name if task_meta else r.task_id
                f_cat = r.failure_category or (
                    task_meta.failure_category if task_meta else "unknown"
                )
                f_stage = (
                    "verify"
                    if not r.verification_passed
                    else ("run_tests" if r.tests_failed > 0 else "implement_change")
                )
                last_strat = r.recovery_strategies[-1] if r.recovery_strategies else None

                rec = BenchmarkFailureRecord(
                    task_id=r.task_id,
                    benchmark_name=b_name,
                    failure_stage=f_stage,
                    failure_category=f_cat,
                    root_execution_event=r.error_message or "Test verification criteria unmet.",
                    recovery_attempts=r.recovery_attempts,
                    strategy_selected=last_strat,
                    strategy_result="FAILED" if r.status != "PASS" else "PASSED",
                    rollback_performed=r.rollback_events > 0,
                    final_termination_reason=(
                        r.termination_reason or r.error_message or "Mission failed verification."
                    ),
                    orion_version=version,
                )
                failure_records.append(rec)

                by_cat[f_cat] = by_cat.get(f_cat, 0) + 1
                by_stage[f_stage] = by_stage.get(f_stage, 0) + 1
                if last_strat:
                    by_strat[last_strat] = by_strat.get(last_strat, 0) + 1
                by_bench[r.task_id] = by_bench.get(r.task_id, 0) + 1
                by_ver[version] = by_ver.get(version, 0) + 1

        return cls(
            total_failures=len(failure_records),
            failures_by_category=by_cat,
            failures_by_stage=by_stage,
            failures_by_strategy=by_strat,
            failures_by_benchmark=by_bench,
            failures_by_version=by_ver,
            records=tuple(failure_records),
        )

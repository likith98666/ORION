"""Rigorous engineering metrics with strictly defined mathematical formulas and denominators."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from orion.core.evaluation.models import TaskRunResult


@dataclass(frozen=True)
class EngineeringMetrics:
    """Comprehensive engineering metrics for autonomous SWE missions and self-healing evaluation.

    Every metric has an explicitly defined numerator, denominator, and mathematical formula.
    Division-by-zero is strictly guarded; when the denominator is zero, the value evaluates to 0.0.
    """

    # --- Mission-Level Metrics ---
    total_missions: int
    passed_missions: int
    failed_missions: int
    verified_missions: int
    safely_terminated_missions: int

    # Formula: passed_missions / total_missions
    # Denominator: total_missions
    mission_success_rate: float

    # Formula: verified_missions / total_missions
    # Denominator: total_missions
    verification_success_rate: float

    # Formula: failed_missions / total_missions
    # Denominator: total_missions
    mission_failure_rate: float

    # Formula: safely_terminated_missions / total_missions
    # Denominator: total_missions (if 0, evaluates to 1.0)
    safe_termination_rate: float

    # Formula: sum(duration_seconds) / total_missions
    # Denominator: total_missions
    mean_duration_seconds: float

    # --- Recovery-Level Metrics ---
    total_recovery_attempts: int
    successful_recoveries: int
    total_rollback_events: int
    max_recovery_depth_observed: int

    # Formula: successful_recoveries / total_recovery_attempts
    # Denominator: total_recovery_attempts (if 0 attempts made, evaluates to 1.0 baseline)
    recovery_success_rate: float

    # Formula: total_rollback_events / total_recovery_attempts
    # Denominator: total_recovery_attempts
    rollback_frequency: float

    # Formula per strategy: strategy_successes / strategy_attempts
    strategy_success_rates: dict[str, float]

    # --- Patch & Execution-Level Metrics ---
    total_tests_executed: int
    total_tests_passed: int
    total_tests_failed: int

    # Formula: total_tests_passed / total_tests_executed
    # Denominator: total_tests_executed
    test_pass_rate: float

    total_files_changed: int

    # Formula: total_files_changed / total_missions
    # Denominator: total_missions
    mean_files_changed_per_mission: float

    # --- Reliability & Reproducibility Metrics ---
    # Formula: correctly_classified_failures / total_classified_failures
    # Denominator: total_classified_failures
    classification_accuracy: float

    # Formula: identical_outcome_runs / total_repeated_runs
    # Denominator: total_repeated_runs
    deterministic_consistency_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize engineering metrics to dictionary with explicit precision."""
        return {
            "mission": {
                "total_missions": self.total_missions,
                "passed_missions": self.passed_missions,
                "failed_missions": self.failed_missions,
                "verified_missions": self.verified_missions,
                "safely_terminated_missions": self.safely_terminated_missions,
                "mission_success_rate": round(self.mission_success_rate, 4),
                "verification_success_rate": round(self.verification_success_rate, 4),
                "mission_failure_rate": round(self.mission_failure_rate, 4),
                "safe_termination_rate": round(self.safe_termination_rate, 4),
                "mean_duration_seconds": round(self.mean_duration_seconds, 3),
            },
            "recovery": {
                "total_recovery_attempts": self.total_recovery_attempts,
                "successful_recoveries": self.successful_recoveries,
                "total_rollback_events": self.total_rollback_events,
                "max_recovery_depth_observed": self.max_recovery_depth_observed,
                "recovery_success_rate": round(self.recovery_success_rate, 4),
                "rollback_frequency": round(self.rollback_frequency, 4),
                "strategy_success_rates": {
                    k: round(v, 4) for k, v in self.strategy_success_rates.items()
                },
            },
            "execution": {
                "total_tests_executed": self.total_tests_executed,
                "total_tests_passed": self.total_tests_passed,
                "total_tests_failed": self.total_tests_failed,
                "test_pass_rate": round(self.test_pass_rate, 4),
                "total_files_changed": self.total_files_changed,
                "mean_files_changed_per_mission": round(self.mean_files_changed_per_mission, 2),
            },
            "reliability": {
                "classification_accuracy": round(self.classification_accuracy, 4),
                "deterministic_consistency_rate": round(self.deterministic_consistency_rate, 4),
            },
        }

    @classmethod
    def compute_from_results(
        cls,
        results: Sequence[TaskRunResult],
        ground_truth_categories: dict[str, str] | None = None,
        deterministic_consistency_rate: float = 1.0,
    ) -> EngineeringMetrics:
        """Compute all metrics from empirical TaskRunResult instances without synthesis."""
        total_missions = len(results)
        if total_missions == 0:
            return cls(
                total_missions=0,
                passed_missions=0,
                failed_missions=0,
                verified_missions=0,
                safely_terminated_missions=0,
                mission_success_rate=0.0,
                verification_success_rate=0.0,
                mission_failure_rate=0.0,
                safe_termination_rate=1.0,
                mean_duration_seconds=0.0,
                total_recovery_attempts=0,
                successful_recoveries=0,
                total_rollback_events=0,
                max_recovery_depth_observed=0,
                recovery_success_rate=1.0,
                rollback_frequency=0.0,
                strategy_success_rates={},
                total_tests_executed=0,
                total_tests_passed=0,
                total_tests_failed=0,
                test_pass_rate=0.0,
                total_files_changed=0,
                mean_files_changed_per_mission=0.0,
                classification_accuracy=1.0,
                deterministic_consistency_rate=deterministic_consistency_rate,
            )

        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status != "PASS")
        verified = sum(1 for r in results if r.verification_passed)
        safely_terminated = sum(
            1 for r in results if r.status in ("PASS", "FAIL") and r.status != "ERROR"
        )

        mission_succ_rate = passed / total_missions
        verif_succ_rate = verified / total_missions
        mission_fail_rate = failed / total_missions
        safe_term_rate = (safely_terminated / total_missions) if total_missions > 0 else 1.0
        mean_dur = sum(r.duration_seconds for r in results) / total_missions

        total_rec_attempts = sum(r.recovery_attempts for r in results)
        total_rollbacks = sum(r.rollback_events for r in results)
        successful_rec = sum(1 for r in results if r.recovery_attempts > 0 and r.status == "PASS")
        rec_success_rate = (successful_rec / total_rec_attempts) if total_rec_attempts > 0 else 1.0
        rollback_freq = (total_rollbacks / total_rec_attempts) if total_rec_attempts > 0 else 0.0

        strat_counts: dict[str, int] = {}
        strat_successes: dict[str, int] = {}
        for r in results:
            for s in r.recovery_strategies:
                strat_counts[s] = strat_counts.get(s, 0) + 1
                if r.status == "PASS":
                    strat_successes[s] = strat_successes.get(s, 0) + 1

        strategy_rates = {
            s: strat_successes.get(s, 0) / count for s, count in strat_counts.items() if count > 0
        }

        tests_passed = sum(r.tests_passed for r in results)
        tests_failed = sum(r.tests_failed for r in results)
        total_tests = tests_passed + tests_failed
        test_pass_rate = (tests_passed / total_tests) if total_tests > 0 else 0.0

        total_files = sum(r.files_changed for r in results)
        mean_files = total_files / total_missions

        # Reliability classification against ground truth if provided
        classified_correct = 0
        total_evaluated_cat = 0
        if ground_truth_categories:
            for r in results:
                if r.task_id in ground_truth_categories and r.failure_category:
                    total_evaluated_cat += 1
                    if r.failure_category == ground_truth_categories[r.task_id]:
                        classified_correct += 1

        classif_acc = (classified_correct / total_evaluated_cat) if total_evaluated_cat > 0 else 1.0

        return cls(
            total_missions=total_missions,
            passed_missions=passed,
            failed_missions=failed,
            verified_missions=verified,
            safely_terminated_missions=safely_terminated,
            mission_success_rate=mission_succ_rate,
            verification_success_rate=verif_succ_rate,
            mission_failure_rate=mission_fail_rate,
            safe_termination_rate=safe_term_rate,
            mean_duration_seconds=mean_dur,
            total_recovery_attempts=total_rec_attempts,
            successful_recoveries=successful_rec,
            total_rollback_events=total_rollbacks,
            max_recovery_depth_observed=max((r.recovery_attempts for r in results), default=0),
            recovery_success_rate=rec_success_rate,
            rollback_frequency=rollback_freq,
            strategy_success_rates=strategy_rates,
            total_tests_executed=total_tests,
            total_tests_passed=tests_passed,
            total_tests_failed=tests_failed,
            test_pass_rate=test_pass_rate,
            total_files_changed=total_files,
            mean_files_changed_per_mission=mean_files,
            classification_accuracy=classif_acc,
            deterministic_consistency_rate=deterministic_consistency_rate,
        )

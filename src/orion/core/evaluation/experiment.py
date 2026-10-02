"""Immutable experiment tracking, reproducibility metadata, and version comparison for V6."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from orion.core.evaluation.failure_analysis import FailureAnalysisReport
from orion.core.evaluation.metrics import EngineeringMetrics
from orion.core.evaluation.models import BenchmarkReport, get_system_environment_metadata
from orion.core.security.redaction import RedactionEngine


def _get_current_git_commit() -> str:
    """Safely query current git commit hash, falling back to 'unknown'."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown"


@dataclass(frozen=True)
class VersionComparisonResult:
    """Empirical differences between two benchmark evaluation experiments."""

    base_experiment_id: str
    base_version: str
    target_experiment_id: str
    target_version: str
    pass_rate_delta: float
    duration_delta_seconds: float
    recovery_success_delta: float
    newly_passing: tuple[str, ...]
    newly_failing: tuple[str, ...]
    performance_improved: tuple[str, ...]
    performance_regressed: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize version comparison result to dictionary."""
        return {
            "base_experiment_id": self.base_experiment_id,
            "base_version": self.base_version,
            "target_experiment_id": self.target_experiment_id,
            "target_version": self.target_version,
            "metrics_delta": {
                "pass_rate_delta": round(self.pass_rate_delta, 4),
                "duration_delta_seconds": round(self.duration_delta_seconds, 3),
                "recovery_success_delta": round(self.recovery_success_delta, 4),
            },
            "newly_passing": list(self.newly_passing),
            "newly_failing": list(self.newly_failing),
            "performance_improved": list(self.performance_improved),
            "performance_regressed": list(self.performance_regressed),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ExperimentRecord:
    """Immutable, fully reproducible record of a benchmark evaluation experiment."""

    experiment_id: str
    orion_version: str
    git_commit: str
    benchmark_corpus_version: str
    configuration: dict[str, Any]
    environment_metadata: dict[str, Any]
    python_version: str
    random_seed: int | None
    deterministic_components: tuple[str, ...]
    nondeterministic_components: tuple[str, ...]
    metrics: EngineeringMetrics
    report: BenchmarkReport
    failure_analysis: FailureAnalysisReport
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize experiment record to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "orion_version": self.orion_version,
            "git_commit": self.git_commit,
            "benchmark_corpus_version": self.benchmark_corpus_version,
            "configuration": self.configuration,
            "environment_metadata": self.environment_metadata,
            "python_version": self.python_version,
            "random_seed": self.random_seed,
            "reproducibility": {
                "deterministic_components": list(self.deterministic_components),
                "nondeterministic_components": list(self.nondeterministic_components),
            },
            "metrics": self.metrics.to_dict(),
            "report": self.report.to_dict(),
            "failure_analysis": self.failure_analysis.to_dict(),
            "created_at": self.created_at,
        }


def _scrub_dict_keys(data: Any, redactor: RedactionEngine) -> Any:
    """Recursively scrub sensitive keys and known secret values."""
    if isinstance(data, dict):
        scrubbed: dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("key", "token", "secret", "password", "auth", "cred")):
                scrubbed[str(k)] = "[REDACTED]"
            else:
                scrubbed[str(k)] = _scrub_dict_keys(v, redactor)
        return scrubbed
    return redactor.redact(data)


class ExperimentTracker:
    """Thread-safe registry for recording, retrieving, and comparing evaluation experiments."""

    DETERMINISTIC_COMPONENTS: tuple[str, ...] = (
        "Isolated filesystem workspace creation",
        "Fixture file extraction and checksum matching",
        "Failure taxonomy classification rules",
        "Rollback manager SHA-256 snapshotting",
        "Deterministic test runner exit code evaluation",
        "VerificationEngine rule-based promotion",
    )

    NONDETERMINISTIC_COMPONENTS: tuple[str, ...] = (
        "Model provider generation tokens and latency",
        "Subprocess execution thread scheduling",
        "OS-level file I/O timings",
    )

    def __init__(self, redaction_engine: RedactionEngine | None = None) -> None:
        self._experiments: dict[str, ExperimentRecord] = {}
        self._redactor = redaction_engine or RedactionEngine()

    def create_experiment(
        self,
        report: BenchmarkReport,
        metrics: EngineeringMetrics,
        failure_analysis: FailureAnalysisReport,
        configuration: dict[str, Any] | None = None,
        orion_version: str = "6.0.0",
        benchmark_corpus_version: str = "1.0.0",
        random_seed: int | None = 42,
    ) -> ExperimentRecord:
        """Create and store an immutable, scrubbed experiment record."""
        exp_id = f"EXP-{uuid4().hex[:8].upper()}"
        clean_config = _scrub_dict_keys(configuration or {}, self._redactor)
        clean_env = self._redactor.redact(get_system_environment_metadata())

        record = ExperimentRecord(
            experiment_id=exp_id,
            orion_version=orion_version,
            git_commit=_get_current_git_commit(),
            benchmark_corpus_version=benchmark_corpus_version,
            configuration=clean_config,
            environment_metadata=clean_env,
            python_version=sys.version.split()[0],
            random_seed=random_seed,
            deterministic_components=self.DETERMINISTIC_COMPONENTS,
            nondeterministic_components=self.NONDETERMINISTIC_COMPONENTS,
            metrics=metrics,
            report=report,
            failure_analysis=failure_analysis,
        )

        self._experiments[exp_id] = record
        return record

    def get_experiment(self, experiment_id: str) -> ExperimentRecord | None:
        """Retrieve an experiment record by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(self) -> list[ExperimentRecord]:
        """List all recorded experiments ordered chronologically."""
        return list(self._experiments.values())

    def compare_experiments(
        self,
        base_id: str,
        target_id: str,
    ) -> VersionComparisonResult:
        """Perform a rigorous, empirical comparison between two experiment records."""
        base = self._experiments.get(base_id)
        if not base:
            raise KeyError(f"Base experiment '{base_id}' not found.")
        target = self._experiments.get(target_id)
        if not target:
            raise KeyError(f"Target experiment '{target_id}' not found.")

        base_res_map = {r.task_id: r for r in base.report.results}
        tgt_res_map = {r.task_id: r for r in target.report.results}

        newly_passing: list[str] = []
        newly_failing: list[str] = []
        improved: list[str] = []
        regressed: list[str] = []

        all_keys = set(base_res_map.keys()).union(tgt_res_map.keys())
        for tid in sorted(all_keys):
            b_item = base_res_map.get(tid)
            t_item = tgt_res_map.get(tid)
            if b_item and t_item:
                if b_item.status != "PASS" and t_item.status == "PASS":
                    newly_passing.append(tid)
                elif b_item.status == "PASS" and t_item.status != "PASS":
                    newly_failing.append(tid)

                if t_item.duration_seconds < b_item.duration_seconds * 0.8:
                    improved.append(tid)
                elif t_item.duration_seconds > b_item.duration_seconds * 1.2:
                    regressed.append(tid)

        pass_delta = (
            target.metrics.mission_success_rate - base.metrics.mission_success_rate
        )
        dur_delta = (
            target.metrics.mean_duration_seconds - base.metrics.mean_duration_seconds
        )
        rec_delta = (
            target.metrics.recovery_success_rate - base.metrics.recovery_success_rate
        )

        summary = (
            f"Comparison {base.orion_version} ({base_id}) -> {target.orion_version} ({target_id}): "
            f"pass rate delta={pass_delta:+.2%}, "
            f"duration delta={dur_delta:+.2f}s, "
            f"newly passing={len(newly_passing)}, "
            f"newly failing={len(newly_failing)}."
        )

        return VersionComparisonResult(
            base_experiment_id=base_id,
            base_version=base.orion_version,
            target_experiment_id=target_id,
            target_version=target.orion_version,
            pass_rate_delta=pass_delta,
            duration_delta_seconds=dur_delta,
            recovery_success_delta=rec_delta,
            newly_passing=tuple(newly_passing),
            newly_failing=tuple(newly_failing),
            performance_improved=tuple(improved),
            performance_regressed=tuple(regressed),
            summary=summary,
        )

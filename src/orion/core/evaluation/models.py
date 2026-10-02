"""Domain models and DTOs for ORION standardized SWE benchmark evaluation."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class BenchmarkCategory(str, Enum):
    """Categorization of standard SWE engineering benchmark tasks."""

    BUG_FIX = "bug_fix"
    REGRESSION_FIX = "regression_fix"
    SYNTAX_VALIDATION = "syntax_validation"
    RECOVERY_CHALLENGE = "recovery_challenge"
    FEATURE_ADDITION = "feature_addition"


class BenchmarkDifficulty(str, Enum):
    """Complexity and difficulty tier of a benchmark task."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class BenchmarkTask:
    """A standardized, reproducible SWE evaluation problem."""

    task_id: str
    name: str
    category: BenchmarkCategory
    difficulty: BenchmarkDifficulty
    problem_statement: str
    workspace_files: dict[str, str]
    test_files: dict[str, str]
    target_files: tuple[str, ...] = ()
    expected_exit_code: int = 0
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id cannot be empty.")
        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty.")
        if not isinstance(self.category, BenchmarkCategory):
            raise TypeError("category must be a BenchmarkCategory enum.")
        if not isinstance(self.difficulty, BenchmarkDifficulty):
            raise TypeError("difficulty must be a BenchmarkDifficulty enum.")
        if not self.problem_statement or not self.problem_statement.strip():
            raise ValueError("problem_statement cannot be empty.")
        if not self.workspace_files:
            raise ValueError("workspace_files must contain at least one file.")
        if not self.test_files:
            raise ValueError("test_files must contain at least one test file.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary representation."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "problem_statement": self.problem_statement,
            "workspace_files": list(self.workspace_files.keys()),
            "test_files": list(self.test_files.keys()),
            "target_files": list(self.target_files),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class TaskRunResult:
    """Recorded outcome from executing a single benchmark task."""

    task_id: str
    category: str
    status: str  # "PASS", "FAIL", "TIMEOUT", "ERROR"
    duration_seconds: float
    tests_passed: int
    tests_failed: int
    verification_passed: bool
    recovery_attempts: int
    files_changed: int
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize task run result to dictionary."""
        return {
            "task_id": self.task_id,
            "category": self.category,
            "status": self.status,
            "duration_seconds": round(self.duration_seconds, 3),
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "verification_passed": self.verification_passed,
            "recovery_attempts": self.recovery_attempts,
            "files_changed": self.files_changed,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class BenchmarkReport:
    """Comprehensive, deterministic evaluation report across a benchmark suite."""

    benchmark_id: str
    suite_name: str
    started_at: str
    completed_at: str
    total_tasks: int
    passed_tasks: int
    failed_tasks: int
    pass_at_1_rate: float
    verification_completeness: float
    recovery_success_rate: float
    mean_duration_seconds: float
    results: tuple[TaskRunResult, ...]
    environment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert benchmark report to structured JSON-serializable dictionary."""
        return {
            "benchmark_id": self.benchmark_id,
            "suite_name": self.suite_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metrics": {
                "total_tasks": self.total_tasks,
                "passed_tasks": self.passed_tasks,
                "failed_tasks": self.failed_tasks,
                "pass_at_1_rate": round(self.pass_at_1_rate, 4),
                "verification_completeness": round(self.verification_completeness, 4),
                "recovery_success_rate": round(self.recovery_success_rate, 4),
                "mean_duration_seconds": round(self.mean_duration_seconds, 3),
            },
            "environment": self.environment,
            "results": [r.to_dict() for r in self.results],
        }

    def to_markdown(self) -> str:
        """Render a formatted, auditable Markdown scorecard."""
        pass_pct = f"{self.pass_at_1_rate * 100:.1f}%"
        verif_pct = f"{self.verification_completeness * 100:.1f}%"
        recov_pct = f"{self.recovery_success_rate * 100:.1f}%"

        lines = [
            f"# ORION Benchmark Scorecard — {self.suite_name}",
            "",
            f"**Benchmark ID**: `{self.benchmark_id}`  ",
            f"**Completed At**: `{self.completed_at}`  ",
            f"**Platform**: `{self.environment.get('platform', platform.system())}` | "
            f"**Python**: `{self.environment.get('python_version', sys.version.split()[0])}`",
            "",
            "## Aggregate Metrics",
            "",
            "| Metric | Measured Value | Standard |",
            "| :--- | :--- | :--- |",
            (
                f"| **Pass@1 Rate** | **{pass_pct}** "
                f"({self.passed_tasks}/{self.total_tasks}) | Deterministic pass |"
            ),
            f"| **Verification Completeness** | **{verif_pct}** | Authoritative promotion |",
            f"| **Recovery Success Rate** | **{recov_pct}** | Bounded self-healing |",
            (
                f"| **Mean Task Duration** | **{self.mean_duration_seconds:.2f}s** "
                "| Wall-clock latency |"
            ),
            "",
            "## Task Execution Breakdown",
            "",
            "| Task ID | Category | Status | Verified | Tests Passed | Duration | Error |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for r in self.results:
            status_badge = f"**{r.status}**" if r.status == "PASS" else f"`{r.status}`"
            verif_badge = "✓" if r.verification_passed else "✗"
            err_text = r.error_message or "—"
            if len(err_text) > 30:
                err_text = err_text[:27] + "..."
            lines.append(
                f"| `{r.task_id}` | {r.category} | {status_badge} | "
                f"{verif_badge} | {r.tests_passed} | {r.duration_seconds:.2f}s | {err_text} |"
            )

        lines.append("")
        lines.append("---")
        lines.append("*Report generated deterministically by ORION Evaluation Subsystem.*")
        return "\n".join(lines)


def get_system_environment_metadata() -> dict[str, Any]:
    """Capture runtime platform metadata for reproducible experiment tracking."""
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "captured_at": datetime.now(UTC).isoformat(),
    }

"""ORION Evaluation and Benchmarking Subsystem."""

from __future__ import annotations

from orion.core.evaluation.corpus import (
    FAILURE_TAXONOMY_CORPUS,
    SMOKE_CORPUS,
    STANDARD_CORPUS,
    get_benchmark_suite,
)
from orion.core.evaluation.experiment import (
    ExperimentRecord,
    ExperimentTracker,
    VersionComparisonResult,
)
from orion.core.evaluation.failure_analysis import (
    BenchmarkFailureRecord,
    FailureAnalysisReport,
)
from orion.core.evaluation.metrics import EngineeringMetrics
from orion.core.evaluation.models import (
    BenchmarkCategory,
    BenchmarkDifficulty,
    BenchmarkReport,
    BenchmarkTask,
    TaskRunResult,
    get_system_environment_metadata,
)
from orion.core.evaluation.runner import BenchmarkRunner

__all__ = [
    "BenchmarkCategory",
    "BenchmarkDifficulty",
    "BenchmarkFailureRecord",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkTask",
    "EngineeringMetrics",
    "ExperimentRecord",
    "ExperimentTracker",
    "FAILURE_TAXONOMY_CORPUS",
    "FailureAnalysisReport",
    "SMOKE_CORPUS",
    "STANDARD_CORPUS",
    "TaskRunResult",
    "VersionComparisonResult",
    "get_benchmark_suite",
    "get_system_environment_metadata",
]

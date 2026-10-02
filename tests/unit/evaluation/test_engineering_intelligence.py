"""Dedicated V6 Engineering Intelligence & Evaluation Test Suite.

Validates:
- Standardized failure taxonomy benchmark corpus and metadata schema
- Deterministic benchmark loading and malformed task rejection
- Benchmark execution for both SUCCESSFUL and FAILURE cases
- Result persistence and artifact generation
- Engineering metrics formulas and denominator correctness
- Zero-division guards across all metric categories
- Multi-dimensional failure aggregation (category, stage, strategy, version)
- Experiment immutability, reproducibility separation, and secret redaction
- Cross-version empirical comparison
- REST API contracts for /api/v1/evaluation/*
- Security boundaries, path containment, and backend-authoritative evidence integrity
"""

from __future__ import annotations

import json
import threading
from dataclasses import FrozenInstanceError
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService
from orion.core.evaluation.corpus import (
    FAILURE_TAXONOMY_CORPUS,
    SMOKE_CORPUS,
    STANDARD_CORPUS,
    TASK_BUG_FIX_CALCULATOR,
    TASK_SECURITY_TRAVERSAL_GUARD,
    get_benchmark_suite,
)
from orion.core.evaluation.experiment import ExperimentTracker
from orion.core.evaluation.failure_analysis import FailureAnalysisReport
from orion.core.evaluation.metrics import EngineeringMetrics
from orion.core.evaluation.models import (
    BenchmarkCategory,
    BenchmarkDifficulty,
    BenchmarkReport,
    BenchmarkTask,
    TaskRunResult,
)
from orion.core.evaluation.runner import BenchmarkRunner
from orion.core.security.redaction import RedactionEngine


@pytest.fixture
def eval_server(tmp_path: Path):
    """Fixture providing an Orion server for V6 Evaluation REST API testing."""
    repo = tmp_path / "eval_workspace"
    repo.mkdir(parents=True, exist_ok=True)
    test_service = MissionAPIService(default_workspace_path=repo)

    class CustomHandler(OrionAPIHandler):
        service = test_service

    server = HTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_service, repo

    server.shutdown()
    server.server_close()


# ---------------------------------------------------------------------------
# 1. Corpus Schema Validation & Deterministic Loading
# ---------------------------------------------------------------------------


def test_failure_taxonomy_corpus_schema():
    """Verify all tasks in failure taxonomy corpus conform to strict metadata schemas."""
    assert len(FAILURE_TAXONOMY_CORPUS) >= 6
    task_ids = set()

    for task in FAILURE_TAXONOMY_CORPUS:
        assert task.task_id not in task_ids, f"Duplicate task_id: {task.task_id}"
        task_ids.add(task.task_id)
        assert task.name
        assert isinstance(task.category, BenchmarkCategory)
        assert isinstance(task.difficulty, BenchmarkDifficulty)
        assert task.problem_statement
        assert len(task.workspace_files) > 0
        assert len(task.test_files) > 0
        assert task.timeout_seconds > 0.0
        assert task.risk_classification in ("low", "medium", "high")
        assert task.failure_category in (
            "syntax_failure",
            "assertion_failure",
            "type_failure",
            "import_failure",
            "test_regression",
            "security_failure",
            "unknown",
        )

        d = task.to_dict()
        assert d["task_id"] == task.task_id
        assert d["category"] == task.category.value
        assert d["difficulty"] == task.difficulty.value
        assert "workspace_files" in d
        assert "test_files" in d


def test_malformed_benchmark_task_rejection():
    """Verify BenchmarkTask constructor rejects invalid or incomplete configurations."""
    valid_ws = {"src/app.py": "x = 1"}
    valid_test = {"tests/test_app.py": "assert True"}

    with pytest.raises(ValueError, match="task_id cannot be empty"):
        BenchmarkTask(
            task_id="",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files=valid_ws,
            test_files=valid_test,
        )

    with pytest.raises(ValueError, match="name cannot be empty"):
        BenchmarkTask(
            task_id="T-1",
            name="   ",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files=valid_ws,
            test_files=valid_test,
        )

    with pytest.raises(TypeError, match="category must be a BenchmarkCategory"):
        BenchmarkTask(
            task_id="T-1",
            name="Valid",
            category="invalid_category",  # type: ignore
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files=valid_ws,
            test_files=valid_test,
        )

    with pytest.raises(ValueError, match="problem_statement cannot be empty"):
        BenchmarkTask(
            task_id="T-1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="",
            workspace_files=valid_ws,
            test_files=valid_test,
        )

    with pytest.raises(ValueError, match="workspace_files must contain at least one file"):
        BenchmarkTask(
            task_id="T-1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files={},
            test_files=valid_test,
        )

    with pytest.raises(ValueError, match="test_files must contain at least one test file"):
        BenchmarkTask(
            task_id="T-1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files=valid_ws,
            test_files={},
        )

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        BenchmarkTask(
            task_id="T-1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Test",
            workspace_files=valid_ws,
            test_files=valid_test,
            timeout_seconds=-5.0,
        )


def test_deterministic_suite_retrieval():
    """Verify get_benchmark_suite deterministic retrieval across aliases."""
    smoke1 = get_benchmark_suite("smoke")
    smoke2 = get_benchmark_suite("quick")
    assert smoke1 == smoke2
    assert smoke1 == SMOKE_CORPUS

    std1 = get_benchmark_suite("standard")
    std2 = get_benchmark_suite("default")
    assert std1 == std2
    assert std1 == STANDARD_CORPUS

    tax1 = get_benchmark_suite("taxonomy")
    tax2 = get_benchmark_suite("v6")
    assert tax1 == tax2
    assert tax1 == FAILURE_TAXONOMY_CORPUS


# ---------------------------------------------------------------------------
# 2. Benchmark Execution & Result Grounding (Success & Failure)
# ---------------------------------------------------------------------------


def test_benchmark_runner_successful_execution(tmp_path: Path):
    """Verify execution of repaired benchmark task leads to real passing test and verification."""
    runner = BenchmarkRunner(output_dir=tmp_path / "artifacts")
    run_res = runner.run_task(TASK_BUG_FIX_CALCULATOR, tmp_path / "ws_success", auto_repair=True)

    assert run_res.task_id == TASK_BUG_FIX_CALCULATOR.task_id
    assert run_res.status == "PASS"
    assert run_res.verification_passed is True
    assert run_res.tests_passed == 1
    assert run_res.tests_failed == 0
    assert run_res.files_changed >= 1
    assert run_res.evidence_count > 0
    assert run_res.duration_seconds > 0.0


def test_benchmark_runner_failure_execution(tmp_path: Path):
    """Verify execution of unrepaired benchmark task captures real test failure and stage."""
    runner = BenchmarkRunner(output_dir=tmp_path / "artifacts")
    run_res = runner.run_task(TASK_BUG_FIX_CALCULATOR, tmp_path / "ws_failure", auto_repair=False)

    assert run_res.task_id == TASK_BUG_FIX_CALCULATOR.task_id
    assert run_res.status == "FAIL"
    assert run_res.verification_passed is False
    assert run_res.tests_passed == 0
    assert run_res.tests_failed == 1
    assert run_res.files_changed == 0
    assert run_res.error_message is not None
    assert "verification failed" in (run_res.termination_reason or "").lower()


def test_suite_execution_disk_persistence(tmp_path: Path):
    """Verify suite execution produces on-disk JSON report and Markdown scorecard."""
    out_dir = tmp_path / "persisted_eval"
    runner = BenchmarkRunner(output_dir=out_dir)
    report = runner.run_suite(suite="smoke", auto_repair=True)

    assert report.total_tasks == 2
    assert report.passed_tasks == 2
    assert report.pass_at_1_rate == 1.0

    json_files = list(out_dir.glob("benchmark_report_*.json"))
    md_files = list(out_dir.glob("benchmark_scorecard_*.md"))
    assert len(json_files) == 1
    assert len(md_files) == 1

    loaded = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert loaded["benchmark_id"] == report.benchmark_id
    assert loaded["metrics"]["pass_at_1_rate"] == 1.0


# ---------------------------------------------------------------------------
# 3. Engineering Metrics & Denominator Correctness
# ---------------------------------------------------------------------------


def test_engineering_metrics_mathematical_formulas():
    """Verify exact mathematical calculation and precision of EngineeringMetrics."""
    res1 = TaskRunResult(
        task_id="T-1",
        category="bug_fix",
        status="PASS",
        duration_seconds=2.0,
        tests_passed=3,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=1,
        files_changed=2,
        recovery_strategies=("cache_clear",),
        rollback_events=0,
        failure_category="assertion_failure",
    )
    res2 = TaskRunResult(
        task_id="T-2",
        category="syntax_validation",
        status="FAIL",
        duration_seconds=4.0,
        tests_passed=0,
        tests_failed=2,
        verification_passed=False,
        recovery_attempts=2,
        files_changed=0,
        recovery_strategies=("ast_rewrite", "rollback"),
        rollback_events=1,
        failure_category="syntax_failure",
        error_message="SyntaxError in validator",
    )

    ground_truth = {"T-1": "assertion_failure", "T-2": "syntax_failure"}
    metrics = EngineeringMetrics.compute_from_results(
        [res1, res2], ground_truth_categories=ground_truth
    )

    # Mission-level checks
    assert metrics.total_missions == 2
    assert metrics.passed_missions == 1
    assert metrics.failed_missions == 1
    assert metrics.verified_missions == 1
    assert metrics.mission_success_rate == 0.5  # 1 / 2
    assert metrics.verification_success_rate == 0.5  # 1 / 2
    assert metrics.mission_failure_rate == 0.5  # 1 / 2
    assert metrics.safe_termination_rate == 1.0  # 1 safely terminated failure / 1 failure
    assert metrics.mean_duration_seconds == 3.0  # (2.0 + 4.0) / 2

    # Recovery-level checks
    assert metrics.total_recovery_attempts == 3  # 1 + 2
    assert metrics.successful_recoveries == 1  # res1 had recovery > 0 and PASS
    assert metrics.total_rollback_events == 1
    assert metrics.max_recovery_depth_observed == 2
    assert metrics.recovery_success_rate == pytest.approx(1 / 3, 0.001)
    assert metrics.rollback_frequency == pytest.approx(1 / 3, 0.001)

    # Strategy success rates
    assert metrics.strategy_success_rates["cache_clear"] == 1.0  # 1 attempt, passed
    assert metrics.strategy_success_rates["ast_rewrite"] == 0.0  # 1 attempt, failed
    assert metrics.strategy_success_rates["rollback"] == 0.0

    # Execution-level checks
    assert metrics.total_tests_executed == 5  # 3 + 2
    assert metrics.total_tests_passed == 3
    assert metrics.total_tests_failed == 2
    assert metrics.test_pass_rate == 0.6  # 3 / 5
    assert metrics.total_files_changed == 2
    assert metrics.mean_files_changed_per_mission == 1.0  # 2 / 2

    # Reliability checks
    assert metrics.classification_accuracy == 1.0  # Both ground truth categories matched


def test_engineering_metrics_zero_division_guards():
    """Verify EngineeringMetrics strictly guards against zero-division for empty results."""
    empty_metrics = EngineeringMetrics.compute_from_results([])

    assert empty_metrics.total_missions == 0
    assert empty_metrics.mission_success_rate == 0.0
    assert empty_metrics.verification_success_rate == 0.0
    assert empty_metrics.mission_failure_rate == 0.0
    assert empty_metrics.safe_termination_rate == 1.0
    assert empty_metrics.recovery_success_rate == 1.0
    assert empty_metrics.rollback_frequency == 0.0
    assert empty_metrics.test_pass_rate == 0.0
    assert empty_metrics.mean_files_changed_per_mission == 0.0
    assert empty_metrics.classification_accuracy == 1.0

    d = empty_metrics.to_dict()
    assert d["mission"]["total_missions"] == 0
    assert d["recovery"]["recovery_success_rate"] == 1.0


# ---------------------------------------------------------------------------
# 4. Multi-Dimensional Failure Analysis & Aggregation
# ---------------------------------------------------------------------------


def test_failure_analysis_aggregation():
    """Verify FailureAnalysisReport aggregates by category, stage, strategy, and version."""
    res_fail1 = TaskRunResult(
        task_id="SWE-SYN-001",
        category="syntax_validation",
        status="FAIL",
        duration_seconds=1.5,
        tests_passed=0,
        tests_failed=1,
        verification_passed=False,
        recovery_attempts=1,
        files_changed=0,
        recovery_strategies=("ast_fix",),
        rollback_events=0,
        failure_category="syntax_failure",
        error_message="SyntaxError on line 2",
    )
    res_fail2 = TaskRunResult(
        task_id="SWE-SEC-001",
        category="recovery_challenge",
        status="FAIL",
        duration_seconds=2.0,
        tests_passed=0,
        tests_failed=1,
        verification_passed=False,
        recovery_attempts=2,
        files_changed=0,
        recovery_strategies=("boundary_check", "strict_filter"),
        rollback_events=1,
        failure_category="security_failure",
        error_message="Path traversal permitted",
    )
    res_pass = TaskRunResult(
        task_id="SWE-BUG-001",
        category="bug_fix",
        status="PASS",
        duration_seconds=1.0,
        tests_passed=1,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=0,
        files_changed=1,
    )

    tasks_lookup = {
        "SWE-SYN-001": BenchmarkTask(
            task_id="SWE-SYN-001",
            name="Validator Syntax",
            category=BenchmarkCategory.SYNTAX_VALIDATION,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="fix syntax",
            workspace_files={"a.py": "x=1"},
            test_files={"t.py": "assert True"},
            failure_category="syntax_failure",
        ),
        "SWE-SEC-001": BenchmarkTask(
            task_id="SWE-SEC-001",
            name="Path Security",
            category=BenchmarkCategory.RECOVERY_CHALLENGE,
            difficulty=BenchmarkDifficulty.HARD,
            problem_statement="block traversal",
            workspace_files={"a.py": "x=1"},
            test_files={"t.py": "assert True"},
            failure_category="security_failure",
        ),
    }

    report = FailureAnalysisReport.from_results(
        [res_fail1, res_fail2, res_pass], task_lookup=tasks_lookup, version="6.0.0"
    )

    assert report.total_failures == 2
    assert report.failures_by_category["syntax_failure"] == 1
    assert report.failures_by_category["security_failure"] == 1
    assert report.failures_by_strategy["ast_fix"] == 1
    assert report.failures_by_strategy["strict_filter"] == 1
    assert report.failures_by_benchmark["SWE-SYN-001"] == 1
    assert report.failures_by_benchmark["SWE-SEC-001"] == 1
    assert report.failures_by_version["6.0.0"] == 2

    assert len(report.records) == 2
    sec_rec = next(r for r in report.records if r.task_id == "SWE-SEC-001")
    assert sec_rec.rollback_performed is True
    assert sec_rec.strategy_selected == "strict_filter"

    d = report.to_dict()
    assert d["total_failures"] == 2
    assert "aggregations" in d


# ---------------------------------------------------------------------------
# 5. Experiment Tracking, Immutability & Secret Redaction
# ---------------------------------------------------------------------------


def test_experiment_immutability_and_redaction():
    """Verify ExperimentRecord is immutable and redacts known secrets from config."""
    tracker = ExperimentTracker(RedactionEngine())
    runner = BenchmarkRunner()

    report = runner.run_suite(suite="smoke", auto_repair=True)
    metrics = EngineeringMetrics.compute_from_results(report.results)
    failures = FailureAnalysisReport.from_results(report.results)

    config_with_secrets = {
        "provider": "gemini",
        "api_key": "AIzaSySecretApiKey12345",
        "token": "ghp_1234567890abcdef",
        "nested": {"secret_token": "bearer xyz987"},
    }

    experiment = tracker.create_experiment(
        report=report,
        metrics=metrics,
        failure_analysis=failures,
        configuration=config_with_secrets,
        orion_version="6.0.0",
    )

    assert experiment.experiment_id.startswith("EXP-")
    assert experiment.orion_version == "6.0.0"

    # Verify secret redaction
    cfg = experiment.configuration
    assert "[REDACTED" in cfg["api_key"]
    assert "[REDACTED" in cfg["token"]
    assert "[REDACTED" in cfg["nested"]["secret_token"]

    # Verify immutability (frozen dataclass)
    with pytest.raises(FrozenInstanceError):
        experiment.orion_version = "7.0.0"  # type: ignore

    # Verify reproducibility components are exposed
    assert len(experiment.deterministic_components) > 0
    assert len(experiment.nondeterministic_components) > 0


# ---------------------------------------------------------------------------
# 6. Version Comparison Across Benchmark Runs
# ---------------------------------------------------------------------------


def test_cross_version_comparison():
    """Verify VersionComparisonResult computes empirical differences between experiments."""
    tracker = ExperimentTracker()

    # Base experiment: 50% pass rate, 5.0s duration
    res_base_pass = TaskRunResult(
        task_id="TASK-1",
        category="bug_fix",
        status="PASS",
        duration_seconds=5.0,
        tests_passed=1,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=0,
        files_changed=1,
    )
    res_base_fail = TaskRunResult(
        task_id="TASK-2",
        category="bug_fix",
        status="FAIL",
        duration_seconds=5.0,
        tests_passed=0,
        tests_failed=1,
        verification_passed=False,
        recovery_attempts=1,
        files_changed=0,
    )
    report_base = BenchmarkReport(
        benchmark_id="b-1",
        suite_name="test",
        started_at="2026-10-01T00:00:00Z",
        completed_at="2026-10-01T00:00:10Z",
        total_tasks=2,
        passed_tasks=1,
        failed_tasks=1,
        pass_at_1_rate=0.5,
        verification_completeness=0.5,
        recovery_success_rate=0.0,
        mean_duration_seconds=5.0,
        results=(res_base_pass, res_base_fail),
    )
    metrics_base = EngineeringMetrics.compute_from_results(report_base.results)
    failures_base = FailureAnalysisReport.from_results(report_base.results)
    exp_base = tracker.create_experiment(
        report=report_base,
        metrics=metrics_base,
        failure_analysis=failures_base,
        orion_version="5.0.0",
    )

    # Target experiment: 100% pass rate, 2.0s duration
    res_tgt_1 = TaskRunResult(
        task_id="TASK-1",
        category="bug_fix",
        status="PASS",
        duration_seconds=2.0,
        tests_passed=1,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=0,
        files_changed=1,
    )
    res_tgt_2 = TaskRunResult(
        task_id="TASK-2",
        category="bug_fix",
        status="PASS",
        duration_seconds=2.0,
        tests_passed=1,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=1,
        files_changed=1,
    )
    report_tgt = BenchmarkReport(
        benchmark_id="b-2",
        suite_name="test",
        started_at="2026-10-02T00:00:00Z",
        completed_at="2026-10-02T00:00:04Z",
        total_tasks=2,
        passed_tasks=2,
        failed_tasks=0,
        pass_at_1_rate=1.0,
        verification_completeness=1.0,
        recovery_success_rate=1.0,
        mean_duration_seconds=2.0,
        results=(res_tgt_1, res_tgt_2),
    )
    metrics_tgt = EngineeringMetrics.compute_from_results(report_tgt.results)
    failures_tgt = FailureAnalysisReport.from_results(report_tgt.results)
    exp_tgt = tracker.create_experiment(
        report=report_tgt,
        metrics=metrics_tgt,
        failure_analysis=failures_tgt,
        orion_version="6.0.0",
    )

    comparison = tracker.compare_experiments(exp_base.experiment_id, exp_tgt.experiment_id)

    assert comparison.base_version == "5.0.0"
    assert comparison.target_version == "6.0.0"
    assert comparison.pass_rate_delta == 0.5  # 1.0 - 0.5
    assert comparison.duration_delta_seconds == -3.0  # 2.0 - 5.0
    assert "TASK-2" in comparison.newly_passing
    assert len(comparison.newly_failing) == 0
    assert "TASK-1" in comparison.performance_improved
    assert "TASK-2" in comparison.performance_improved
    assert "pass rate delta=+50.00%" in comparison.summary


# ---------------------------------------------------------------------------
# 7. Evaluation REST API Endpoints & Contracts
# ---------------------------------------------------------------------------


def test_api_evaluation_endpoints_full_lifecycle(eval_server):
    """Test full API lifecycle: list benchmarks, run evaluation, query metrics, and compare."""
    base_url, _, _ = eval_server

    # 1. GET /api/v1/evaluation/benchmarks
    req_bench = Request(f"{base_url}/api/v1/evaluation/benchmarks")
    with urlopen(req_bench) as resp:
        assert resp.status == HTTPStatus.OK
        b_data = json.loads(resp.read().decode("utf-8"))
        assert "suites" in b_data
        assert "taxonomy" in b_data["suites"]

    # 2. POST /api/v1/evaluation/run (Run 1: Passing smoke suite)
    payload1 = json.dumps({"suite": "smoke", "auto_repair": True}).encode("utf-8")
    req_run1 = Request(
        f"{base_url}/api/v1/evaluation/run",
        data=payload1,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_run1) as resp:
        assert resp.status == HTTPStatus.CREATED
        exp1_data = json.loads(resp.read().decode("utf-8"))
        assert "experiment_id" in exp1_data
        exp1_id = exp1_data["experiment_id"]
        assert exp1_data["metrics"]["mission"]["mission_success_rate"] == 1.0

    # 3. POST /api/v1/evaluation/run (Run 2: Failing smoke suite unrepaired)
    payload2 = json.dumps({"suite": "smoke", "auto_repair": False}).encode("utf-8")
    req_run2 = Request(
        f"{base_url}/api/v1/evaluation/run",
        data=payload2,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_run2) as resp:
        assert resp.status == HTTPStatus.CREATED
        exp2_data = json.loads(resp.read().decode("utf-8"))
        exp2_id = exp2_data["experiment_id"]
        assert exp2_data["metrics"]["mission"]["mission_success_rate"] == 0.0

    # 4. GET /api/v1/evaluation/runs
    req_list = Request(f"{base_url}/api/v1/evaluation/runs")
    with urlopen(req_list) as resp:
        assert resp.status == HTTPStatus.OK
        runs_data = json.loads(resp.read().decode("utf-8"))
        assert runs_data["total"] >= 2

    # 5. GET /api/v1/evaluation/runs/{id}
    req_get1 = Request(f"{base_url}/api/v1/evaluation/runs/{exp1_id}")
    with urlopen(req_get1) as resp:
        assert resp.status == HTTPStatus.OK
        detail = json.loads(resp.read().decode("utf-8"))
        assert detail["experiment_id"] == exp1_id

    # 6. GET /api/v1/evaluation/runs/{id}/metrics
    req_metrics = Request(f"{base_url}/api/v1/evaluation/runs/{exp1_id}/metrics")
    with urlopen(req_metrics) as resp:
        assert resp.status == HTTPStatus.OK
        m_data = json.loads(resp.read().decode("utf-8"))
        assert m_data["mission"]["mission_success_rate"] == 1.0

    # 7. GET /api/v1/evaluation/runs/{id}/failures
    req_failures = Request(f"{base_url}/api/v1/evaluation/runs/{exp2_id}/failures")
    with urlopen(req_failures) as resp:
        assert resp.status == HTTPStatus.OK
        f_data = json.loads(resp.read().decode("utf-8"))
        assert f_data["total_failures"] == 2

    # 8. POST /api/v1/evaluation/compare
    compare_payload = json.dumps({"base_id": exp2_id, "target_id": exp1_id}).encode("utf-8")
    req_compare = Request(
        f"{base_url}/api/v1/evaluation/compare",
        data=compare_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_compare) as resp:
        assert resp.status == HTTPStatus.OK
        comp_data = json.loads(resp.read().decode("utf-8"))
        assert comp_data["metrics_delta"]["pass_rate_delta"] == 1.0

    # 9. GET /api/v1/evaluation/compare?base_id=...&target_id=...
    req_compare_get = Request(
        f"{base_url}/api/v1/evaluation/compare?base_id={exp2_id}&target_id={exp1_id}"
    )
    with urlopen(req_compare_get) as resp:
        assert resp.status == HTTPStatus.OK
        comp_get_data = json.loads(resp.read().decode("utf-8"))
        assert comp_get_data["metrics_delta"]["pass_rate_delta"] == 1.0


# ---------------------------------------------------------------------------
# 8. Security Boundaries & Evidence Integrity
# ---------------------------------------------------------------------------


def test_path_traversal_guard_task_execution(tmp_path: Path):
    """Verify security benchmark SWE-SEC-001 correctly exercises path containment."""
    runner = BenchmarkRunner(output_dir=tmp_path / "artifacts")
    res = runner.run_task(TASK_SECURITY_TRAVERSAL_GUARD, tmp_path / "ws_sec", auto_repair=True)
    assert res.task_id == "SWE-SEC-001"
    assert res.status == "PASS"
    assert res.verification_passed is True


def test_evidence_integrity_traceability(tmp_path: Path):
    """Verify every metric and report can be traced back to actual ledger items."""
    runner = BenchmarkRunner()
    res = runner.run_task(TASK_BUG_FIX_CALCULATOR, tmp_path / "ws_trace", auto_repair=True)

    # Invariant: Evidence count reflects actual stages executed
    assert res.evidence_count >= 5
    assert res.verification_passed is True

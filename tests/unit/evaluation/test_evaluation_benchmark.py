"""Unit and integration tests for Phase 9 Evaluation, Benchmarking, and Reporting."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService
from orion.core.evaluation.corpus import (
    SMOKE_CORPUS,
    STANDARD_CORPUS,
    get_benchmark_suite,
)
from orion.core.evaluation.models import (
    BenchmarkCategory,
    BenchmarkDifficulty,
    BenchmarkReport,
    BenchmarkTask,
    TaskRunResult,
    get_system_environment_metadata,
)
from orion.core.evaluation.runner import BenchmarkRunner


@pytest.fixture
def benchmark_server(tmp_path: Path):
    """Fixture providing an Orion server with benchmark endpoints enabled."""
    repo = tmp_path / "bench_workspace"
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
# 1. Benchmark Task & Model Validation Tests
# ---------------------------------------------------------------------------


def test_benchmark_task_validation():
    """Verify BenchmarkTask enforces strict required fields and positive timeouts."""
    with pytest.raises(ValueError, match="task_id cannot be empty"):
        BenchmarkTask(
            task_id="",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Fix",
            workspace_files={"a.py": "x=1"},
            test_files={"t.py": "assert True"},
        )

    with pytest.raises(ValueError, match="workspace_files must contain"):
        BenchmarkTask(
            task_id="T1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Fix",
            workspace_files={},
            test_files={"t.py": "assert True"},
        )

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        BenchmarkTask(
            task_id="T1",
            name="Valid",
            category=BenchmarkCategory.BUG_FIX,
            difficulty=BenchmarkDifficulty.EASY,
            problem_statement="Fix",
            workspace_files={"a.py": "x=1"},
            test_files={"t.py": "assert True"},
            timeout_seconds=0,
        )


def test_benchmark_task_serialization():
    """Verify BenchmarkTask serializes correctly to dictionary."""
    task = BenchmarkTask(
        task_id="TEST-001",
        name="Sample Fix",
        category=BenchmarkCategory.BUG_FIX,
        difficulty=BenchmarkDifficulty.EASY,
        problem_statement="Fix something",
        workspace_files={"src/a.py": "def foo(): return 1"},
        test_files={"tests/test_a.py": "from src.a import foo; assert foo() == 1"},
        target_files=("src/a.py",),
    )
    d = task.to_dict()
    assert d["task_id"] == "TEST-001"
    assert d["category"] == "bug_fix"
    assert d["difficulty"] == "easy"
    assert "src/a.py" in d["workspace_files"]
    assert "tests/test_a.py" in d["test_files"]


# ---------------------------------------------------------------------------
# 2. Benchmark Corpus Tests
# ---------------------------------------------------------------------------


def test_benchmark_corpus_retrieval():
    """Verify standardized benchmark suites are registered and retrievable."""
    std = get_benchmark_suite("standard")
    assert len(std) == len(STANDARD_CORPUS)
    assert len(std) >= 4

    smoke = get_benchmark_suite("smoke")
    assert len(smoke) == len(SMOKE_CORPUS)
    assert len(smoke) >= 2

    with pytest.raises(KeyError, match="Unknown benchmark suite"):
        get_benchmark_suite("non_existent_suite")


# ---------------------------------------------------------------------------
# 3. Environment Metadata & Scorecard Formatting
# ---------------------------------------------------------------------------


def test_system_environment_metadata():
    """Verify runtime environment metadata captures OS, Python version, and timestamp."""
    meta = get_system_environment_metadata()
    assert "platform" in meta
    assert "python_version" in meta
    assert "captured_at" in meta


def test_benchmark_report_markdown_scorecard():
    """Verify BenchmarkReport renders a valid Markdown scorecard with table and metrics."""
    res1 = TaskRunResult(
        task_id="TASK-01",
        category="bug_fix",
        status="PASS",
        duration_seconds=1.25,
        tests_passed=2,
        tests_failed=0,
        verification_passed=True,
        recovery_attempts=0,
        files_changed=1,
    )
    report = BenchmarkReport(
        benchmark_id="bench-1234",
        suite_name="test_suite",
        started_at="2026-10-03T01:00:00Z",
        completed_at="2026-10-03T01:00:10Z",
        total_tasks=1,
        passed_tasks=1,
        failed_tasks=0,
        pass_at_1_rate=1.0,
        verification_completeness=1.0,
        recovery_success_rate=1.0,
        mean_duration_seconds=1.25,
        results=(res1,),
        environment={"platform": "TestOS", "python_version": "3.12.0"},
    )

    md = report.to_markdown()
    assert "# ORION Benchmark Scorecard" in md
    assert "Pass@1 Rate" in md
    assert "100.0%" in md
    assert "TASK-01" in md
    assert "PASS" in md


# ---------------------------------------------------------------------------
# 4. Benchmark Runner Execution Tests
# ---------------------------------------------------------------------------


def test_benchmark_runner_single_task(tmp_path: Path):
    """Verify BenchmarkRunner executes a single benchmark task in an isolated workspace."""
    runner = BenchmarkRunner(output_dir=tmp_path / "artifacts")
    task = SMOKE_CORPUS[0]  # Calculator task

    run_res = runner.run_task(task, tmp_path / "ws_task_0")
    assert run_res.task_id == task.task_id
    assert run_res.status == "PASS"
    assert run_res.verification_passed is True
    assert run_res.duration_seconds > 0.0
    assert run_res.tests_passed >= 1


def test_benchmark_runner_suite_execution(tmp_path: Path):
    """Verify BenchmarkRunner executes a full suite and produces disk artifacts."""
    artifacts_dir = tmp_path / "bench_output"
    runner = BenchmarkRunner(output_dir=artifacts_dir)

    report = runner.run_suite(suite=SMOKE_CORPUS)
    assert report.total_tasks == len(SMOKE_CORPUS)
    assert report.passed_tasks == len(SMOKE_CORPUS)
    assert report.failed_tasks == 0
    assert report.pass_at_1_rate == 1.0
    assert report.verification_completeness == 1.0

    # Verify artifacts were generated
    json_reports = list(artifacts_dir.glob("benchmark_report_*.json"))
    md_reports = list(artifacts_dir.glob("benchmark_scorecard_*.md"))
    assert len(json_reports) == 1
    assert len(md_reports) == 1

    loaded = json.loads(json_reports[0].read_text(encoding="utf-8"))
    assert loaded["metrics"]["pass_at_1_rate"] == 1.0


# ---------------------------------------------------------------------------
# 5. Benchmark API Integration Tests
# ---------------------------------------------------------------------------


def test_api_list_benchmarks(benchmark_server):
    """Test GET /api/v1/benchmarks returns available benchmark suites and tasks."""
    base_url, _, _ = benchmark_server
    req = Request(f"{base_url}/api/v1/benchmarks")

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert "suites" in data
        assert "standard" in data["suites"]
        assert "smoke" in data["suites"]
        assert data["total_suites"] == 2


def test_api_run_benchmark_smoke_suite(benchmark_server):
    """Test POST /api/v1/benchmarks/run executes suite and returns certified report."""
    base_url, _, _ = benchmark_server
    payload = json.dumps({"suite": "smoke"}).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/benchmarks/run",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        report = json.loads(resp.read().decode("utf-8"))
        assert "benchmark_id" in report
        assert report["suite_name"] == "smoke"
        assert report["metrics"]["pass_at_1_rate"] == 1.0
        assert len(report["results"]) == 2

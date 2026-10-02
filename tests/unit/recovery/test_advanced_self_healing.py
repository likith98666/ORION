"""Unit tests for ORION V5 Advanced Self-Healing System."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService
from orion.core.recovery.advanced.memory import AdaptiveRecoveryMemory
from orion.core.recovery.advanced.planner import (
    AdaptiveRecoveryPlanner,
    RecoveryStrategyType,
)
from orion.core.recovery.advanced.rollback import (
    FileSnapshot,
    IntelligentRollbackManager,
    WorkspaceSnapshot,
)
from orion.core.recovery.advanced.simulation import RecoverySimulator
from orion.core.recovery.advanced.taxonomy import (
    FailureCategory,
    FailureClassifier,
)
from orion.core.swe.evidence import EvidenceCategory, EvidenceItem, EvidenceLevel
from orion.core.swe.recovery.budget import RecoveryBudget
from orion.core.swe.stages import SWETaskStage


def test_failure_classifier_syntax_error() -> None:
    raw_error = (
        'File "src/calculator.py", line 42\n'
        "    def add(a, b\n"
        "                ^\n"
        "SyntaxError: closing parenthesis ')' does not match opening parenthesis '('\n"
    )
    diag = FailureClassifier.classify(raw_error)
    assert diag.category == FailureCategory.SYNTAX_FAILURE
    assert diag.target_file == "src/calculator.py"
    assert diag.line_number == 42
    assert "SyntaxError" in diag.error_message

    d = diag.to_dict()
    assert d["category"] == "syntax_failure"
    assert d["target_file"] == "src/calculator.py"
    assert d["line_number"] == 42


def test_failure_classifier_categories() -> None:
    cases = [
        ("TypeError: unsupported operand type(s)", FailureCategory.TYPE_FAILURE),
        ("ModuleNotFoundError: No module named 'foobar'", FailureCategory.IMPORT_FAILURE),
        ("AssertionError: assert 1 == 2", FailureCategory.ASSERTION_FAILURE),
        ("Operation timed out after 30 seconds", FailureCategory.TIMEOUT),
        ("patch conflict: hunk #1 failed", FailureCategory.PATCH_CONFLICT),
        ("PermissionDenied: not allowed to write", FailureCategory.SECURITY_FAILURE),
        ("No matching distribution found for pkg", FailureCategory.DEPENDENCY_FAILURE),
        ("MemoryError: out of memory", FailureCategory.RESOURCE_FAILURE),
        ("Detected regression in suite", FailureCategory.TEST_REGRESSION),
        ("Some totally unrecognized error string", FailureCategory.UNKNOWN),
    ]
    for text, expected in cases:
        diag = FailureClassifier.classify(text)
        assert diag.category == expected, f"Failed for text '{text}': got {diag.category}"


def test_recovery_simulator_safe_vs_unsafe(tmp_path: Path) -> None:
    sim = RecoverySimulator()

    # Safe simulation
    res_safe = sim.simulate(
        action_type="targeted_patch_repair",
        target_files=["src/foo.py", "src/bar.py"],
        estimated_duration_seconds=5.0,
        max_duration_budget=30.0,
    )
    assert res_safe.is_safe_to_execute is True
    assert res_safe.predicted_risk == "low"
    assert len(res_safe.expected_tests_impacted) == 2

    # Unsafe due to budget
    res_budget = sim.simulate(
        action_type="targeted_patch_repair",
        target_files=["src/foo.py"],
        estimated_duration_seconds=40.0,
        max_duration_budget=30.0,
    )
    assert res_budget.is_safe_to_execute is False
    assert res_budget.predicted_risk == "high"

    # Unsafe due to protected file rule
    res_forbidden = sim.simulate(
        action_type="targeted_patch_repair",
        target_files=[".env", "pyproject.toml"],
        estimated_duration_seconds=5.0,
    )
    assert res_forbidden.is_safe_to_execute is False
    assert res_forbidden.predicted_risk == "critical"

    # High risk due to blast radius count
    res_large = sim.simulate(
        action_type="targeted_patch_repair",
        target_files=[f"src/file_{i}.py" for i in range(7)],
        estimated_duration_seconds=5.0,
    )
    assert res_large.predicted_risk == "high"

    # Repetition of failed strategy elevates risk
    res_rep = sim.simulate(
        action_type="restore_snapshot",
        target_files=["src/foo.py"],
        past_failed_strategies=["restore_snapshot"],
    )
    assert res_rep.predicted_risk == "high"


def test_adaptive_recovery_memory() -> None:
    mem = AdaptiveRecoveryMemory(max_history=5)
    diag = FailureClassifier.classify("TypeError: invalid argument")

    # Record two attempts
    mem.record_attempt(
        attempt_number=1,
        diagnosis=diag,
        strategy_name="targeted_patch_repair",
        success=False,
        duration_seconds=3.5,
    )
    mem.record_attempt(
        attempt_number=2,
        diagnosis=diag,
        strategy_name="restore_snapshot",
        success=True,
        duration_seconds=1.5,
    )

    failed = mem.get_failed_strategies_for_failure(FailureCategory.TYPE_FAILURE)
    assert failed == ["targeted_patch_repair"]

    metrics = mem.get_strategy_metrics()
    assert "targeted_patch_repair" in metrics
    assert metrics["targeted_patch_repair"]["success_rate"] == 0.0
    assert metrics["targeted_patch_repair"]["attempts"] == 1

    assert "restore_snapshot" in metrics
    assert metrics["restore_snapshot"]["success_rate"] == 1.0
    assert metrics["restore_snapshot"]["mean_duration_seconds"] == 1.5

    # Test history cap
    for i in range(10):
        mem.record_attempt(
            attempt_number=i + 3,
            diagnosis=diag,
            strategy_name="dummy",
            success=True,
            duration_seconds=1.0,
        )
    assert len(mem._history) == 5

    mem.clear()
    assert len(mem._history) == 0


def test_intelligent_rollback_manager(tmp_path: Path) -> None:
    # Setup test workspace
    f1 = tmp_path / "src" / "module_a.py"
    f2 = tmp_path / "src" / "module_b.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("def a(): return 1\n", encoding="utf-8")
    f2.write_text("def b(): return 2\n", encoding="utf-8")

    mgr = IntelligentRollbackManager(tmp_path)
    snapshot = mgr.capture_snapshot()

    assert len(snapshot.files) == 2
    assert "src/module_a.py" in snapshot.files
    assert "src/module_b.py" in snapshot.files

    # Integrity matches initially
    is_valid, drift = mgr.verify_integrity(snapshot)
    assert is_valid is True
    assert len(drift) == 0

    # Modify f1, delete f2, add f3
    f1.write_text("corrupted content", encoding="utf-8")
    f2.unlink()
    f3 = tmp_path / "src" / "module_c.py"
    f3.write_text("untracked", encoding="utf-8")

    is_valid, drift = mgr.verify_integrity(snapshot)
    assert is_valid is False
    assert len(drift) == 2  # module_a modified, module_b missing

    # Test Partial Rollback: restore only module_a
    count, restored = mgr.rollback(snapshot, target_files=["src/module_a.py"])
    assert count == 1
    assert restored == ["src/module_a.py"]
    assert f1.read_text(encoding="utf-8") == "def a(): return 1\n"
    assert not f2.exists()
    assert f3.exists()

    # Test Full Rollback
    count, restored = mgr.rollback(snapshot)
    assert count == 2
    assert f1.read_text(encoding="utf-8") == "def a(): return 1\n"
    assert f2.exists()
    assert f2.read_text(encoding="utf-8") == "def b(): return 2\n"
    assert not f3.exists()  # Untracked file removed during full rollback

    # Integrity restored
    is_valid, drift = mgr.verify_integrity(snapshot)
    assert is_valid is True


def test_adaptive_recovery_planner() -> None:
    mem = AdaptiveRecoveryMemory()
    planner = AdaptiveRecoveryPlanner(memory=mem, max_attempts=3)

    # 1. Syntax error -> targeted_patch_repair
    syntax_diag = FailureClassifier.classify("SyntaxError: bad syntax", target_file="src/app.py")
    plan1 = planner.create_plan(syntax_diag, attempt_number=1)
    assert plan1.strategy == RecoveryStrategyType.TARGETED_PATCH_REPAIR
    assert plan1.requires_snapshot is True

    # 2. Record failure of targeted_patch_repair -> next attempt selects restore_snapshot
    mem.record_attempt(
        attempt_number=1,
        diagnosis=syntax_diag,
        strategy_name=RecoveryStrategyType.TARGETED_PATCH_REPAIR.value,
        success=False,
        duration_seconds=4.0,
    )
    plan2 = planner.create_plan(syntax_diag, attempt_number=2)
    assert plan2.strategy == RecoveryStrategyType.RESTORE_SNAPSHOT

    # 3. Security failure -> immediate abort_and_escalate
    sec_diag = FailureClassifier.classify(
        "PermissionDenied: cannot access", target_file="src/app.py"
    )
    plan_sec = planner.create_plan(sec_diag, attempt_number=1)
    assert plan_sec.strategy == RecoveryStrategyType.ABORT_AND_ESCALATE

    # 4. Exceeded max attempts -> abort_and_escalate
    plan_exhausted = planner.create_plan(syntax_diag, attempt_number=4)
    assert plan_exhausted.strategy == RecoveryStrategyType.ABORT_AND_ESCALATE


def test_service_v5_methods(tmp_path: Path) -> None:
    service = MissionAPIService(default_workspace_path=tmp_path)

    # Classify
    diag_dict = service.classify_failure("TypeError: bad type", target_file="src/main.py")
    assert diag_dict["category"] == "type_failure"
    assert diag_dict["target_file"] == "src/main.py"

    # Simulate
    sim_dict = service.simulate_recovery_action(
        action_type="restore_snapshot", target_files=["src/main.py"]
    )
    assert sim_dict["action_type"] == "restore_snapshot"
    assert sim_dict["is_safe_to_execute"] is True

    # Plan
    plan_dict = service.plan_adaptive_recovery(
        output_text="SyntaxError: invalid syntax",
        target_files=["src/main.py"],
        attempt_number=1,
    )
    assert plan_dict["strategy"] == "targeted_patch_repair"

    # Record & Metrics
    service.record_recovery_attempt(
        attempt_number=1,
        category="syntax_failure",
        error_message="SyntaxError",
        strategy_name="targeted_patch_repair",
        success=True,
        duration_seconds=2.1,
    )
    metrics = service.get_recovery_strategy_metrics()
    assert "targeted_patch_repair" in metrics
    assert metrics["targeted_patch_repair"]["success_rate"] == 1.0


def test_server_v5_http_endpoints(tmp_path: Path) -> None:
    service = MissionAPIService(default_workspace_path=tmp_path)

    class CustomHandler(OrionAPIHandler):
        pass

    CustomHandler.service = service

    server = HTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. POST /api/v1/recovery/classify
        payload1 = json.dumps(
            {"output_text": "TypeError: unsupported operand", "target_file": "src/calc.py"}
        ).encode("utf-8")
        req1 = Request(
            f"{base_url}/api/v1/recovery/classify",
            data=payload1,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req1) as resp1:
            assert resp1.status == HTTPStatus.OK
            res_classify = json.loads(resp1.read().decode("utf-8"))
            assert res_classify["category"] == "type_failure"

        # 2. POST /api/v1/recovery/simulate
        payload2 = json.dumps(
            {"action_type": "restore_snapshot", "target_files": ["src/calc.py"]}
        ).encode("utf-8")
        req2 = Request(
            f"{base_url}/api/v1/recovery/simulate",
            data=payload2,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req2) as resp2:
            assert resp2.status == HTTPStatus.OK
            res_sim = json.loads(resp2.read().decode("utf-8"))
            assert res_sim["is_safe_to_execute"] is True

        # 3. POST /api/v1/recovery/plan
        payload3 = json.dumps(
            {"output_text": "AssertionError: 1 != 2", "target_files": ["src/calc.py"]}
        ).encode("utf-8")
        req3 = Request(
            f"{base_url}/api/v1/recovery/plan",
            data=payload3,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req3) as resp3:
            assert resp3.status == HTTPStatus.OK
            res_plan = json.loads(resp3.read().decode("utf-8"))
            assert res_plan["strategy"] == "targeted_patch_repair"

        # 4. GET /api/v1/recovery/metrics
        req4 = Request(f"{base_url}/api/v1/recovery/metrics")
        with urlopen(req4) as resp4:
            assert resp4.status == HTTPStatus.OK
            res_metrics = json.loads(resp4.read().decode("utf-8"))
            assert "metrics" in res_metrics
    finally:
        server.shutdown()
        server.server_close()


def test_rollback_path_traversal_protection(tmp_path: Path) -> None:
    """Verify IntelligentRollbackManager prevents path traversal attacks."""
    mgr = IntelligentRollbackManager(tmp_path)
    snap_id = mgr.capture_snapshot().snapshot_id
    bad_snap = WorkspaceSnapshot(snapshot_id=snap_id, root_dir=str(tmp_path))
    bad_snap.files["../../outside.py"] = FileSnapshot(
        rel_path="../../outside.py",
        sha256_hash="dummy",
        size_bytes=4,
        content=b"evil",
    )
    with pytest.raises(ValueError, match="Path traversal detected"):
        mgr.rollback(bad_snap, target_files=["../../outside.py"])


def test_planner_with_exhausted_budget() -> None:
    """Verify AdaptiveRecoveryPlanner escalates to ABORT_AND_ESCALATE when budget is exhausted."""
    from orion.core.swe.recovery.strategies import RecoveryStrategy

    budget = RecoveryBudget(max_total_attempts=1)
    budget.consume(RecoveryStrategy.RETRY_TEST, duration_seconds=1.0)
    assert budget.is_exhausted is True

    planner = AdaptiveRecoveryPlanner(budget=budget)
    syntax_diag = FailureClassifier.classify("SyntaxError: bad syntax", target_file="src/app.py")
    plan = planner.create_plan(syntax_diag, attempt_number=1)
    assert plan.strategy == RecoveryStrategyType.ABORT_AND_ESCALATE


def test_strategy_repetition_escalation() -> None:
    """Verify repeated failures exhaust candidate strategies and cleanly escalate to abort."""
    mem = AdaptiveRecoveryMemory()
    planner = AdaptiveRecoveryPlanner(memory=mem, max_attempts=5)
    syntax_diag = FailureClassifier.classify("SyntaxError: parse failure", target_file="src/app.py")

    # Attempt 1: picks targeted_patch_repair
    p1 = planner.create_plan(syntax_diag, attempt_number=1)
    assert p1.strategy == RecoveryStrategyType.TARGETED_PATCH_REPAIR

    # Record failure of targeted_patch_repair
    mem.record_attempt(1, syntax_diag, p1.strategy.value, success=False, duration_seconds=2.0)

    # Attempt 2: picks restore_snapshot
    p2 = planner.create_plan(syntax_diag, attempt_number=2)
    assert p2.strategy == RecoveryStrategyType.RESTORE_SNAPSHOT

    # Record failure of restore_snapshot
    mem.record_attempt(2, syntax_diag, p2.strategy.value, success=False, duration_seconds=2.0)

    # Attempt 3: all candidates exhausted -> abort_and_escalate
    p3 = planner.create_plan(syntax_diag, attempt_number=3)
    assert p3.strategy == RecoveryStrategyType.ABORT_AND_ESCALATE


def test_evidence_integrity_classification() -> None:
    """Verify recovery events follow strict CLAIMED -> OBSERVED -> VERIFIED evidence semantics."""
    item = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.RECOVERY_EVENT,
        stage=SWETaskStage.RUN_TESTS,
        source="recovery_coordinator",
        content="Restored 2 modified files to prior SHA-256 snapshot.",
        summary="Rollback executed cleanly",
    )
    assert item.level == EvidenceLevel.OBSERVED
    assert item.category == EvidenceCategory.RECOVERY_EVENT
    assert item.level != EvidenceLevel.VERIFIED

"""Deterministic Local Benchmark Suite for ORION Autonomous Software Engineering.

Provides reproducible benchmarks covering:
1. Bug diagnosis & code repair
2. Test repair & synchronization
3. Failure recovery & retry transparency
4. Security boundary enforcement
5. Unbounded evidence suppression
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.security import ApprovalRequiredError, ApprovalService
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.swe.coordinator import SWEWorkflowCoordinator
from orion.core.swe.evaluation import EvaluationStatus
from orion.core.swe.evidence import (
    MAX_EVIDENCE_CONTENT_LENGTH,
    EvidenceCategory,
    EvidenceLedger,
)
from orion.core.swe.formulation import ProposedFixPlan
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.tools.repository.factory import register_repository_tools
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.errors import PathOutsideWorkspaceError
from orion.core.workspace.models import Workspace


@dataclass(frozen=True)
class BenchmarkResult:
    """Captured benchmark execution metrics."""

    benchmark_id: str
    category: str
    objective: str
    elapsed_ms: float
    stages_completed: list[str]
    evidence_counts: dict[str, int]
    verification_passed: bool
    recovery_attempts: int
    final_status: str


def _create_swe_agent() -> Agent:
    return Agent.create(
        name="Benchmark-SWE-Agent",
        description="Autonomous benchmark agent",
        capabilities=frozenset({
            AgentCapability.REPOSITORY_ANALYSIS,
            AgentCapability.SOFTWARE_DEBUGGING,
            AgentCapability.REASONING,
            AgentCapability.CODE_MODIFICATION,
            AgentCapability.TESTING,
            AgentCapability.VERIFICATION,
            AgentCapability.WRITING,
        }),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({
                AgentPermission.READ_FILES,
                AgentPermission.WRITE_FILES,
                AgentPermission.CODE_EXECUTION,
            })
        ),
    )


def test_benchmark_bug_diagnosis_and_code_repair(tmp_path: Path):
    """Benchmark 1: Diagnose off-by-one / reversal bug, formulate fix, verify and evaluate."""
    start_time = time.perf_counter()
    repo = tmp_path / "str_repo"
    repo.mkdir(parents=True, exist_ok=True)
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Faulty implementation
    (src_dir / "utils.py").write_text(
        "def reverse_words(s: str) -> str:\n"
        "    return ' '.join(s.split(' '))\n",
        encoding="utf-8",
    )
    # Unit test asserting reversed words
    (tests_dir / "test_utils.py").write_text(
        "from src.utils import reverse_words\n\n"
        "def test_reverse():\n"
        "    assert reverse_words('hello world') == 'world hello'\n",
        encoding="utf-8",
    )
    (repo / "conftest.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.abspath('.'))\n",
        encoding="utf-8",
    )

    workspace = Workspace(repository_root=repo)
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, workspace)

    approval_service = ApprovalService(repository=InMemoryApprovalRepository())
    tool_executor = ToolExecutor(registry=registry, approval_service=approval_service)
    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=tool_executor,
        verification_engine=verification_engine,
        recovery_coordinator=recovery_coordinator,
    )
    agent = _create_swe_agent()

    # 1. Inspect
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    list_res = coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=agent,
        tool_name="list_files",
        arguments={"path": ".", "recursive": True},
    )
    assert list_res.success is True
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    # 2. Analyze
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    test_res1 = coordinator.execute_tool(
        stage=SWETaskStage.ANALYZE_FAILURE,
        agent=agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_utils.py"},
    )
    assert test_res1.output["exit_code"] != 0
    coordinator.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent",
        content="Diagnosed: words are not reversed before joining.",
    )
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    # 3. Formulate
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    plan = ProposedFixPlan(
        target_files=("src/utils.py",),
        intended_modification="Slice word list with [::-1]",
        expected_behavior="reverse_words returns words in reverse order",
        validation_strategy="run_tests tests/test_utils.py",
        constraints=("Do not change API signature",),
    )
    coordinator.record_formulation(plan)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    # 4. Implement
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    fixed_code = (
        "def reverse_words(s: str) -> str:\n"
        "    return ' '.join(s.split(' ')[::-1])\n"
    )
    exec_id = uuid4()
    with pytest.raises(ApprovalRequiredError) as exc_info:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=agent,
            tool_name="write_file",
            arguments={"path": "src/utils.py", "content": fixed_code},
            execution_id=exec_id,
        )
    approval_service.approve(request_id=exc_info.value.request_id, approver="tech-lead")
    write_res = coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=agent,
        tool_name="write_file",
        arguments={"path": "src/utils.py", "content": fixed_code},
        execution_id=exec_id,
        approval_id=exc_info.value.request_id,
    )
    assert write_res.success is True
    coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

    # 5. Run tests
    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_res2 = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_utils.py"},
    )
    assert test_res2.output["exit_code"] == 0
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    # 6. Verify
    coordinator.advance_stage(SWETaskStage.VERIFY)
    verif_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["1 passed"],
    )
    assert verif_res.status == VerificationStatus.PASSED
    coordinator.complete_stage(SWETaskStage.VERIFY)

    # 7. Report & Evaluate
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)
    report = coordinator.generate_report(summary="Fixed reverse_words with verified passing test.")

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    benchmark_result = BenchmarkResult(
        benchmark_id="BM-01-CODE-REPAIR",
        category="bug diagnosis & small code repair",
        objective="Repair reverse_words function to satisfy unit test",
        elapsed_ms=elapsed_ms,
        stages_completed=[s.value for s in coordinator.completed_stages],
        evidence_counts={
            "claimed": len(report.claimed_evidence),
            "observed": len(report.observed_evidence),
            "verified": len(report.verified_evidence),
        },
        verification_passed=coordinator.ledger.has_verified(SWETaskStage.VERIFY),
        recovery_attempts=0,
        final_status=report.status,
    )

    assert benchmark_result.final_status == "verified_success"
    assert benchmark_result.verification_passed is True
    assert benchmark_result.evidence_counts["verified"] == 1
    assert len(benchmark_result.stages_completed) == 7
    assert report.evaluation.status == EvaluationStatus.PASS


def test_benchmark_test_repair(tmp_path: Path):
    """Benchmark 2: Diagnose stale test assertion, formulate test repair, verify and evaluate."""
    repo = tmp_path / "test_repair_repo"
    repo.mkdir(parents=True, exist_ok=True)
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Implementation is correct
    (src_dir / "service.py").write_text(
        "def get_status() -> str:\n"
        "    return 'ONLINE'\n",
        encoding="utf-8",
    )
    # Test has stale assertion
    (tests_dir / "test_service.py").write_text(
        "from src.service import get_status\n\n"
        "def test_status():\n"
        "    assert get_status() == 'INITIALIZING'\n",
        encoding="utf-8",
    )
    (repo / "conftest.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.abspath('.'))\n",
        encoding="utf-8",
    )

    workspace = Workspace(repository_root=repo)
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, workspace)

    approval_service = ApprovalService(repository=InMemoryApprovalRepository())
    tool_executor = ToolExecutor(registry=registry, approval_service=approval_service)
    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=tool_executor,
        verification_engine=verification_engine,
        recovery_coordinator=recovery_coordinator,
    )
    agent = _create_swe_agent()

    # Step through workflow
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=agent,
        tool_name="read_file",
        arguments={"path": "src/service.py"},
    )
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.execute_tool(
        stage=SWETaskStage.ANALYZE_FAILURE,
        agent=agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_service.py"},
    )
    coordinator.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent",
        content=(
            "Diagnosed: test_status has outdated expected status 'INITIALIZING' "
            "instead of 'ONLINE'."
        ),
    )
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    plan = ProposedFixPlan(
        target_files=("tests/test_service.py",),
        intended_modification="Update test expected value to 'ONLINE'",
        expected_behavior="test_status passes",
        validation_strategy="run_tests tests/test_service.py",
        constraints=("Do not modify src/service.py",),
    )
    coordinator.record_formulation(plan)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    updated_test = (
        "from src.service import get_status\n\n"
        "def test_status():\n"
        "    assert get_status() == 'ONLINE'\n"
    )
    exec_id = uuid4()
    with pytest.raises(ApprovalRequiredError) as exc_info:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=agent,
            tool_name="write_file",
            arguments={"path": "tests/test_service.py", "content": updated_test},
            execution_id=exec_id,
        )
    approval_service.approve(request_id=exc_info.value.request_id, approver="lead")
    coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=agent,
        tool_name="write_file",
        arguments={"path": "tests/test_service.py", "content": updated_test},
        execution_id=exec_id,
        approval_id=exc_info.value.request_id,
    )
    coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_res = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_service.py"},
    )
    assert test_res.output["exit_code"] == 0
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    coordinator.advance_stage(SWETaskStage.VERIFY)
    verif_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["1 passed"],
    )
    assert verif_res.status == VerificationStatus.PASSED
    coordinator.complete_stage(SWETaskStage.VERIFY)

    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)
    report = coordinator.generate_report(
        summary="Repaired stale test assertion in test_service.py."
    )

    assert report.status == "verified_success"
    assert report.evaluation.status == EvaluationStatus.PASS
    assert report.evaluation.metrics.files_changed == 1
    assert report.is_verified_success is True


def test_benchmark_security_boundary_enforcement(tmp_path: Path):
    """Benchmark 3: Validate that workspace boundary violations are strictly intercepted."""
    workspace_root = tmp_path / "safe_zone"
    workspace_root.mkdir(parents=True, exist_ok=True)
    outside_secret = tmp_path / "secret.env"
    outside_secret.write_text("DB_PASSWORD=ultra_secret_key", encoding="utf-8")

    workspace = Workspace(repository_root=workspace_root)
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, workspace)

    tool_executor = ToolExecutor(registry=registry)
    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=tool_executor,
        verification_engine=verification_engine,
        recovery_coordinator=recovery_coordinator,
    )
    agent = _create_swe_agent()

    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)

    # 1. Attempt path traversal via read_file tool through coordinator
    tool_res = coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=agent,
        tool_name="read_file",
        arguments={"path": "../secret.env"},
    )
    assert tool_res.success is False
    assert any(
        term in str(tool_res.error).lower()
        for term in ("outside", "boundary", "security", "path")
    )

    # 2. Direct workspace containment validation raises PathOutsideWorkspaceError
    with pytest.raises(PathOutsideWorkspaceError):
        workspace.resolve_path("../secret.env")

    # 3. Verify no secret leaked into evidence ledger
    for item in coordinator.ledger.get_items():
        assert "ultra_secret_key" not in item.content
        for v in item.metadata.values():
            assert "ultra_secret_key" not in str(v)


def test_benchmark_unbounded_evidence_suppression():
    """Benchmark 4: Ensure oversized content is bounded to MAX_EVIDENCE_CONTENT_LENGTH."""
    ledger = EvidenceLedger()
    huge_stdout = "X" * 100_000  # 100 KB text output

    item = ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        category=EvidenceCategory.COMMAND_RESULT,
        content=huge_stdout,
        metadata={"raw_length": len(huge_stdout)},
    )

    # Content must be bounded and marked as truncated
    assert item.content.endswith("... [TRUNCATED]")
    assert len(item.content) <= MAX_EVIDENCE_CONTENT_LENGTH + 32
    assert item.metadata["content_truncated"] is True
    assert item.metadata["original_length"] == 100_000

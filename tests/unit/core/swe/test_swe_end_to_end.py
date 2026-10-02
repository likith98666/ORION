from pathlib import Path
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.observability.context import TelemetryContext
from orion.core.recovery.failures import FailureType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.security import ApprovalRequiredError, ApprovalService
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.swe.coordinator import SWEWorkflowCoordinator
from orion.core.swe.evidence import EvidenceCategory, EvidenceLevel
from orion.core.swe.formulation import ProposedFixPlan
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.tools.repository.factory import register_repository_tools
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.failure_adapter import VerificationFailureAdapter
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Create a temporary test repository with a faulty implementation and test suite."""
    repo = tmp_path / "calc_repo"
    repo.mkdir(parents=True, exist_ok=True)
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Faulty module: subtracts instead of adds
    code_file = src_dir / "math_lib.py"
    code_file.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a - b\n",
        encoding="utf-8",
    )

    # Unit test asserting correct addition
    test_file = tests_dir / "test_math_lib.py"
    test_file.write_text(
        "from src.math_lib import add\n\n"
        "def test_addition():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    # conftest to ensure src is in python path
    conftest_file = repo / "conftest.py"
    conftest_file.write_text(
        "import sys, os\n"
        "sys.path.insert(0, os.path.abspath('.'))\n",
        encoding="utf-8",
    )

    return repo


def test_deterministic_swe_workflow_end_to_end(test_repo: Path):
    """Deterministic end-to-end integration scenario across all 7 SWE workflow stages.

    Uses the real Stage 2 repository tools, real workspace containment, real subprocess pytest,
    real approval enforcement, and real verification engine.
    """
    workspace = Workspace(repository_root=test_repo)
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, workspace)

    approval_repository = InMemoryApprovalRepository()
    approval_service = ApprovalService(repository=approval_repository)
    tool_executor = ToolExecutor(
        registry=registry,
        approval_service=approval_service,
    )

    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

    telemetry = TelemetryContext(
        request_id=uuid4(),
        trace_id=uuid4(),
        task_id=uuid4(),
    )

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=tool_executor,
        verification_engine=verification_engine,
        recovery_coordinator=recovery_coordinator,
        telemetry_context=telemetry,
    )

    swe_agent = Agent.create(
        name="SWE-Engineer",
        description="Autonomous SWE agent with code and test privileges",
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

    # -------------------------------------------------------------
    # STAGE 1: INSPECT_REPOSITORY
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)

    list_res = coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=swe_agent,
        tool_name="list_files",
        arguments={"path": ".", "recursive": True},
    )
    assert list_res.success is True
    entries = [entry["path"] for entry in list_res.output["entries"]]
    assert any("math_lib.py" in e for e in entries)

    read_res = coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=swe_agent,
        tool_name="read_file",
        arguments={"path": "src/math_lib.py"},
    )
    assert read_res.success is True
    assert "return a - b" in read_res.output["content"]

    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    # -------------------------------------------------------------
    # STAGE 2: ANALYZE_FAILURE
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)

    # Run tests to reproduce failure
    test_res = coordinator.execute_tool(
        stage=SWETaskStage.ANALYZE_FAILURE,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    assert test_res.success is True
    assert test_res.output["exit_code"] != 0  # Test fails!
    assert "assert -1 == 5" in test_res.output["stdout"]

    coordinator.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent:debugger",
        content="Diagnosed: add() returns a - b instead of a + b.",
    )

    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    # -------------------------------------------------------------
    # STAGE 3: FORMULATE_FIX
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)

    plan = ProposedFixPlan(
        target_files=("src/math_lib.py",),
        intended_modification="Change 'return a - b' to 'return a + b'",
        expected_behavior="add(2, 3) evaluates to 5 and test_addition passes",
        validation_strategy="run_tests with target='tests/test_math_lib.py'",
        constraints=("Preserve function signature and type hints",),
    )
    coordinator.record_formulation(plan)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    # -------------------------------------------------------------
    # STAGE 4: IMPLEMENT_CHANGE
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)

    exec_id = uuid4()
    fixed_content = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    # Write tool is HIGH risk, must require approval
    with pytest.raises(ApprovalRequiredError) as exc_info:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=swe_agent,
            tool_name="write_file",
            arguments={"path": "src/math_lib.py", "content": fixed_content},
            execution_id=exec_id,
        )

    # Grant approval
    approval_service.approve(
        request_id=exc_info.value.request_id,
        approver="tech-lead",
        reason="Approved fix for math_lib add operation",
    )

    # Re-execute write_file with approval_id
    write_res = coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=swe_agent,
        tool_name="write_file",
        arguments={"path": "src/math_lib.py", "content": fixed_content},
        execution_id=exec_id,
        approval_id=exc_info.value.request_id,
    )
    assert write_res.success is True

    # Use diff tool to inspect changes
    diff_res = coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=swe_agent,
        tool_name="diff",
        arguments={
            "path": "src/math_lib.py",
            "comparison_content": "def add(a: int, b: int) -> int:\n    return a - b\n",
        },
    )
    assert diff_res.success is True
    assert diff_res.output["identical"] is False
    assert "return a + b" in diff_res.output["diff"]

    coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

    # -------------------------------------------------------------
    # STAGE 5: RUN_TESTS
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.RUN_TESTS)

    test_res2 = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    assert test_res2.success is True
    assert test_res2.output["exit_code"] == 0  # Tests pass!
    assert "1 passed" in test_res2.output["stdout"]

    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    # -------------------------------------------------------------
    # STAGE 6: VERIFY
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.VERIFY)

    verif_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["1 passed"],
    )
    assert verif_res.status == VerificationStatus.PASSED
    assert coordinator.ledger.has_verified(SWETaskStage.VERIFY) is True

    coordinator.complete_stage(SWETaskStage.VERIFY)

    # -------------------------------------------------------------
    # STAGE 7: GENERATE_REPORT
    # -------------------------------------------------------------
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

    report = coordinator.generate_report(summary="Fixed math_lib bug with verified test execution.")
    assert report.status == "verified_success"
    assert len(report.claimed_evidence) >= 2  # Formulation + diagnosis
    assert len(report.observed_evidence) >= 4  # Inspect, analyze test, write, validate test
    assert len(report.verified_evidence) == 1  # Verified test outcome

    # Verify that CLAIMED, OBSERVED, and VERIFIED remain strictly distinct
    claimed_levels = {e.level for e in report.claimed_evidence}
    observed_levels = {e.level for e in report.observed_evidence}
    verified_levels = {e.level for e in report.verified_evidence}

    assert claimed_levels == {EvidenceLevel.CLAIMED}
    assert observed_levels == {EvidenceLevel.OBSERVED}
    assert verified_levels == {EvidenceLevel.VERIFIED}

    # Verify evaluation details
    assert report.evaluation is not None
    assert report.evaluation.status.value == "pass"
    assert report.evaluation.criteria.workflow_completed is True
    assert report.evaluation.criteria.test_passed is True
    assert report.evaluation.criteria.verification_passed is True
    assert report.evaluation.criteria.evidence_complete is True
    assert report.evaluation.criteria.changes_traceable is True
    assert report.evaluation.metrics.tests_passed >= 1
    assert report.evaluation.metrics.verification_passed == 1
    assert report.evaluation.metrics.files_changed == 1
    assert report.is_verified_success is True


def test_swe_workflow_failure_recovery_loop(test_repo: Path):
    """Verify that a test failure produces structured failure and invokes RecoveryCoordinator."""
    workspace = Workspace(repository_root=test_repo)
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

    swe_agent = Agent.create(
        name="SWE-Engineer",
        description="SWE agent",
        capabilities=frozenset({
            AgentCapability.REPOSITORY_ANALYSIS,
            AgentCapability.SOFTWARE_DEBUGGING,
            AgentCapability.TESTING,
            AgentCapability.VERIFICATION,
        }),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.READ_FILES, AgentPermission.CODE_EXECUTION})
        ),
    )

    # Advance through to RUN_TESTS without fixing the bug
    for stage in [
        SWETaskStage.INSPECT_REPOSITORY,
        SWETaskStage.ANALYZE_FAILURE,
        SWETaskStage.FORMULATE_FIX,
        SWETaskStage.IMPLEMENT_CHANGE,
    ]:
        coordinator.advance_stage(stage)
        coordinator.complete_stage(stage)

    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_res = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    assert test_res.output["exit_code"] != 0
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    # VERIFY stage verifies that expected requirements failed
    coordinator.advance_stage(SWETaskStage.VERIFY)
    exec_id = uuid4()
    verif_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["1 passed"],
    )
    assert verif_res.status == VerificationStatus.FAILED
    assert coordinator.ledger.has_verified(SWETaskStage.VERIFY) is False

    # Convert failed verification to Failure
    failure = VerificationFailureAdapter.to_failure(verif_res)
    assert failure.failure_type == FailureType.VERIFICATION_FAILURE

    failed_execution = AgentExecution.create(
        agent_id=swe_agent.id,
        agent_task_id=uuid4(),
    )
    failed_execution.status = AgentExecutionStatus.FAILED
    failed_execution.failure = failure
    failed_execution.error_message = failure.message

    # Recovery coordinator evaluates failure
    recovery_result = coordinator.handle_stage_failure(failed_execution)
    assert recovery_result.decision.strategy is not None
    assert recovery_result.action is not None

    coordinator.complete_stage(SWETaskStage.VERIFY)
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

    # Final report must NOT be verified_success
    report = coordinator.generate_report()
    assert report.status == "failed"
    assert len(report.verified_evidence) == 0
    assert report.evaluation is not None
    assert report.evaluation.status.value == "fail"
    assert report.evaluation.criteria.verification_passed is False
    assert report.is_verified_success is False


def test_swe_workflow_recovery_retry_success(test_repo: Path):
    """Scenario C: Integration demonstrating failure -> recovery event -> retry -> verified success.

    Preserves full recovery transparency and audit trail in the evidence ledger.
    """
    workspace = Workspace(repository_root=test_repo)
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, workspace)

    approval_repository = InMemoryApprovalRepository()
    approval_service = ApprovalService(repository=approval_repository)
    tool_executor = ToolExecutor(
        registry=registry,
        approval_service=approval_service,
    )

    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    recovery_coordinator = RecoveryCoordinator(recovery_engine=RecoveryEngine())

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=tool_executor,
        verification_engine=verification_engine,
        recovery_coordinator=recovery_coordinator,
    )

    swe_agent = Agent.create(
        name="SWE-Engineer",
        description="SWE agent with code and test privileges",
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

    # 1. Inspect repository
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=swe_agent,
        tool_name="list_files",
        arguments={"path": ".", "recursive": True},
    )
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    # 2. Analyze failure
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.execute_tool(
        stage=SWETaskStage.ANALYZE_FAILURE,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    coordinator.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent:debugger",
        content="Bug observed in math_lib.",
    )
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    # 3. Formulate fix
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    plan = ProposedFixPlan(
        target_files=("src/math_lib.py",),
        intended_modification="Fix math_lib add implementation",
        expected_behavior="add(2, 3) evaluates to 5",
        validation_strategy="run_tests tests/test_math_lib.py",
        constraints=("Keep pure python",),
    )
    coordinator.record_formulation(plan)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    # 4. Attempt 1: Implement an incorrect change (returns a * b instead of a + b)
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    exec_id_1 = uuid4()
    bad_fix = "def add(a: int, b: int) -> int:\n    return a * b\n"

    with pytest.raises(ApprovalRequiredError) as exc_info:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=swe_agent,
            tool_name="write_file",
            arguments={"path": "src/math_lib.py", "content": bad_fix},
            execution_id=exec_id_1,
        )

    approval_service.approve(request_id=exc_info.value.request_id, approver="lead")
    coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=swe_agent,
        tool_name="write_file",
        arguments={"path": "src/math_lib.py", "content": bad_fix},
        execution_id=exec_id_1,
        approval_id=exc_info.value.request_id,
    )
    coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

    # 5. Attempt 1: Run tests (fails!)
    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_res_1 = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    assert test_res_1.output["exit_code"] != 0
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    # 6. Attempt 1: Verification fails -> Recovery triggered
    coordinator.advance_stage(SWETaskStage.VERIFY)
    verif_res_1 = coordinator.verify_fix(
        execution_id=exec_id_1,
        expected_requirements=["1 passed"],
    )
    assert verif_res_1.status == VerificationStatus.FAILED

    failure = VerificationFailureAdapter.to_failure(verif_res_1)
    failed_exec_1 = AgentExecution.create(
        agent_id=swe_agent.id,
        agent_task_id=uuid4(),
    )
    failed_exec_1.status = AgentExecutionStatus.FAILED
    failed_exec_1.failure = failure
    failed_exec_1.error_message = failure.message

    recovery_res = coordinator.handle_stage_failure(failed_exec_1)
    assert recovery_res.decision.strategy is not None

    # Verify recovery event is logged in evidence ledger
    recovery_items = coordinator.ledger.get_items(category=EvidenceCategory.RECOVERY_EVENT)
    assert len(recovery_items) == 1

    # 7. Attempt 2 (Retry): Re-enter IMPLEMENT_CHANGE to apply the correct change
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    exec_id_2 = uuid4()
    good_fix = "def add(a: int, b: int) -> int:\n    return a + b\n"

    with pytest.raises(ApprovalRequiredError) as exc_info2:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=swe_agent,
            tool_name="write_file",
            arguments={"path": "src/math_lib.py", "content": good_fix},
            execution_id=exec_id_2,
        )

    approval_service.approve(request_id=exc_info2.value.request_id, approver="lead")
    write_res_2 = coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=swe_agent,
        tool_name="write_file",
        arguments={"path": "src/math_lib.py", "content": good_fix},
        execution_id=exec_id_2,
        approval_id=exc_info2.value.request_id,
    )
    assert write_res_2.success is True

    # 8. Attempt 2: Re-run tests (passes!)
    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_res_2 = coordinator.execute_tool(
        stage=SWETaskStage.RUN_TESTS,
        agent=swe_agent,
        tool_name="run_tests",
        arguments={"target": "tests/test_math_lib.py"},
    )
    assert test_res_2.output["exit_code"] == 0
    assert "1 passed" in test_res_2.output["stdout"]

    # 9. Attempt 2: Re-verify (passes!)
    coordinator.advance_stage(SWETaskStage.VERIFY)
    verif_res_2 = coordinator.verify_fix(
        execution_id=exec_id_2,
        expected_requirements=["1 passed"],
    )
    assert verif_res_2.status == VerificationStatus.PASSED
    assert coordinator.ledger.has_verified(SWETaskStage.VERIFY) is True
    coordinator.complete_stage(SWETaskStage.VERIFY)

    # 10. Generate final report and evaluate
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)
    report = coordinator.generate_report(summary="Recovered from initial failure and verified fix.")

    assert report.status == "verified_success"
    assert report.evaluation is not None
    assert report.evaluation.status.value == "pass"
    assert report.evaluation.metrics.recovery_attempts == 1
    assert report.evaluation.metrics.verification_passed == 1
    assert report.evaluation.metrics.verification_failed == 1
    assert report.evaluation.criteria.recovery_transparent is True
    assert len(report.verified_evidence) == 1


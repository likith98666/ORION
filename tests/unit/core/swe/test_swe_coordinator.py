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
from orion.core.security.risk import ToolRiskLevel
from orion.core.swe.coordinator import SWEWorkflowCoordinator
from orion.core.swe.errors import (
    DisallowedFileModificationError,
    DisallowedStageToolError,
    MissingWorkspaceError,
    WorkflowSequenceError,
)
from orion.core.swe.evidence import EvidenceLevel
from orion.core.swe.formulation import ProposedFixPlan
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import ToolInputField, ToolInputSchema, ToolInputType
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.failure_adapter import VerificationFailureAdapter
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace


def _create_mock_tool(name: str, permission: AgentPermission, risk: ToolRiskLevel, output="ok"):
    return ToolDefinition(
        name=name,
        description=f"Mock {name}",
        permission=permission,
        risk_level=risk,
        input_schema=ToolInputSchema(
            fields=(
                ToolInputField(name="param", input_type=ToolInputType.STRING, required=False),
                ToolInputField(name="path", input_type=ToolInputType.STRING, required=False),
                ToolInputField(name="content", input_type=ToolInputType.STRING, required=False),
            )
        ),
        handler=lambda args: output,
    )


def _setup_coordinator(tmp_path: Path, with_approval=False):
    workspace = Workspace(repository_root=tmp_path)
    registry = InMemoryToolRegistry()

    # Register mock versions of the canonical tools
    registry.register(_create_mock_tool("list_files", AgentPermission.READ_FILES, ToolRiskLevel.LOW))
    registry.register(_create_mock_tool("read_file", AgentPermission.READ_FILES, ToolRiskLevel.LOW))
    registry.register(_create_mock_tool("search_files", AgentPermission.READ_FILES, ToolRiskLevel.LOW))
    registry.register(_create_mock_tool("diff", AgentPermission.READ_FILES, ToolRiskLevel.LOW))
    registry.register(_create_mock_tool("write_file", AgentPermission.WRITE_FILES, ToolRiskLevel.HIGH))
    registry.register(_create_mock_tool("apply_change", AgentPermission.WRITE_FILES, ToolRiskLevel.HIGH))
    registry.register(_create_mock_tool("run_tests", AgentPermission.CODE_EXECUTION, ToolRiskLevel.MEDIUM))

    approval_service = None
    if with_approval:
        approval_service = ApprovalService(repository=InMemoryApprovalRepository())

    tool_executor = ToolExecutor(
        registry=registry,
        approval_service=approval_service,
    )

    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)

    recovery_engine = RecoveryEngine()
    recovery_coordinator = RecoveryCoordinator(recovery_engine=recovery_engine)

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

    return coordinator, approval_service


def test_coordinator_requires_workspace():
    """Verify SWEWorkflowCoordinator rejects initialization without a Workspace."""
    verif_service = VerificationService(repository=InMemoryVerificationRepository())
    verification_engine = VerificationEngine(verification_service=verif_service)
    registry = InMemoryToolRegistry()
    tool_executor = ToolExecutor(registry=registry)

    with pytest.raises(MissingWorkspaceError):
        SWEWorkflowCoordinator(
            workspace=None,  # type: ignore
            tool_executor=tool_executor,
            verification_engine=verification_engine,
        )


def test_coordinator_enforces_stage_progression(tmp_path: Path):
    """Verify stages cannot be skipped or executed out of order."""
    coordinator, _ = _setup_coordinator(tmp_path)

    # Attempting to jump directly to IMPLEMENT_CHANGE must fail
    with pytest.raises(WorkflowSequenceError) as exc_info:
        coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    assert "Cannot advance to 'implement_change' before completing prior stage 'inspect_repository'" in str(exc_info.value)

    # Advance properly step by step
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    assert coordinator.current_stage == SWETaskStage.IMPLEMENT_CHANGE


def test_coordinator_tool_gating_inspect_repository(tmp_path: Path):
    """Verify tool gating during INSPECT_REPOSITORY prohibits write_file and run_tests."""
    coordinator, _ = _setup_coordinator(tmp_path)
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)

    agent = Agent.create(
        name="Inspector",
        description="Inspector agent",
        capabilities=frozenset({AgentCapability.REPOSITORY_ANALYSIS}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.READ_FILES, AgentPermission.WRITE_FILES, AgentPermission.CODE_EXECUTION})
        ),
    )

    # list_files is allowed
    result = coordinator.execute_tool(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        agent=agent,
        tool_name="list_files",
        arguments={},
    )
    assert result.success is True

    # write_file is prohibited in inspection stage
    with pytest.raises(DisallowedFileModificationError):
        coordinator.execute_tool(
            stage=SWETaskStage.INSPECT_REPOSITORY,
            agent=agent,
            tool_name="write_file",
            arguments={"path": "foo.py", "content": "x = 1"},
        )

    # run_tests is prohibited in inspection stage
    with pytest.raises(DisallowedStageToolError):
        coordinator.execute_tool(
            stage=SWETaskStage.INSPECT_REPOSITORY,
            agent=agent,
            tool_name="run_tests",
            arguments={},
        )


def test_coordinator_tool_gating_analyze_failure(tmp_path: Path):
    """Verify tool gating during ANALYZE_FAILURE allows run_tests but prohibits write_file."""
    coordinator, _ = _setup_coordinator(tmp_path)
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)

    agent = Agent.create(
        name="Debugger",
        description="Debugging agent",
        capabilities=frozenset({AgentCapability.SOFTWARE_DEBUGGING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.READ_FILES, AgentPermission.CODE_EXECUTION, AgentPermission.WRITE_FILES})
        ),
    )

    # run_tests is allowed in ANALYZE_FAILURE
    result = coordinator.execute_tool(
        stage=SWETaskStage.ANALYZE_FAILURE,
        agent=agent,
        tool_name="run_tests",
        arguments={},
    )
    assert result.success is True

    # write_file is prohibited in ANALYZE_FAILURE
    with pytest.raises(DisallowedFileModificationError):
        coordinator.execute_tool(
            stage=SWETaskStage.ANALYZE_FAILURE,
            agent=agent,
            tool_name="write_file",
            arguments={"path": "foo.py", "content": "x = 1"},
        )


def test_coordinator_formulate_fix_recording(tmp_path: Path):
    """Verify FORMULATE_FIX records structured proposed fix plan."""
    coordinator, _ = _setup_coordinator(tmp_path)
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)

    plan = ProposedFixPlan(
        target_files=("src/calculator.py",),
        intended_modification="Fix operator precedence in evaluate()",
        expected_behavior="Parentheses are respected in math expressions",
        validation_strategy="Run tests in tests/test_calc.py",
        constraints=("Keep pure python",),
    )

    item = coordinator.record_formulation(plan)
    assert item.level == EvidenceLevel.CLAIMED
    assert coordinator.formulated_plan == plan
    assert len(coordinator.ledger.get_items(level=EvidenceLevel.CLAIMED)) == 1


def test_coordinator_implement_change_approval_enforcement(tmp_path: Path):
    """Verify write tools require approval during IMPLEMENT_CHANGE when approval service is active."""
    coordinator, approval_service = _setup_coordinator(tmp_path, with_approval=True)

    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)

    agent = Agent.create(
        name="Coder",
        description="Coder agent",
        capabilities=frozenset({AgentCapability.CODE_MODIFICATION}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WRITE_FILES, AgentPermission.READ_FILES})
        ),
    )

    exec_id = uuid4()

    # Initial call to write_file raises ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError) as exc_info:
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=agent,
            tool_name="write_file",
            arguments={"path": "src/code.py", "content": "fixed"},
            execution_id=exec_id,
        )

    req_id = exc_info.value.request_id

    # Approve request
    approval_service.approve(
        request_id=req_id,
        approver="security-reviewer",
    )

    # Re-execute with approval_id
    result = coordinator.execute_tool(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        agent=agent,
        tool_name="write_file",
        arguments={"path": "src/code.py", "content": "fixed"},
        execution_id=exec_id,
        approval_id=req_id,
    )
    assert result.success is True
    assert coordinator.ledger.has_observed(SWETaskStage.IMPLEMENT_CHANGE) is True


def test_coordinator_verification_and_recovery(tmp_path: Path):
    """Verify verification records VERIFIED on pass, and failure delegates to RecoveryCoordinator."""
    coordinator, _ = _setup_coordinator(tmp_path)

    # Fast-forward through stages to RUN_TESTS
    for stage in [
        SWETaskStage.INSPECT_REPOSITORY,
        SWETaskStage.ANALYZE_FAILURE,
        SWETaskStage.FORMULATE_FIX,
        SWETaskStage.IMPLEMENT_CHANGE,
    ]:
        coordinator.advance_stage(stage)
        coordinator.complete_stage(stage)

    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)
    coordinator.advance_stage(SWETaskStage.VERIFY)

    exec_id = uuid4()

    # 1. Test failing verification
    fail_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["All 10 tests passed"],
        custom_output="5 passed, 2 failed in 0.5s",
    )
    assert fail_res.status == VerificationStatus.FAILED
    assert coordinator.ledger.has_verified(SWETaskStage.VERIFY) is False

    # Convert failed verification to Failure and test RecoveryCoordinator
    failure = VerificationFailureAdapter.to_failure(fail_res)
    assert failure.failure_type == FailureType.VERIFICATION_FAILURE

    failed_execution = AgentExecution.create(
        agent_id=uuid4(),
        agent_task_id=uuid4(),
    )
    failed_execution.status = AgentExecutionStatus.FAILED
    failed_execution.failure = failure
    failed_execution.error_message = failure.message

    recovery_res = coordinator.handle_stage_failure(failed_execution)
    assert recovery_res.decision.strategy is not None
    assert recovery_res.action is not None

    # 2. Test passing verification
    pass_res = coordinator.verify_fix(
        execution_id=exec_id,
        expected_requirements=["All 10 tests passed"],
        custom_output="All 10 tests passed in 0.8s",
    )
    assert pass_res.status == VerificationStatus.PASSED
    assert coordinator.ledger.has_verified(SWETaskStage.VERIFY) is True

    # 3. Advance to GENERATE_REPORT and generate report
    coordinator.complete_stage(SWETaskStage.VERIFY)
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)

    report = coordinator.generate_report()
    assert report.status == "verified_success"
    assert len(report.verified_evidence) == 1

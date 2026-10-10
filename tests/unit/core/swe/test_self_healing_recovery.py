"""Comprehensive test suite for Phase 6: Bounded Self-Healing Recovery Subsystem."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security.approval import ApprovalRequest, ApprovalStatus
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel
from orion.core.swe.cognitive.patch_approval import (
    PatchApprovalPackage,
)
from orion.core.swe.cognitive.patch_contracts import (
    PatchOperation,
    PatchOperationType,
    PatchProposal,
)
from orion.core.swe.cognitive.service import SWECognitiveService
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.applier import PatchApplicationAuthority
from orion.core.swe.execution.contracts import (
    PatchApplicationResult,
)
from orion.core.swe.execution.errors import PatchApplicationError
from orion.core.swe.execution.runner import ControlledExecutionAuthority, ControlledTestResult
from orion.core.swe.execution.states import (
    PatchExecutionState,
)
from orion.core.swe.execution.verifier import PatchVerificationAuthority
from orion.core.swe.recovery import (
    BudgetExhaustedError,
    FailureCategory,
    FailureClassification,
    FailureClassifier,
    InvalidRecoveryTransitionError,
    RecoveryAttempt,
    RecoveryAttemptLifecycle,
    RecoveryAttemptState,
    RecoveryBudget,
    RecoveryDepthExceededError,
    RecoveryPlan,
    RecoveryPlanner,
    RecoveryPolicy,
    RecoveryPolicyViolationError,
    RecoveryStrategy,
    RecoveryStrategyRegistry,
    SWERecoveryCoordinator,
    UnregisteredStrategyError,
)
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.errors import WorkspaceError
from orion.core.workspace.models import Workspace
from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.providers.base import BaseModelProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.runtime.runtime import ModelRuntime
from orion.models.selection.selector import ModelSelector


class ScriptedMockProvider(BaseModelProvider):
    """Predictable mock provider for Phase 6 self-healing tests."""

    def __init__(self, response_text: str, name: str = "mock") -> None:
        self._response_text = response_text
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return f"{self._name}-model"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"text_generation", "structured_output"})

    def health_check(self) -> bool:
        return True

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=self._response_text,
            model_name=self.model_name,
            provider_name=self.name,
            input_tokens=50,
            output_tokens=50,
        )


def _create_agent() -> Agent:
    return Agent.create(
        name="swe_engineer",
        description="Autonomous recovery engineer",
        capabilities=frozenset({AgentCapability.CODE_EXECUTION}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset(
                {
                    AgentPermission.READ_FILES,
                    AgentPermission.WRITE_FILES,
                    AgentPermission.CODE_EXECUTION,
                }
            )
        ),
    )


def _setup_test_env(
    tmp_path: Path,
) -> tuple[
    Workspace,
    ApprovalService,
    PatchApplicationAuthority,
    ControlledExecutionAuthority,
    PatchVerificationAuthority,
    EvidenceLedger,
    VerificationEngine,
]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    workspace = Workspace.create(repository_root=repo_dir)

    approval_repo = InMemoryApprovalRepository()
    approval_service = ApprovalService(repository=approval_repo)

    v_repo = InMemoryVerificationRepository()
    v_service = VerificationService(repository=v_repo)
    v_engine = VerificationEngine(verification_service=v_service)

    ledger = EvidenceLedger()
    applier = PatchApplicationAuthority(
        workspace=workspace,
        approval_service=approval_service,
        ledger=ledger,
    )
    runner = ControlledExecutionAuthority(workspace=workspace, ledger=ledger)
    verifier = PatchVerificationAuthority(verification_engine=v_engine, ledger=ledger)

    return workspace, approval_service, applier, runner, verifier, ledger, v_engine


def _create_cognitive_service(
    workspace: Workspace,
    response_text: str = "",
    provider_name: str = "mock",
    registry: ModelProviderRegistry | None = None,
) -> SWECognitiveService:
    if not response_text:
        response_text = json.dumps(
            {
                "change_intent": "Self-healing fix",
                "affected_files": ["src/main.py"],
                "modifications": ["Correct return value to 42"],
                "rationale": "Fix failed assertions",
                "expected_effect": "All tests pass",
                "validation_plan": ["pytest"],
                "confidence": 0.95,
            }
        )
    if registry is None:
        provider = ScriptedMockProvider(response_text=response_text, name=provider_name)
        registry = ModelProviderRegistry()
        registry.register(provider)
    selector = ModelSelector(registry=registry)
    runtime = ModelRuntime(selector=selector)
    config = ModelConfig(provider_name=provider_name)
    return SWECognitiveService(
        model_runtime=runtime,
        model_config=config,
        workspace=workspace,
    )


def _make_test_result(
    exit_code: int = 0,
    status: str = "passed",
    stdout: str = "",
    stderr: str = "",
    duration: float = 1.0,
    timed_out: bool = False,
) -> ControlledTestResult:
    now = datetime.now(UTC)
    return ControlledTestResult(
        execution_id=uuid4(),
        target="pytest",
        exit_code=exit_code,
        status=status,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        started_at=now,
        completed_at=now,
        timed_out=timed_out,
    )


# ==============================================================================
# 1. Failure Classification
# ==============================================================================


def test_01_failure_classification_categories() -> None:
    classifier = FailureClassifier()

    # TEST_FAILURE
    t_res = _make_test_result(
        exit_code=1,
        status="failed",
        duration=1.0,
        stdout="FAILED test_math.py::test_add - AssertionError",
    )
    c1 = classifier.classify(test_result=t_res)
    assert c1.category == FailureCategory.TEST_FAILURE
    assert c1.is_recoverable is True

    # TIMEOUT
    t_timeout = _make_test_result(
        exit_code=-1,
        status="failed",
        timed_out=True,
        duration=60.0,
        stderr="Test timed out after 60s",
    )
    c2 = classifier.classify(test_result=t_timeout)
    assert c2.category == FailureCategory.TIMEOUT

    # PATCH_APPLICATION_FAILURE
    app_fail = PatchApplicationResult(
        patch_id=uuid4(),
        task_id=uuid4(),
        execution_id=uuid4(),
        status=PatchExecutionState.FAILED,
        completed_operations=(),
        error="Target file not found on disk: src/missing.py",
    )
    c3 = classifier.classify(application_result=app_fail)
    assert c3.category == FailureCategory.PATCH_APPLICATION_FAILURE

    # STALE_STATE
    c4 = classifier.classify(failure="Concurrent workspace lock collision detected")
    assert c4.category == FailureCategory.STALE_STATE

    # VERIFICATION_FAILURE
    vr = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.FAILED,
        reason="Required assertion not met in output",
    )
    c5 = classifier.classify(verification_result=vr)
    assert c5.category == FailureCategory.VERIFICATION_FAILURE

    # APPROVAL_FAILURE
    c6 = classifier.classify(failure="Patch proposal was rejected by operator")
    assert c6.category == FailureCategory.APPROVAL_FAILURE
    assert c6.is_recoverable is False

    # WORKSPACE_INTEGRITY_FAILURE
    c7 = classifier.classify(failure="SHA-256 hash mismatch after patch write")
    assert c7.category == FailureCategory.WORKSPACE_INTEGRITY_FAILURE
    assert c7.is_recoverable is False

    # DEPENDENCY_FAILURE
    c8 = classifier.classify(failure="ModuleNotFoundError: No module named 'pytest'")
    assert c8.category == FailureCategory.DEPENDENCY_FAILURE


# ==============================================================================
# 2. Deterministic Classification Overrules Model Claim
# ==============================================================================


def test_02_deterministic_classification_overrules_model_claim() -> None:
    classifier = FailureClassifier()
    t_res = _make_test_result(
        exit_code=1,
        status="failed",
        duration=0.5,
        stdout="AssertionError: expected 42 but got 0",
    )

    # LLM claims this is merely an environment glitch or dependency issue
    claimed = "The model claims this is an ENVIRONMENT_FAILURE due to cloud network delay."

    classification = classifier.classify(
        test_result=t_res,
        claimed_diagnosis=claimed,
    )

    # Deterministic signal MUST govern
    assert classification.category == FailureCategory.TEST_FAILURE
    assert classification.claimed_category == claimed
    assert "AssertionError" in classification.root_causes[0]


# ==============================================================================
# 3. Valid Recovery Strategy Selection
# ==============================================================================


def test_03_valid_recovery_strategy_selection() -> None:
    policy = RecoveryPolicy()
    classifier = FailureClassifier()

    # Initial test failure -> RETRY_TEST
    c_test = classifier.classify(failure="AssertionError: 1 != 2")
    strat1, _ = policy.select_strategy(classification=c_test, history=())
    assert strat1 == RecoveryStrategy.RETRY_TEST

    # Stale workspace state -> REFRESH_WORKSPACE_STATE
    c_stale = classifier.classify(failure="Workspace lock collision")
    strat2, _ = policy.select_strategy(classification=c_stale, history=())
    assert strat2 == RecoveryStrategy.REFRESH_WORKSPACE_STATE

    # Patch application failure -> ROLLBACK
    c_app = classifier.classify(failure="Patch application failed midway")
    strat3, _ = policy.select_strategy(classification=c_app, history=())
    assert strat3 == RecoveryStrategy.ROLLBACK


# ==============================================================================
# 4. Invalid Strategy Rejection
# ==============================================================================


def test_04_invalid_strategy_rejection() -> None:
    policy = RecoveryPolicy()
    planner = RecoveryPlanner(policy=policy)
    budget = RecoveryBudget()

    # APPROVAL_FAILURE cannot use RETRY_TEST or REGENERATE_PATCH
    classification = FailureClassification(
        failure_id=uuid4(),
        category=FailureCategory.APPROVAL_FAILURE,
        message="Approval denied by policy",
        root_causes=("Explicit operator rejection",),
    )

    with pytest.raises(RecoveryPolicyViolationError):
        planner.plan_recovery(
            classification=classification,
            budget=budget,
            candidate_strategy=RecoveryStrategy.RETRY_TEST,
        )


# ==============================================================================
# 5. Budget Consumption
# ==============================================================================


def test_05_budget_consumption() -> None:
    budget = RecoveryBudget(
        max_total_attempts=5,
        max_patch_regenerations=2,
        max_test_retries=2,
    )

    s1 = budget.consume(RecoveryStrategy.RETRY_TEST, duration_seconds=1.5)
    assert s1.total_attempts == 1
    assert s1.test_retries == 1
    assert s1.remaining_attempts == 4
    assert s1.elapsed_seconds >= 1.5

    s2 = budget.consume(
        RecoveryStrategy.REGENERATE_PATCH,
        duration_seconds=2.0,
        affected_files=["src/foo.py", "src/bar.py"],
    )
    assert s2.total_attempts == 2
    assert s2.patch_regenerations == 1
    assert s2.affected_files_count == 2
    assert s2.recovery_depth == 2


# ==============================================================================
# 6. Budget Exhaustion
# ==============================================================================


def test_06_budget_exhaustion() -> None:
    budget = RecoveryBudget(max_total_attempts=2)
    budget.consume(RecoveryStrategy.RETRY_TEST)
    budget.consume(RecoveryStrategy.RETRY_TEST)

    assert budget.is_exhausted is True
    assert budget.can_attempt() is False

    with pytest.raises(BudgetExhaustedError):
        budget.consume(RecoveryStrategy.RETRY_TEST)


# ==============================================================================
# 7. Maximum Recovery Depth
# ==============================================================================


def test_07_maximum_recovery_depth() -> None:
    budget = RecoveryBudget(max_total_attempts=10, max_recovery_depth=2)

    budget.consume(RecoveryStrategy.REFRESH_WORKSPACE_STATE, increment_depth=True)
    assert budget.recovery_depth == 1

    budget.consume(RecoveryStrategy.REFRESH_WORKSPACE_STATE, increment_depth=True)
    assert budget.recovery_depth == 2

    with pytest.raises(RecoveryDepthExceededError):
        budget.consume(RecoveryStrategy.REFRESH_WORKSPACE_STATE, increment_depth=True)


# ==============================================================================
# 8. Retry Test Recovery
# ==============================================================================


def test_08_retry_test_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    # Write a passing test to repository root so retry succeeds
    (workspace.repository_root / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    # Execute recovery with initial test failure
    report = coord.recover(
        failure="Test failure: flaky network assertion",
        agent=agent,
        test_target="pytest",
    )

    assert report.total_attempts_executed >= 1
    assert report.final_state == RecoveryAttemptState.SUCCEEDED


# ==============================================================================
# 9. Patch Regeneration Recovery
# ==============================================================================


def test_09_patch_regeneration_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    cog = _create_cognitive_service(workspace)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        cognitive_service=cog,
        ledger=ledger,
    )

    agent = _create_agent()
    # Force candidate strategy REGENERATE_PATCH
    report = coord.recover(
        failure="Test assertion failed: value mismatch",
        agent=agent,
        candidate_strategy=RecoveryStrategy.REGENERATE_PATCH,
    )

    assert report.total_attempts_executed >= 1
    assert any(a.strategy == RecoveryStrategy.REGENERATE_PATCH for a in report.attempts)


# ==============================================================================
# 10. Model-Change Recovery
# ==============================================================================


def test_10_model_change_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    # Register both primary and alternate models in provider registry
    registry = ModelProviderRegistry()
    registry.register(ScriptedMockProvider(response_text="", name="mock"))
    registry.register(ScriptedMockProvider(response_text="", name="alternate_mock"))
    cog = _create_cognitive_service(workspace, provider_name="mock", registry=registry)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        cognitive_service=cog,
        ledger=ledger,
    )

    agent = _create_agent()
    report = coord.recover(
        failure="Repeated verification failure under mock model",
        agent=agent,
        candidate_strategy=RecoveryStrategy.CHANGE_MODEL,
        available_models=["alternate_mock"],
    )

    assert any(a.strategy == RecoveryStrategy.CHANGE_MODEL for a in report.attempts)


# ==============================================================================
# 11. Rollback Recovery
# ==============================================================================


def test_11_rollback_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    # Create target file with initial clean state
    test_file = workspace.repository_root / "calc.py"
    test_file.write_text("def answer(): return 42\n", encoding="utf-8")

    # Snapshot pre-state
    rec_point = applier.recovery_manager.create_recovery_point(
        workspace=workspace,
        affected_files=("calc.py",),
        execution_id=uuid4(),
    )

    # Mutate the file to simulate broken state
    test_file.write_text("SYNTAX ERROR CORRUPTED\n", encoding="utf-8")

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    report = coord.recover(
        failure="Patch application failure: syntax corrupted",
        agent=agent,
        current_recovery_point=rec_point,
        candidate_strategy=RecoveryStrategy.ROLLBACK,
    )

    # File must be restored cleanly
    assert test_file.read_text(encoding="utf-8") == "def answer(): return 42\n"
    assert any(a.strategy == RecoveryStrategy.ROLLBACK for a in report.attempts)


# ==============================================================================
# 12. Rollback Failure Handling
# ==============================================================================


def test_12_rollback_failure_handling(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    # Attempt rollback without any recovery point
    report = coord.recover(
        failure="Corrupted state requiring rollback",
        agent=agent,
        current_recovery_point=None,
        candidate_strategy=RecoveryStrategy.ROLLBACK,
    )

    # Must terminate cleanly with failed attempt
    assert report.final_state in (RecoveryAttemptState.FAILED, RecoveryAttemptState.TERMINATED)


# ==============================================================================
# 13. Stale Workspace Recovery
# ==============================================================================


def test_13_stale_workspace_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    # Lock workspace to simulate stale lock
    lock_exec_id = uuid4()
    applier.lock_manager.acquire(workspace.workspace_id, lock_exec_id)
    assert applier.lock_manager.is_locked(workspace.workspace_id) is True

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    report = coord.recover(
        failure="Workspace lock collision detected: stale state",
        agent=agent,
        candidate_strategy=RecoveryStrategy.REFRESH_WORKSPACE_STATE,
    )

    # Stale lock should have been released during recovery
    assert applier.lock_manager.is_locked(workspace.workspace_id) is False
    assert any(a.strategy == RecoveryStrategy.REFRESH_WORKSPACE_STATE for a in report.attempts)


# ==============================================================================
# 14. Verification Failure Recovery
# ==============================================================================


def test_14_verification_failure_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    cog = _create_cognitive_service(workspace)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        cognitive_service=cog,
        ledger=ledger,
    )

    vr = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.FAILED,
        reason="Required output tag <verified> missing",
    )

    agent = _create_agent()
    report = coord.recover(
        failure=vr,
        agent=agent,
    )

    assert report.total_attempts_executed >= 1
    assert report.initial_failure_category == FailureCategory.VERIFICATION_FAILURE


# ==============================================================================
# 15. Repeated Failure Termination
# ==============================================================================


def test_15_repeated_failure_termination() -> None:
    policy = RecoveryPolicy()
    classifier = FailureClassifier()
    classification = classifier.classify(failure="AssertionError: 1 != 2")

    plan1 = RecoveryPlan(
        plan_id=uuid4(),
        failure_id=uuid4(),
        failure_category=FailureCategory.TEST_FAILURE,
        selected_strategy=RecoveryStrategy.RETRY_TEST,
        rationale="Retry 1",
        expected_action="retest",
        attempt_number=1,
    )
    attempt1 = RecoveryAttempt(
        attempt_id=uuid4(),
        execution_id=uuid4(),
        failure_id=uuid4(),
        strategy=RecoveryStrategy.RETRY_TEST,
        start_time=datetime.now(UTC),
        state=RecoveryAttemptState.FAILED,
        plan=plan1,
    )

    plan2 = RecoveryPlan(
        plan_id=uuid4(),
        failure_id=uuid4(),
        failure_category=FailureCategory.TEST_FAILURE,
        selected_strategy=RecoveryStrategy.REGENERATE_PATCH,
        rationale="Regen 1",
        expected_action="regen",
        attempt_number=2,
    )
    attempt2 = RecoveryAttempt(
        attempt_id=uuid4(),
        execution_id=uuid4(),
        failure_id=uuid4(),
        strategy=RecoveryStrategy.REGENERATE_PATCH,
        start_time=datetime.now(UTC),
        state=RecoveryAttemptState.FAILED,
        plan=plan2,
    )

    strat, _ = policy.select_strategy(
        classification=classification,
        history=(attempt1, attempt2),
        can_change_model=False,
    )
    assert strat in (RecoveryStrategy.MODIFY_PATCH, RecoveryStrategy.TERMINATE)


# ==============================================================================
# 16. Approval-Required Recovery
# ==============================================================================


def test_16_approval_required_recovery() -> None:
    registry = RecoveryStrategyRegistry()
    regen_def = registry.get_definition(RecoveryStrategy.REGENERATE_PATCH)
    assert regen_def.approval_required is True

    modify_def = registry.get_definition(RecoveryStrategy.MODIFY_PATCH)
    assert modify_def.approval_required is True

    retry_def = registry.get_definition(RecoveryStrategy.RETRY_TEST)
    assert retry_def.approval_required is False


# ==============================================================================
# 17. Approval Rejection Termination
# ==============================================================================


def test_17_approval_rejection_termination(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    cog = _create_cognitive_service(workspace)

    # Monkey-patch approval service to reject request
    orig_create = approval_svc.create_request

    def rejecting_create(*args: Any, **kwargs: Any) -> ApprovalRequest:
        req = orig_create(*args, **kwargs)
        approval_svc.deny(
            request_id=req.id,
            approver="security_operator",
            reason="Auto-rejected by security test",
        )
        return req

    approval_svc.create_request = rejecting_create  # type: ignore[method-assign]

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        cognitive_service=cog,
        ledger=ledger,
    )

    agent = _create_agent()
    report = coord.recover(
        failure="Test failure",
        agent=agent,
        candidate_strategy=RecoveryStrategy.REGENERATE_PATCH,
    )

    assert report.final_state in (RecoveryAttemptState.FAILED, RecoveryAttemptState.TERMINATED)


# ==============================================================================
# 18. Arbitrary Strategy Rejection
# ==============================================================================


def test_18_arbitrary_strategy_rejection() -> None:
    registry = RecoveryStrategyRegistry()
    with pytest.raises(UnregisteredStrategyError):
        registry.get_definition("INVENTED_AUTONOMOUS_STRATEGY")  # type: ignore[arg-type]


# ==============================================================================
# 19. Model Attempting Unauthorized Recovery
# ==============================================================================


def test_19_model_attempting_unauthorized_recovery(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    # Non-recoverable failure cannot be forced by model claim
    report = coord.recover(
        failure="Approval denied by operator",
        agent=agent,
        candidate_strategy=RecoveryStrategy.RETRY_TEST,
    )

    # Deterministic policy must force TERMINATE regardless of model candidate
    assert report.final_state == RecoveryAttemptState.TERMINATED


# ==============================================================================
# 20. Filesystem Boundary Enforcement
# ==============================================================================


def test_20_filesystem_boundary_enforcement(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    # Verify that recovery subsystem cannot write outside workspace
    outside_file = tmp_path.parent / "escape.txt"
    assert not outside_file.exists()

    agent = _create_agent()
    exec_id = uuid4()
    req = approval_svc.create_request(
        agent_id=agent.id,
        tool_name="apply_patch",
        action="apply",
        risk_level=ToolRiskLevel.HIGH,
        execution_id=exec_id,
    )
    approval_svc.approve(request_id=req.id, approver="security_operator")

    # Applier must reject outside paths even when approved
    with pytest.raises((WorkspaceError, PatchApplicationError)):
        applier.apply_patch(
            approval_package=PatchApprovalPackage(
                request_id=req.id,
                patch_proposal=PatchProposal(
                    task_id=uuid4(),
                    operations=(
                        PatchOperation(
                            operation_type=PatchOperationType.CREATE_FILE,
                            path="../escape.txt",
                            new_content="escaped",
                        ),
                    ),
                    affected_files=("../escape.txt",),
                    rationale="escape",
                    validation_steps=(),
                    confidence=1.0,
                    unified_diff="",
                ),
                agent_id=agent.id,
                execution_id=exec_id,
                tool_name="apply_patch",
                action="apply",
                risk_level=ToolRiskLevel.HIGH,
                created_at=datetime.now(UTC),
                status=ApprovalStatus.APPROVED,
            ),
            execution_id=exec_id,
        )
    assert not outside_file.exists()


# ==============================================================================
# 21. Evidence Generation
# ==============================================================================


def test_21_evidence_generation(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    agent = _create_agent()
    coord.recover(failure="Test failure", agent=agent)

    items = ledger.get_items()
    categories = {i.category for i in items}
    assert EvidenceCategory.DIAGNOSTIC_RESULT in categories
    assert EvidenceCategory.PROPOSED_CHANGE in categories
    assert EvidenceCategory.RECOVERY_EVENT in categories


# ==============================================================================
# 22. Lifecycle Transition Validation
# ==============================================================================


def test_22_lifecycle_transition_validation() -> None:
    lifecycle = RecoveryAttemptLifecycle(initial_state=RecoveryAttemptState.PLANNED)

    # PLANNED -> AUTHORIZED is valid
    lifecycle.transition_to(RecoveryAttemptState.AUTHORIZED, reason="Approved")
    assert lifecycle.current_state == RecoveryAttemptState.AUTHORIZED

    # AUTHORIZED -> SUCCEEDED is invalid without execution
    with pytest.raises(InvalidRecoveryTransitionError):
        lifecycle.transition_to(RecoveryAttemptState.SUCCEEDED, reason="Bypass execution")


# ==============================================================================
# 23. Recovery Provenance Audit Trail
# ==============================================================================


def test_23_recovery_provenance_audit_trail(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)
    budget = RecoveryBudget(max_total_attempts=2)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
        budget=budget,
    )

    agent = _create_agent()
    report = coord.recover(failure="Test failure", agent=agent)

    audit_dict = report.to_dict()
    assert "mission_id" in audit_dict
    assert "task_id" in audit_dict
    assert "execution_id" in audit_dict
    assert "final_state" in audit_dict
    assert "attempts" in audit_dict
    assert "final_budget" in audit_dict
    assert isinstance(audit_dict["attempts"], list)


# ==============================================================================
# 24. Successful Self-Healing End-to-End
# ==============================================================================


def test_24_successful_self_healing_e2e(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, v_engine = _setup_test_env(tmp_path)

    # Initial target file
    main_file = workspace.repository_root / "math_util.py"
    main_file.write_text("def answer(): return 0\n", encoding="utf-8")

    # Scripted mock producing working patch
    patch_response = json.dumps(
        {
            "change_intent": "Fix math answer",
            "affected_files": ["math_util.py"],
            "modifications": ["return 42 instead of 0"],
            "rationale": "Align with verification requirements",
            "expected_effect": "Returns 42",
            "validation_plan": ["pytest"],
            "confidence": 0.99,
        }
    )
    cog = _create_cognitive_service(workspace, response_text=patch_response)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        cognitive_service=cog,
        ledger=ledger,
    )

    # Create deliberate initial failure
    initial_failure = _make_test_result(
        exit_code=1,
        status="failed",
        stdout="FAILED: expected 42 but got 0",
    )

    agent = _create_agent()
    report = coord.recover(
        failure=initial_failure,
        agent=agent,
        candidate_strategy=RecoveryStrategy.REGENERATE_PATCH,
        expected_requirements=["return 42"],
    )

    assert report.total_attempts_executed >= 1
    assert report.initial_failure_category == FailureCategory.TEST_FAILURE


# ==============================================================================
# 25. Unsuccessful Bounded Recovery End-to-End
# ==============================================================================


def test_25_unsuccessful_bounded_recovery_e2e(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
    )

    # Failure that is deterministically unrecoverable
    unrecoverable = "Integrity check failed: unauthorized filesystem modification detected"

    agent = _create_agent()
    report = coord.recover(
        failure=unrecoverable,
        agent=agent,
    )

    assert report.verified_success is False
    assert report.final_state == RecoveryAttemptState.TERMINATED
    assert report.initial_failure_category == FailureCategory.WORKSPACE_INTEGRITY_FAILURE


# ==============================================================================
# 26. Recovery Budget Exhaustion End-to-End
# ==============================================================================


def test_26_recovery_budget_exhaustion_e2e(tmp_path: Path) -> None:
    workspace, approval_svc, applier, runner, verifier, ledger, _ = _setup_test_env(tmp_path)

    # Budget strictly capped at 2 attempts
    budget = RecoveryBudget(
        max_total_attempts=2,
        max_test_retries=1,
    )

    coord = SWERecoveryCoordinator(
        workspace=workspace,
        patch_applier=applier,
        execution_runner=runner,
        verification_authority=verifier,
        recovery_manager=applier.recovery_manager,
        approval_service=approval_svc,
        ledger=ledger,
        budget=budget,
    )

    agent = _create_agent()
    report = coord.recover(
        failure="Persistent test failure",
        agent=agent,
    )

    # Loop must terminate boundedly when budget is exhausted
    assert report.total_attempts_executed <= 2
    assert report.final_state in (RecoveryAttemptState.FAILED, RecoveryAttemptState.TERMINATED)
    assert report.verified_success is False
    assert budget.is_exhausted or budget.remaining_attempts == 0


def test_controlled_test_result_output_summary() -> None:
    """Verify ControlledTestResult.output_summary combines stdout and stderr."""
    now = datetime.now(UTC)
    res = ControlledTestResult(
        execution_id=uuid4(),
        target="tests/test_foo.py",
        exit_code=1,
        status="failed",
        stdout="collected 5 items",
        stderr="FAILED test_foo.py",
        duration_seconds=1.5,
        started_at=now,
        completed_at=now,
    )
    summary = res.output_summary
    assert "Tests failed with exit code 1" in summary

    passed_res = ControlledTestResult(
        execution_id=uuid4(),
        target="tests/test_foo.py",
        exit_code=0,
        status="passed",
        stdout="passed",
        stderr="",
        duration_seconds=0.42,
        started_at=now,
        completed_at=now,
    )
    assert "Tests passed (0.42s)" in passed_res.output_summary

"""Comprehensive unit and security tests for Phase 5: Controlled Patch Execution."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from orion.config.model_config import ModelConfig
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
from orion.core.swe.coordinator import SWEWorkflowCoordinator
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger, EvidenceLevel
from orion.core.swe.execution.applier import PatchApplicationAuthority
from orion.core.swe.execution.errors import (
    ApprovalIntegrityError,
    ControlledExecutionError,
    InvalidStateTransitionError,
    PatchApplicationError,
    RevokedApprovalError,
    StaleApprovalError,
    UnapprovedPatchError,
    WorkspaceLockedError,
)
from orion.core.swe.execution.lock import WorkspaceLockManager
from orion.core.swe.execution.runner import ControlledExecutionAuthority
from orion.core.swe.execution.states import (
    PatchExecutionLifecycle,
    PatchExecutionState,
)
from orion.core.swe.execution.verifier import PatchVerificationAuthority
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace
from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.providers.base import BaseModelProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.runtime.runtime import ModelRuntime
from orion.models.selection.selector import ModelSelector


class ScriptedPatchProvider(BaseModelProvider):
    """Predictable mock provider for Phase 5 end-to-end integration tests."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-scripted"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"text_generation", "structured_output"})

    def health_check(self) -> bool:
        return True

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=self._response_text,
            model_name="mock-scripted",
            provider_name="mock",
            input_tokens=50,
            output_tokens=50,
        )


def _create_test_agent() -> Agent:
    return Agent(
        id=uuid4(),
        name="swe_engineer",
        description="Autonomous software engineering agent",
        capabilities=frozenset(),
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


def _setup_authorities(
    tmp_path: Path,
) -> tuple[
    Workspace,
    ApprovalService,
    PatchApplicationAuthority,
    ControlledExecutionAuthority,
    PatchVerificationAuthority,
    EvidenceLedger,
]:
    workspace = Workspace.create(repository_root=tmp_path)
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

    return workspace, approval_service, applier, runner, verifier, ledger


def _create_approved_patch_package(
    workspace: Workspace,
    approval_service: ApprovalService,
    operations: tuple[PatchOperation, ...],
    agent: Agent | None = None,
    task_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> PatchApprovalPackage:
    effective_agent = agent or _create_test_agent()
    effective_task_id = task_id or uuid4()

    proposal = PatchProposal(
        task_id=effective_task_id,
        operations=operations,
        affected_files=tuple(op.path for op in operations),
        rationale="Fix verified bug",
        validation_steps=("pytest",),
        confidence=0.95,
        unified_diff="--- a\n+++ b\n",
        syntax_results=(),
        total_lines_added=5,
        total_lines_removed=0,
    )

    req = approval_service.create_request(
        agent_id=effective_agent.id,
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
        expires_at=expires_at,
    )
    approval_service.approve(request_id=req.id, approver="lead_engineer")

    return PatchApprovalPackage(
        request_id=req.id,
        patch_proposal=proposal,
        agent_id=effective_agent.id,
        execution_id=uuid4(),
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
        created_at=req.created_at,
        status=ApprovalStatus.APPROVED,
    )


# ---------------------------------------------------------------------------
# Security & Pre-Apply Validation Tests
# ---------------------------------------------------------------------------


def test_valid_approved_patch_application(tmp_path: Path) -> None:
    """Test 1: Valid approved patch applies cleanly, updates files, and records evidence."""
    ws, app_svc, applier, _, _, ledger = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="src/calc.py",
                new_content="def add(a, b):\n    return a + b\n",
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.is_applied is True
    assert result.status == PatchExecutionState.APPLIED
    file_content = (tmp_path / "src" / "calc.py").read_text(encoding="utf-8")
    assert file_content == "def add(a, b):\n    return a + b\n"
    assert len(ledger.get_items(category=EvidenceCategory.FILE_CHANGE)) == 1


def test_unapproved_patch_rejected(tmp_path: Path) -> None:
    """Test 2: Applying a patch with PENDING status raises UnapprovedPatchError."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    agent = _create_test_agent()
    proposal = PatchProposal(
        task_id=uuid4(),
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="mod.py",
                new_content="x = 1\n",
            ),
        ),
        affected_files=("mod.py",),
        rationale="Fix",
        validation_steps=("pytest",),
        confidence=0.9,
    )
    req = app_svc.create_request(
        agent_id=agent.id,
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
    )
    # Not approved!
    pkg = PatchApprovalPackage(
        request_id=req.id,
        patch_proposal=proposal,
        agent_id=agent.id,
        execution_id=uuid4(),
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
        created_at=req.created_at,
        status=ApprovalStatus.PENDING,
    )

    with pytest.raises(UnapprovedPatchError) as exc_info:
        applier.apply_patch(pkg)
    assert "not in APPROVED state" in str(exc_info.value)


def test_revoked_approval_rejected(tmp_path: Path) -> None:
    """Test 3: Applying a patch with DENIED status raises RevokedApprovalError."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    agent = _create_test_agent()
    proposal = PatchProposal(
        task_id=uuid4(),
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="mod.py",
                new_content="x = 1\n",
            ),
        ),
        affected_files=("mod.py",),
        rationale="Fix",
        validation_steps=(),
        confidence=0.9,
    )
    req = app_svc.create_request(
        agent_id=agent.id,
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
    )
    app_svc.deny(request_id=req.id, approver="security_officer", reason="Unsafe")

    pkg = PatchApprovalPackage(
        request_id=req.id,
        patch_proposal=proposal,
        agent_id=agent.id,
        execution_id=uuid4(),
        tool_name="apply_change",
        action="apply_patch",
        risk_level=ToolRiskLevel.HIGH,
        created_at=req.created_at,
        status=ApprovalStatus.DENIED,
    )

    with pytest.raises(RevokedApprovalError) as exc_info:
        applier.apply_patch(pkg)
    assert "DENIED" in str(exc_info.value)


def test_stale_approval_rejected(tmp_path: Path) -> None:
    """Test 4: Applying a patch with an expired approval raises StaleApprovalError."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="mod.py",
                new_content="x = 1\n",
            ),
        ),
    )
    # Simulate expiration occurring between approval and application
    stored = app_svc._repository.get(pkg.request_id)
    assert stored is not None
    expired_time = datetime.now(UTC) - timedelta(minutes=10)
    app_svc._repository.save(
        ApprovalRequest(
            id=stored.id,
            agent_id=stored.agent_id,
            execution_id=stored.execution_id,
            tool_name=stored.tool_name,
            action=stored.action,
            risk_level=stored.risk_level,
            created_at=stored.created_at,
            expires_at=expired_time,
            status=ApprovalStatus.APPROVED,
        )
    )

    with pytest.raises(StaleApprovalError) as exc_info:
        applier.apply_patch(pkg)
    assert "expired" in str(exc_info.value).lower()


def test_modified_after_approval_patch_rejected(tmp_path: Path) -> None:
    """Test 5: Tampered approval package (e.g. mismatched agent) raises ApprovalIntegrityError."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="mod.py",
                new_content="x = 1\n",
            ),
        ),
    )
    # Tamper with agent_id
    tampered_pkg = PatchApprovalPackage(
        request_id=pkg.request_id,
        patch_proposal=pkg.patch_proposal,
        agent_id=uuid4(),  # Different agent!
        execution_id=pkg.execution_id,
        tool_name=pkg.tool_name,
        action=pkg.action,
        risk_level=pkg.risk_level,
        created_at=pkg.created_at,
        status=pkg.status,
    )

    with pytest.raises(ApprovalIntegrityError) as exc_info:
        applier.apply_patch(tampered_pkg)
    assert "does not match" in str(exc_info.value)


def test_wrong_workspace_rejected(tmp_path: Path) -> None:
    """Test 6: Operation targeting a file escaping the workspace boundary is rejected."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="../outside.txt",
                new_content="escaped",
            ),
        ),
    )

    with pytest.raises(PatchApplicationError) as exc_info:
        applier.apply_patch(pkg)
    err_text = str(exc_info.value).lower()
    assert "escapes workspace boundary" in err_text or "traversal" in err_text


def test_path_traversal_rejected(tmp_path: Path) -> None:
    """Test 7: Path with traversal sequence '..' is rejected at application boundary."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="sub/../../escape.py",
                new_content="malicious",
            ),
        ),
    )

    with pytest.raises(PatchApplicationError) as exc_info:
        applier.apply_patch(pkg)
    assert "traversal" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "protected_file",
    [
        ".env",
        ".env.production",
        "credentials.json",
        ".git/config",
        "id_rsa",
        "cert.pem",
        "secret.key",
    ],
)
def test_protected_file_rejected(tmp_path: Path, protected_file: str) -> None:
    """Test 8: Protected credential and configuration files are rejected at boundary."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path=protected_file,
                new_content="SECRET=123",
            ),
        ),
    )

    with pytest.raises(PatchApplicationError) as exc_info:
        applier.apply_patch(pkg)
    assert "protected" in str(exc_info.value).lower()


def test_concurrent_application_rejected_and_serialized(tmp_path: Path) -> None:
    """Test 9: Attempting concurrent application while lock is held raises WorkspaceLockedError."""
    workspace = Workspace.create(repository_root=tmp_path)
    lock_mgr = WorkspaceLockManager()
    execution_1 = uuid4()
    execution_2 = uuid4()

    lock_mgr.acquire(workspace.workspace_id, execution_1)
    assert lock_mgr.is_locked(workspace.workspace_id) is True

    # Same execution reentrant
    lock_mgr.acquire(workspace.workspace_id, execution_1)

    # Different execution must be rejected
    with pytest.raises(WorkspaceLockedError) as exc_info:
        lock_mgr.acquire(workspace.workspace_id, execution_2)
    assert "is locked by execution" in str(exc_info.value)

    # Safe release
    lock_mgr.release(workspace.workspace_id, execution_1)
    lock_mgr.release(workspace.workspace_id, execution_1)
    assert lock_mgr.is_locked(workspace.workspace_id) is False


def test_successful_create_file(tmp_path: Path) -> None:
    """Test 10: CREATE_FILE creates new file, ensures parent dirs, and records hash."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="pkg/sub/module.py",
                new_content="VALUE = 42\n",
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.status == PatchExecutionState.APPLIED
    target = tmp_path / "pkg" / "sub" / "module.py"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "VALUE = 42\n"


def test_successful_modify_file(tmp_path: Path) -> None:
    """Test 11: MODIFY_FILE updates existing file and computes deltas."""
    file_path = tmp_path / "app.py"
    file_path.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    content_bytes = file_path.read_text(encoding="utf-8").encode("utf-8")
    expected_hash = hashlib.sha256(content_bytes).hexdigest()

    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.MODIFY_FILE,
                path="app.py",
                new_content="def hello():\n    return 'hello world'\n",
                expected_hash=expected_hash,
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.status == PatchExecutionState.APPLIED
    assert file_path.read_text(encoding="utf-8") == "def hello():\n    return 'hello world'\n"


def test_successful_delete_file(tmp_path: Path) -> None:
    """Test 12: DELETE_FILE unlinks target file cleanly."""
    file_path = tmp_path / "obsolete.py"
    file_path.write_text("old = True\n", encoding="utf-8")
    content_bytes = file_path.read_text(encoding="utf-8").encode("utf-8")
    expected_hash = hashlib.sha256(content_bytes).hexdigest()

    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.DELETE_FILE,
                path="obsolete.py",
                expected_hash=expected_hash,
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.status == PatchExecutionState.APPLIED
    assert not file_path.exists()


def test_application_failure_handling(tmp_path: Path) -> None:
    """Test 13: Pre-check failure on missing MODIFY_FILE returns FAILED status without crash."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.MODIFY_FILE,
                path="non_existent.py",
                new_content="content",
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.status == PatchExecutionState.FAILED
    assert "not found on disk" in str(result.error)


def test_partial_application_and_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test 14 & 15: If an operation fails mid-patch, prior mutations are cleanly rolled back."""
    # Setup initial file
    initial_file = tmp_path / "base.py"
    initial_file.write_text("original content\n", encoding="utf-8")
    base_hash = hashlib.sha256(b"original content\n").hexdigest()

    ws, app_svc, applier, _, _, ledger = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.MODIFY_FILE,
                path="base.py",
                new_content="mutated content\n",
                expected_hash=base_hash,
            ),
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="created.py",
                new_content="newly created\n",
            ),
        ),
    )

    real_write_text = Path.write_text

    def mock_write_text(self_path: Path, data: str, *args: Any, **kwargs: Any) -> Any:
        if self_path.name == "created.py":
            raise OSError("Simulated disk error during creation of created.py")
        return real_write_text(self_path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    result = applier.apply_patch(pkg)
    # State must be RECOVERED
    assert result.status == PatchExecutionState.RECOVERED
    assert result.failed_operation is not None
    assert result.failed_operation.path == "created.py"
    # Verify rollback: base.py must have its original content restored!
    assert initial_file.read_text(encoding="utf-8") == "original content\n"
    # Verify recovery event logged in ledger
    rec_items = ledger.get_items(category=EvidenceCategory.RECOVERY_EVENT)
    assert len(rec_items) >= 1


def test_unexpected_filesystem_modification_hash_mismatch(tmp_path: Path) -> None:
    """Test 16 & 17: Concurrent file modification creates stale hash mismatch that is rejected."""
    f = tmp_path / "target.py"
    f.write_text("version 1\n", encoding="utf-8")

    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.MODIFY_FILE,
                path="target.py",
                new_content="version 3\n",
                expected_hash="stale_or_wrong_hash_12345",
            ),
        ),
    )

    result = applier.apply_patch(pkg)
    assert result.status == PatchExecutionState.FAILED
    assert "Stale hash" in str(result.error)
    # File content remains untouched
    assert f.read_text(encoding="utf-8") == "version 1\n"


def test_test_timeout_handling(tmp_path: Path) -> None:
    """Test 18: Controlled test runner detects timeout and reports timeout status."""
    ws = Workspace.create(repository_root=tmp_path)
    # Create test that sleeps longer than timeout
    test_file = tmp_path / "test_slow.py"
    test_file.write_text("import time\ndef test_sleep():\n    time.sleep(2)\n", encoding="utf-8")

    runner = ControlledExecutionAuthority(workspace=ws)
    result = runner.run_tests(target="test_slow.py", timeout_seconds=1)
    assert result.timed_out is True
    assert result.status == "timeout"
    assert result.exit_code == -1
    assert result.passed is False


def test_non_zero_test_exit_code(tmp_path: Path) -> None:
    """Test 19: Failing tests return non-zero exit code and status='failed'."""
    ws = Workspace.create(repository_root=tmp_path)
    test_file = tmp_path / "test_fail.py"
    test_file.write_text("def test_broken():\n    assert 1 == 2\n", encoding="utf-8")

    runner = ControlledExecutionAuthority(workspace=ws)
    result = runner.run_tests(target="test_fail.py", timeout_seconds=10)
    assert result.passed is False
    assert result.exit_code != 0
    assert result.status == "failed"


def test_successful_verification(tmp_path: Path) -> None:
    """Test 20: Passing test output produces VERIFIED status and records VERIFIED evidence."""
    ws, app_svc, applier, runner, verifier, ledger = _setup_authorities(tmp_path)

    # 1. Apply clean patch
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="math_utils.py",
                new_content="def multiply(a, b):\n    return a * b\n",
            ),
        ),
    )
    app_result = applier.apply_patch(pkg)
    assert app_result.is_applied is True

    # 2. Add passing test
    (tmp_path / "test_math.py").write_text(
        "from math_utils import multiply\ndef test_mul():\n    assert multiply(3, 4) == 12\n",
        encoding="utf-8",
    )

    # 3. Run controlled tests
    test_result = runner.run_tests(target="test_math.py", timeout_seconds=10)
    assert test_result.passed is True

    # 4. Verify outcome
    outcome = verifier.verify_execution(
        application_result=app_result,
        test_result=test_result,
        expected_requirements=["passed"],
    )

    assert outcome.is_verified is True
    assert outcome.lifecycle_state == PatchExecutionState.VERIFIED
    # Evidence must contain VERIFIED record
    verified_items = ledger.get_items(level=EvidenceLevel.VERIFIED)
    assert len(verified_items) >= 1
    assert "Verification PASSED" in verified_items[0].content


def test_failed_verification(tmp_path: Path) -> None:
    """Test 21: Failing tests produce FAILED lifecycle state and do not create VERIFIED evidence."""
    ws, app_svc, applier, runner, verifier, ledger = _setup_authorities(tmp_path)

    # 1. Apply patch
    pkg = _create_approved_patch_package(
        workspace=ws,
        approval_service=app_svc,
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="logic.py",
                new_content="def check():\n    return False\n",
            ),
        ),
    )
    app_result = applier.apply_patch(pkg)

    # 2. Add failing test
    (tmp_path / "test_logic.py").write_text(
        "from logic import check\ndef test_check():\n    assert check() is True\n",
        encoding="utf-8",
    )

    # 3. Run tests
    test_result = runner.run_tests(target="test_logic.py", timeout_seconds=10)
    assert test_result.passed is False

    # 4. Verify
    outcome = verifier.verify_execution(
        application_result=app_result,
        test_result=test_result,
        expected_requirements=["passed"],
    )

    assert outcome.is_verified is False
    assert outcome.lifecycle_state == PatchExecutionState.FAILED
    assert len(ledger.get_items(level=EvidenceLevel.VERIFIED)) == 0


def test_model_attempting_unauthorized_execution(tmp_path: Path) -> None:
    """Test 22: Raw model proposal cannot bypass approval or directly invoke application."""
    ws, app_svc, applier, _, _, _ = _setup_authorities(tmp_path)

    raw_proposal = PatchProposal(
        task_id=uuid4(),
        operations=(
            PatchOperation(
                operation_type=PatchOperationType.CREATE_FILE,
                path="unauthorized.py",
                new_content="print('hacked')",
            ),
        ),
        affected_files=("unauthorized.py",),
        rationale="bypass",
        validation_steps=(),
        confidence=1.0,
    )

    # Pass raw proposal without approval
    with pytest.raises(TypeError):
        applier.apply_patch(raw_proposal)  # type: ignore[arg-type]


def test_arbitrary_shell_command_rejection(tmp_path: Path) -> None:
    """Test 23: Test execution rejects arbitrary shell commands and traversal sequences."""
    ws = Workspace.create(repository_root=tmp_path)
    runner = ControlledExecutionAuthority(workspace=ws)

    # Escape traversal sequence in target
    with pytest.raises(ControlledExecutionError) as exc_info:
        runner.run_tests(target="../test_outside.py")
    assert "forbidden" in str(exc_info.value).lower() or "escapes" in str(exc_info.value).lower()


def test_workspace_escape_rejection(tmp_path: Path) -> None:
    """Test 24: Absolute path outside workspace is rejected by runner."""
    ws = Workspace.create(repository_root=tmp_path)
    runner = ControlledExecutionAuthority(workspace=ws)

    outside = "C:/Windows/System32/drivers/etc/hosts" if Path("C:/").exists() else "/etc/passwd"
    with pytest.raises(ControlledExecutionError) as exc_info:
        runner.run_tests(target=outside)
    assert "escapes workspace boundary" in str(exc_info.value).lower()


def test_phase5_state_machine_transitions() -> None:
    """Test 25: Lifecycle state machine enforces deterministic valid transitions."""
    lifecycle = PatchExecutionLifecycle(initial_state=PatchExecutionState.PROPOSED)
    assert lifecycle.current_state.value == PatchExecutionState.PROPOSED.value

    lifecycle.transition_to(PatchExecutionState.VALIDATED)
    lifecycle.transition_to(PatchExecutionState.PENDING_APPROVAL)
    lifecycle.transition_to(PatchExecutionState.AUTHORIZED)
    lifecycle.transition_to(PatchExecutionState.APPLYING)
    lifecycle.transition_to(PatchExecutionState.APPLIED)
    lifecycle.transition_to(PatchExecutionState.EXECUTING)
    lifecycle.transition_to(PatchExecutionState.VERIFIED)

    assert lifecycle.current_state.value == PatchExecutionState.VERIFIED.value
    assert len(lifecycle.history) == 7

    # Illegal transition from terminal VERIFIED state
    with pytest.raises(InvalidStateTransitionError):
        lifecycle.transition_to(PatchExecutionState.APPLYING)


# ---------------------------------------------------------------------------
# Step 14: End-to-End SWE Workflow Integration Test
# ---------------------------------------------------------------------------


def test_end_to_end_phase5_swe_workflow(tmp_path: Path) -> None:
    """Test 26: Full end-to-end integration:

    USER TASK -> SWE COGNITION -> PATCH PROPOSAL -> PATCH VALIDATION ->
    APPROVAL -> PATCH APPLICATION -> TEST EXECUTION -> VERIFICATION -> FINAL RESULT.
    """
    workspace = Workspace.create(repository_root=tmp_path)

    # Setup baseline repository file
    code_file = tmp_path / "service.py"
    code_file.write_text("def compute(x):\n    return x - 1\n", encoding="utf-8")
    code_bytes = code_file.read_text(encoding="utf-8").encode("utf-8")
    expected_hash = hashlib.sha256(code_bytes).hexdigest()

    # Setup failing test in repository
    test_file = tmp_path / "test_service.py"
    test_file.write_text(
        "from service import compute\ndef test_compute():\n    assert compute(5) == 10\n",
        encoding="utf-8",
    )

    # Model payload synthesizing the fix
    canned_patch = {
        "affected_files": ["service.py"],
        "operations": [
            {
                "operation_type": "MODIFY_FILE",
                "path": "service.py",
                "new_content": "def compute(x):\n    return x * 2\n",
                "expected_hash": expected_hash,
            }
        ],
        "rationale": "Fix arithmetic logic to multiply x by 2",
        "validation_steps": ["pytest test_service.py"],
        "confidence": 0.98,
    }

    # Setup cognitive service
    provider = ScriptedPatchProvider(json.dumps(canned_patch))
    registry = ModelProviderRegistry()
    registry.register(provider)
    selector = ModelSelector(registry)
    runtime = ModelRuntime(selector)
    model_config = ModelConfig(model_name="mock-model", provider_name="mock")
    cognitive_svc = SWECognitiveService(
        model_runtime=runtime,
        model_config=model_config,
        workspace=workspace,
    )

    # Setup tools and approval
    tool_reg = InMemoryToolRegistry()
    approval_repo = InMemoryApprovalRepository()
    approval_service = ApprovalService(repository=approval_repo)
    executor = ToolExecutor(registry=tool_reg, approval_service=approval_service)

    v_repo = InMemoryVerificationRepository()
    v_service = VerificationService(repository=v_repo)
    v_engine = VerificationEngine(verification_service=v_service)

    coordinator = SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=executor,
        verification_engine=v_engine,
        cognitive_service=cognitive_svc,
    )
    agent = _create_test_agent()

    # 1. INSPECT_REPOSITORY
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)

    # 2. ANALYZE_FAILURE
    coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
    analysis = coordinator.analyze_failure(
        agent=agent,
        test_output="AssertionError: assert compute(5) == 10 failed, got 4",
    )
    coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)

    # 3. FORMULATE_FIX & SYNTHESIZE PATCH
    coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
    fix_plan = coordinator.formulate_fix(agent=agent, diagnosis=analysis)
    patch = coordinator.synthesize_patch(agent=agent, fix_proposal=fix_plan)
    assert len(patch.operations) == 1
    assert patch.operations[0].path == "service.py"

    # Request Approval
    approval_pkg = coordinator.request_patch_approval(patch_proposal=patch, agent=agent)
    assert approval_pkg.status == ApprovalStatus.PENDING

    # Grant Approval (Human / Governance authorization)
    approval_service.approve(request_id=approval_pkg.request_id, approver="security_lead")
    refreshed_pkg = coordinator.refresh_patch_approval()
    assert refreshed_pkg is not None and refreshed_pkg.is_approved is True
    coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)

    # 4. IMPLEMENT_CHANGE (Apply Patch)
    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)
    apply_result = coordinator.apply_approved_patch(refreshed_pkg)
    assert apply_result.is_applied is True
    assert code_file.read_text(encoding="utf-8") == "def compute(x):\n    return x * 2\n"
    coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

    # 5. RUN_TESTS (Controlled Execution)
    coordinator.advance_stage(SWETaskStage.RUN_TESTS)
    test_result = coordinator.run_controlled_tests(target="test_service.py", timeout_seconds=10)
    assert test_result.passed is True
    assert test_result.exit_code == 0
    coordinator.complete_stage(SWETaskStage.RUN_TESTS)

    # 6. VERIFY (VerificationEngine)
    coordinator.advance_stage(SWETaskStage.VERIFY)
    outcome = coordinator.verify_patch_execution(expected_requirements=["passed"])
    assert outcome.is_verified is True
    assert outcome.lifecycle_state == PatchExecutionState.VERIFIED
    coordinator.complete_stage(SWETaskStage.VERIFY)

    # 7. GENERATE_REPORT
    coordinator.advance_stage(SWETaskStage.GENERATE_REPORT)
    report = coordinator.generate_report(summary="Fixed arithmetic bug successfully")
    assert report.status == "verified_success"
    assert "service.py" in report.files_modified

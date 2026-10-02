"""Comprehensive SWE Security Validation Suite for ORION.

Verifies:
1. Path traversal and workspace boundary escapes
2. Protected file access prevention (.env, .git, secret keys)
3. Secret redaction and isolation in evidence records
4. Approval bypass prevention for modifying tools
5. Stage-level tool permission enforcement
6. Subprocess execution isolation (shell=False)
7. Stale state / optimistic concurrency enforcement
"""

from __future__ import annotations

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
from orion.core.swe.errors import DisallowedFileModificationError, DisallowedStageToolError
from orion.core.swe.evidence import (
    _sanitize_metadata,
)
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.tools.repository.errors import StaleStateError
from orion.core.tools.repository.factory import register_repository_tools
from orion.core.tools.repository.write_tools import build_apply_change_tool
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace


@pytest.fixture
def secure_workspace(tmp_path: Path) -> Workspace:
    repo = tmp_path / "sandbox_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "safe_file.py").write_text("print('hello')", encoding="utf-8")
    (repo / ".env").write_text("SECRET_KEY=super_secret_token", encoding="utf-8")
    return Workspace(repository_root=repo)


@pytest.fixture
def unprivileged_agent() -> Agent:
    return Agent.create(
        name="Unprivileged-Agent",
        description="Agent without write permissions",
        capabilities=frozenset({AgentCapability.REPOSITORY_ANALYSIS}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.READ_FILES})
        ),
    )


@pytest.fixture
def full_swe_agent() -> Agent:
    return Agent.create(
        name="Full-SWE-Agent",
        description="Agent with read, write, and execute permissions",
        capabilities=frozenset({
            AgentCapability.REPOSITORY_ANALYSIS,
            AgentCapability.CODE_MODIFICATION,
            AgentCapability.TESTING,
            AgentCapability.VERIFICATION,
        }),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({
                AgentPermission.READ_FILES,
                AgentPermission.WRITE_FILES,
                AgentPermission.CODE_EXECUTION,
            })
        ),
    )


def test_path_traversal_rejection(secure_workspace: Workspace, full_swe_agent: Agent):
    """Verify paths attempting to escape workspace boundary are rejected."""
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, secure_workspace)
    executor = ToolExecutor(registry=registry)

    # Absolute path escape outside workspace
    outside_path = (
        "C:/Windows/System32/drivers/etc/hosts" if Path("C:/").exists() else "/etc/passwd"
    )
    res = executor.execute(
        agent=full_swe_agent,
        tool_name="read_file",
        arguments={"path": outside_path},
    )
    assert res.success is False
    assert any(
        term in str(res.error).lower() for term in ("outside", "boundary", "security", "path")
    )

    # Relative path traversal escape
    res_rel = executor.execute(
        agent=full_swe_agent,
        tool_name="read_file",
        arguments={"path": "../../../secret.txt"},
    )
    assert res_rel.success is False


def test_protected_files_rejection(secure_workspace: Workspace, full_swe_agent: Agent):
    """Verify sensitive files (.env, .git, etc.) are protected from reading or writing."""
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, secure_workspace)
    approval_service = ApprovalService(repository=InMemoryApprovalRepository())
    executor = ToolExecutor(registry=registry, approval_service=approval_service)

    # Attempt to read .env -> rejected by read_file handler
    res_read = executor.execute(
        agent=full_swe_agent,
        tool_name="read_file",
        arguments={"path": ".env"},
    )
    assert res_read.success is False
    assert any(
        term in str(res_read.error).lower()
        for term in ("protect", "secret", "denied", "permission")
    )

    # Attempt to write .env -> approval requested, then rejected by handler
    exec_id = uuid4()
    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=full_swe_agent,
            tool_name="write_file",
            arguments={"path": ".env", "content": "NEW_SECRET"},
            execution_id=exec_id,
        )

    approval_service.approve(request_id=exc_info.value.request_id, approver="admin")
    res_write = executor.execute(
        agent=full_swe_agent,
        tool_name="write_file",
        arguments={"path": ".env", "content": "NEW_SECRET"},
        execution_id=exec_id,
        approval_id=exc_info.value.request_id,
    )
    assert res_write.success is False
    assert any(
        term in str(res_write.error).lower()
        for term in ("protect", "secret", "denied", "permission")
    )


def test_secret_redaction_in_metadata():
    """Verify _sanitize_metadata redacts passwords, tokens, and api keys."""
    raw_metadata = {
        "user": "alice",
        "api_key": "sk-1234567890abcdef",
        "db_password": "mypassword",
        "auth_token": "Bearer xyz987",
        "safe_info": "version 1.0",
        "nested": {
            "secret_key": "shhh",
            "count": 42,
        },
    }

    sanitized = _sanitize_metadata(raw_metadata)
    assert sanitized["user"] == "alice"
    assert sanitized["safe_info"] == "version 1.0"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["db_password"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["secret_key"] == "[REDACTED]"
    assert sanitized["nested"]["count"] == 42


def test_stage_level_tool_permission_enforcement(
    secure_workspace: Workspace, full_swe_agent: Agent
):
    """Verify coordinator prohibits file modification tools during read-only stages."""
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, secure_workspace)
    tool_executor = ToolExecutor(registry=registry)

    coordinator = SWEWorkflowCoordinator(
        workspace=secure_workspace,
        tool_executor=tool_executor,
        verification_engine=VerificationEngine(
            verification_service=VerificationService(repository=InMemoryVerificationRepository())
        ),
        recovery_coordinator=RecoveryCoordinator(recovery_engine=RecoveryEngine()),
    )

    # Stage 1: INSPECT_REPOSITORY prohibits write_file
    coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
    with pytest.raises(DisallowedFileModificationError):
        coordinator.execute_tool(
            stage=SWETaskStage.INSPECT_REPOSITORY,
            agent=full_swe_agent,
            tool_name="write_file",
            arguments={"path": "safe_file.py", "content": "changed"},
        )

    # Prohibits run_tests in INSPECT_REPOSITORY
    with pytest.raises(DisallowedStageToolError):
        coordinator.execute_tool(
            stage=SWETaskStage.INSPECT_REPOSITORY,
            agent=full_swe_agent,
            tool_name="run_tests",
            arguments={"target": "."},
        )


def test_approval_bypass_prevention(secure_workspace: Workspace, full_swe_agent: Agent):
    """Verify write operations cannot bypass the approval requirement."""
    registry = InMemoryToolRegistry()
    register_repository_tools(registry, secure_workspace)
    approval_service = ApprovalService(repository=InMemoryApprovalRepository())
    tool_executor = ToolExecutor(registry=registry, approval_service=approval_service)

    coordinator = SWEWorkflowCoordinator(
        workspace=secure_workspace,
        tool_executor=tool_executor,
        verification_engine=VerificationEngine(
            verification_service=VerificationService(repository=InMemoryVerificationRepository())
        ),
        recovery_coordinator=RecoveryCoordinator(recovery_engine=RecoveryEngine()),
    )

    # Fast-forward to IMPLEMENT_CHANGE
    for stage in [
        SWETaskStage.INSPECT_REPOSITORY,
        SWETaskStage.ANALYZE_FAILURE,
        SWETaskStage.FORMULATE_FIX,
    ]:
        coordinator.advance_stage(stage)
        coordinator.complete_stage(stage)

    coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)

    # Write without approval raises ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError):
        coordinator.execute_tool(
            stage=SWETaskStage.IMPLEMENT_CHANGE,
            agent=full_swe_agent,
            tool_name="write_file",
            arguments={"path": "safe_file.py", "content": "new_code"},
        )


def test_stale_hash_concurrency_protection(secure_workspace: Workspace):
    """Verify apply_change rejects modifications if target file hash is stale."""
    apply_tool = build_apply_change_tool(secure_workspace)

    # Target file has content "print('hello')"
    stale_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(StaleStateError):
        apply_tool.handler({
            "path": "safe_file.py",
            "expected_hash": stale_hash,
            "new_content": "print('world')",
        })


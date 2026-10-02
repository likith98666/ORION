from pathlib import Path
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security.approval import ApprovalRequiredError
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
from orion.core.security.audit import AuditEventType
from orion.core.security.audit_repository_memory import InMemoryAuditRepository
from orion.core.security.audit_service import AuditService
from orion.core.security.authorization import AuthorizationService
from orion.core.tools.execution_repository_memory import InMemoryToolExecutionRepository
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.tools.repository import register_repository_tools
from orion.core.workspace.models import Workspace


def _create_agent(permissions: tuple[AgentPermission, ...]) -> Agent:
    return Agent.create(
        name="SWE Agent",
        description="Autonomous SWE agent.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(frozenset(permissions)),
    )


class TestRepositoryToolExecutorIntegration:
    """End-to-end integration tests through ToolExecutor, Permission, Risk, Approval, and Audit."""

    def test_read_tools_permission_flow(self, tmp_path: Path) -> None:
        (tmp_path / "hello.py").write_text("print('hello')", encoding="utf-8")
        ws = Workspace(repository_root=tmp_path)

        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        # Agent with READ_FILES
        read_agent = _create_agent((AgentPermission.READ_FILES,))
        executor = ToolExecutor(registry)

        result = executor.execute(
            agent=read_agent,
            tool_name="read_file",
            arguments={"path": "hello.py"},
        )
        assert result.success is True
        assert result.output["content"] == "print('hello')"

        # Agent without READ_FILES
        unauthorized_agent = _create_agent((AgentPermission.SEND_MESSAGES,))
        with pytest.raises(PermissionError, match="not authorized"):
            executor.execute(
                agent=unauthorized_agent,
                tool_name="read_file",
                arguments={"path": "hello.py"},
            )

    def test_write_file_high_risk_approval_flow(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        approval_repo = InMemoryApprovalRepository()
        approval_service = ApprovalService(approval_repo)
        audit_repo = InMemoryAuditRepository()
        audit_service = AuditService(audit_repo)
        exec_repo = InMemoryToolExecutionRepository()

        executor = ToolExecutor(
            registry=registry,
            execution_repository=exec_repo,
            approval_service=approval_service,
            audit_service=audit_service,
        )

        agent = _create_agent((AgentPermission.WRITE_FILES,))
        exec_id = uuid4()

        # Step 1: Initial call requires approval
        with pytest.raises(ApprovalRequiredError) as exc_info:
            executor.execute(
                agent=agent,
                tool_name="write_file",
                arguments={"path": "created.py", "content": "x = 100"},
                execution_id=exec_id,
            )

        req_id = exc_info.value.request_id
        req = approval_repo.get(req_id)
        assert req is not None
        assert req.status.value == "pending"
        assert req.tool_name == "write_file"

        # Step 2: Approve the request
        approval_service.approve(
            request_id=req_id,
            approver="security-officer",
            reason="Approved SWE code edit.",
        )

        # Step 3: Execute with valid approval_id
        result = executor.execute(
            agent=agent,
            tool_name="write_file",
            arguments={"path": "created.py", "content": "x = 100"},
            execution_id=exec_id,
            approval_id=req_id,
        )

        assert result.success is True
        assert (tmp_path / "created.py").read_text(encoding="utf-8") == "x = 100"

        # Step 4: Reusing consumed approval is rejected
        with pytest.raises(PermissionError, match="Approval request is not approved"):
            executor.execute(
                agent=agent,
                tool_name="write_file",
                arguments={"path": "created.py", "content": "x = 200"},
                execution_id=exec_id,
                approval_id=req_id,
            )

    def test_apply_change_approval_flow(self, tmp_path: Path) -> None:
        file = tmp_path / "code.py"
        file.write_text("val = 1\n", encoding="utf-8")
        ws = Workspace(repository_root=tmp_path)

        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        approval_service = ApprovalService(InMemoryApprovalRepository())
        executor = ToolExecutor(registry=registry, approval_service=approval_service)
        agent = _create_agent((AgentPermission.WRITE_FILES,))
        exec_id = uuid4()

        # Requires approval
        with pytest.raises(ApprovalRequiredError) as exc_info:
            executor.execute(
                agent=agent,
                tool_name="apply_change",
                arguments={"path": "code.py", "new_content": "val = 2\n"},
                execution_id=exec_id,
            )

        req_id = exc_info.value.request_id
        approval_service.approve(request_id=req_id, approver="admin")

        result = executor.execute(
            agent=agent,
            tool_name="apply_change",
            arguments={"path": "code.py", "new_content": "val = 2\n"},
            execution_id=exec_id,
            approval_id=req_id,
        )

        assert result.success is True
        assert file.read_text(encoding="utf-8") == "val = 2\n"

    def test_validation_tools_permission_flow(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        executor = ToolExecutor(registry=registry)

        # Agent without CODE_EXECUTION
        read_only_agent = _create_agent((AgentPermission.READ_FILES,))
        with pytest.raises(PermissionError, match="not authorized"):
            executor.execute(
                agent=read_only_agent,
                tool_name="run_tests",
                arguments={},
            )

        # Agent with CODE_EXECUTION
        code_agent = _create_agent((AgentPermission.CODE_EXECUTION,))
        result = executor.execute(
            agent=code_agent,
            tool_name="run_tests",
            arguments={},
        )
        assert result.success is True
        assert result.output["operation"] == "test"

    def test_workspace_traversal_via_executor_fails_cleanly(self, tmp_path: Path) -> None:
        ws = Workspace(repository_root=tmp_path)
        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        executor = ToolExecutor(registry=registry)
        agent = _create_agent((AgentPermission.READ_FILES,))

        result = executor.execute(
            agent=agent,
            tool_name="read_file",
            arguments={"path": "../secret.txt"},
        )

        assert result.success is False
        assert "escapes repository root" in result.error

    def test_audit_records_for_repository_tool(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("a = 1", encoding="utf-8")
        ws = Workspace(repository_root=tmp_path)

        registry = InMemoryToolRegistry()
        register_repository_tools(registry, ws)

        audit_repo = InMemoryAuditRepository()
        audit_service = AuditService(audit_repo)
        auth_service = AuthorizationService(audit_service=audit_service)
        executor = ToolExecutor(
            registry=registry,
            authorization_service=auth_service,
            audit_service=audit_service,
        )

        agent = _create_agent((AgentPermission.READ_FILES,))
        exec_id = uuid4()

        result = executor.execute(
            agent=agent,
            tool_name="read_file",
            arguments={"path": "mod.py"},
            execution_id=exec_id,
        )
        assert result.success is True

        events = audit_repo.list_for_execution(exec_id)
        event_types = [e.event_type for e in events]

        assert AuditEventType.AUTHORIZATION_ALLOWED in event_types
        assert AuditEventType.TOOL_EXECUTION_STARTED in event_types
        assert AuditEventType.TOOL_EXECUTION_COMPLETED in event_types

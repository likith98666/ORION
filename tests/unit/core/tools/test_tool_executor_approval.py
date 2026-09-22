from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security.approval import ApprovalRequiredError
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent() -> Agent:
    return Agent.create(
        name="Approval Integration Agent",
        description="Agent used for approval integration tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WEB_ACCESS}),
        ),
    )


def _registry(handler=None) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="high_risk_tool",
            description="High-risk tool used for approval integration.",
            permission=AgentPermission.WEB_ACCESS,
            handler=handler or (lambda arguments: "executed"),
            risk_level=ToolRiskLevel.HIGH,
        )
    )

    return registry


def _approval_service() -> ApprovalService:
    return ApprovalService(InMemoryApprovalRepository())


def test_high_risk_tool_creates_approval_request() -> None:
    service = _approval_service()

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=_agent(),
            tool_name="high_risk_tool",
            arguments={},
        )

    request = service._repository.get(exc_info.value.request_id)

    assert request is not None
    assert request.status.value == "pending"
    assert request.tool_name == "high_risk_tool"
    assert request.action == "execute"
    assert request.risk_level == ToolRiskLevel.HIGH


def test_approved_high_risk_tool_executes() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="high_risk_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="test-approver",
        reason="Approved for integration test.",
    )

    result = executor.execute(
        agent=agent,
        tool_name="high_risk_tool",
        arguments={},
        execution_id=execution_id,
        approval_id=request_id,
    )

    assert result.success is True
    assert result.output == "executed"


def test_approval_is_bound_to_exact_execution_context() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="high_risk_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="test-approver",
    )

    with pytest.raises(PermissionError, match="execution"):
        executor.execute(
            agent=agent,
            tool_name="high_risk_tool",
            arguments={},
            execution_id=uuid4(),
            approval_id=request_id,
        )


def test_approval_is_one_time_use() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="high_risk_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="test-approver",
    )

    first = executor.execute(
        agent=agent,
        tool_name="high_risk_tool",
        arguments={},
        execution_id=execution_id,
        approval_id=request_id,
    )

    assert first.success is True

    with pytest.raises(PermissionError, match="not approved"):
        executor.execute(
            agent=agent,
            tool_name="high_risk_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request_id,
        )


def test_approval_happens_before_handler() -> None:
    calls = []

    def handler(arguments):
        calls.append("handler")
        return "executed"

    service = _approval_service()
    executor = ToolExecutor(
        _registry(handler),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError):
        executor.execute(
            agent=_agent(),
            tool_name="high_risk_tool",
            arguments={},
        )

    assert calls == []

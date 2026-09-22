from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    ApprovalService,
    InMemoryApprovalRepository,
)
from orion.core.security.approval import ApprovalStatus
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent(name: str = "Adversarial Security Agent") -> Agent:
    return Agent.create(
        name=name,
        description="Agent used for approval bypass tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WEB_ACCESS}),
        ),
    )


def _registry(
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH,
    handler=None,
    tool_name: str = "protected_tool",
) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name=tool_name,
            description="Protected tool used for adversarial security tests.",
            permission=AgentPermission.WEB_ACCESS,
            handler=handler or (lambda arguments: "executed"),
            risk_level=risk_level,
        )
    )

    return registry


def _service() -> ApprovalService:
    return ApprovalService(InMemoryApprovalRepository())


def _approved_request(
    service: ApprovalService,
    agent: Agent,
    execution_id,
    tool_name: str = "protected_tool",
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH,
):
    request = service.create_request(
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name=tool_name,
        action="execute",
        risk_level=risk_level,
    )

    service.approve(
        request_id=request.id,
        approver="security-test",
    )

    return request


def test_forged_approval_id_is_blocked() -> None:
    service = _service()
    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="was not found"):
        executor.execute(
            agent=_agent(),
            tool_name="protected_tool",
            arguments={},
            execution_id=uuid4(),
            approval_id=uuid4(),
        )


def test_denied_approval_is_blocked() -> None:
    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name="protected_tool",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    service.deny(
        request_id=request.id,
        approver="security-test",
        reason="Denied for adversarial test.",
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="not approved"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_expired_approval_is_blocked() -> None:
    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name="protected_tool",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    repository = service._repository

    repository.save(
        type(request)(
            id=request.id,
            agent_id=request.agent_id,
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            action=request.action,
            risk_level=request.risk_level,
            created_at=request.created_at,
            expires_at=request.expires_at,
            status=ApprovalStatus.APPROVED,
        )
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="expired"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_other_agents_approval_is_blocked() -> None:
    service = _service()
    approved_agent = _agent("Approved Agent")
    attacker_agent = _agent("Attacker Agent")
    execution_id = uuid4()

    request = _approved_request(
        service,
        approved_agent,
        execution_id,
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="agent"):
        executor.execute(
            agent=attacker_agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_other_execution_approval_is_blocked() -> None:
    service = _service()
    agent = _agent()
    approved_execution = uuid4()
    attacker_execution = uuid4()

    request = _approved_request(
        service,
        agent,
        approved_execution,
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="execution"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=attacker_execution,
            approval_id=request.id,
        )


def test_other_tool_approval_is_blocked() -> None:
    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = _approved_request(
        service,
        agent,
        execution_id,
        tool_name="different_tool",
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="tool"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_other_risk_level_approval_is_blocked() -> None:
    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = _approved_request(
        service,
        agent,
        execution_id,
        risk_level=ToolRiskLevel.HIGH,
    )

    executor = ToolExecutor(
        _registry(ToolRiskLevel.CRITICAL),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="risk level"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_consumed_approval_cannot_be_reused() -> None:
    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = _approved_request(
        service,
        agent,
        execution_id,
    )

    executor = ToolExecutor(
        _registry(),
        approval_service=service,
    )

    first = executor.execute(
        agent=agent,
        tool_name="protected_tool",
        arguments={},
        execution_id=execution_id,
        approval_id=request.id,
    )

    assert first.success is True

    with pytest.raises(PermissionError, match="not approved"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )


def test_handler_is_never_called_when_approval_is_invalid() -> None:
    calls = []

    def handler(arguments):
        calls.append("executed")
        return "executed"

    service = _service()
    agent = _agent()
    execution_id = uuid4()

    request = _approved_request(
        service,
        agent,
        execution_id,
        tool_name="different_tool",
    )

    executor = ToolExecutor(
        _registry(handler=handler),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="tool"):
        executor.execute(
            agent=agent,
            tool_name="protected_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert calls == []

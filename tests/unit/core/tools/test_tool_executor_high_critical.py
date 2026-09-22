from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    ApprovalRequiredError,
    ApprovalService,
    InMemoryApprovalRepository,
)
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent() -> Agent:
    return Agent.create(
        name="High Critical Security Agent",
        description="Agent used for high and critical risk enforcement tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WEB_ACCESS}),
        ),
    )


def _registry(risk_level: ToolRiskLevel) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="risk_controlled_tool",
            description="Risk-controlled tool used for security tests.",
            permission=AgentPermission.WEB_ACCESS,
            handler=lambda arguments: "executed",
            risk_level=risk_level,
        )
    )

    return registry


def _approval_service() -> ApprovalService:
    return ApprovalService(InMemoryApprovalRepository())


def test_high_risk_without_approval_service_is_blocked() -> None:
    executor = ToolExecutor(
        _registry(ToolRiskLevel.HIGH),
    )

    with pytest.raises(
        PermissionError,
        match="requires approval",
    ):
        executor.execute(
            agent=_agent(),
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=uuid4(),
        )


def test_critical_risk_without_approval_service_is_blocked() -> None:
    executor = ToolExecutor(
        _registry(ToolRiskLevel.CRITICAL),
    )

    with pytest.raises(
        PermissionError,
        match="requires approval",
    ):
        executor.execute(
            agent=_agent(),
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=uuid4(),
        )


def test_valid_high_risk_approval_allows_execution() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    executor = ToolExecutor(
        _registry(ToolRiskLevel.HIGH),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="security-test",
        reason="Approved HIGH-risk test action.",
    )

    result = executor.execute(
        agent=agent,
        tool_name="risk_controlled_tool",
        arguments={},
        execution_id=execution_id,
        approval_id=request_id,
    )

    assert result.success is True
    assert result.output == "executed"


def test_valid_critical_risk_approval_allows_execution() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    executor = ToolExecutor(
        _registry(ToolRiskLevel.CRITICAL),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="security-test",
        reason="Approved CRITICAL-risk test action.",
    )

    result = executor.execute(
        agent=agent,
        tool_name="risk_controlled_tool",
        arguments={},
        execution_id=execution_id,
        approval_id=request_id,
    )

    assert result.success is True
    assert result.output == "executed"


def test_critical_approval_cannot_authorize_high_risk_action() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    critical_executor = ToolExecutor(
        _registry(ToolRiskLevel.CRITICAL),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        critical_executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="security-test",
    )

    high_executor = ToolExecutor(
        _registry(ToolRiskLevel.HIGH),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="risk"):
        high_executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request_id,
        )


def test_high_approval_cannot_authorize_critical_risk_action() -> None:
    service = _approval_service()
    agent = _agent()
    execution_id = uuid4()

    high_executor = ToolExecutor(
        _registry(ToolRiskLevel.HIGH),
        approval_service=service,
    )

    with pytest.raises(ApprovalRequiredError) as exc_info:
        high_executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
        )

    request_id = exc_info.value.request_id

    service.approve(
        request_id=request_id,
        approver="security-test",
    )

    critical_executor = ToolExecutor(
        _registry(ToolRiskLevel.CRITICAL),
        approval_service=service,
    )

    with pytest.raises(PermissionError, match="risk"):
        critical_executor.execute(
            agent=agent,
            tool_name="risk_controlled_tool",
            arguments={},
            execution_id=execution_id,
            approval_id=request_id,
        )

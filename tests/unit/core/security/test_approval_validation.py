from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_repository_memory import (
    InMemoryApprovalRepository,
)
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel


def create_approved_request():
    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    agent_id = uuid4()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    service.approve(
        request_id=request.id,
        approver="operator",
    )

    return service, repository, request, agent_id, execution_id


def test_validate_approval_accepts_exact_context() -> None:
    service, _, request, agent_id, execution_id = create_approved_request()

    validated = service.validate_approval(
        request_id=request.id,
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    assert validated.id == request.id
    assert validated.status is ApprovalStatus.APPROVED


def test_validate_approval_rejects_wrong_agent() -> None:
    service, _, request, _, execution_id = create_approved_request()

    with pytest.raises(PermissionError, match="agent"):
        service.validate_approval(
            request_id=request.id,
            agent_id=uuid4(),
            execution_id=execution_id,
            tool_name="send_message",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_validate_approval_rejects_wrong_execution() -> None:
    service, _, request, agent_id, _ = create_approved_request()

    with pytest.raises(PermissionError, match="execution"):
        service.validate_approval(
            request_id=request.id,
            agent_id=agent_id,
            execution_id=uuid4(),
            tool_name="send_message",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_validate_approval_rejects_wrong_tool() -> None:
    service, _, request, agent_id, execution_id = create_approved_request()

    with pytest.raises(PermissionError, match="tool"):
        service.validate_approval(
            request_id=request.id,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name="delete_resource",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_validate_approval_rejects_wrong_action() -> None:
    service, _, request, agent_id, execution_id = create_approved_request()

    with pytest.raises(PermissionError, match="action"):
        service.validate_approval(
            request_id=request.id,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name="send_message",
            action="delete",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_validate_approval_rejects_wrong_risk_level() -> None:
    service, _, request, agent_id, execution_id = create_approved_request()

    with pytest.raises(PermissionError, match="risk level"):
        service.validate_approval(
            request_id=request.id,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name="send_message",
            action="execute",
            risk_level=ToolRiskLevel.CRITICAL,
        )


def test_validate_approval_rejects_missing_request() -> None:
    service, _, _, agent_id, execution_id = create_approved_request()

    with pytest.raises(PermissionError, match="was not found"):
        service.validate_approval(
            request_id=uuid4(),
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name="send_message",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_validate_approval_rejects_expired_request() -> None:
    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    agent_id = uuid4()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

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

    with pytest.raises(PermissionError, match="expired"):
        service.validate_approval(
            request_id=request.id,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name="send_message",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )

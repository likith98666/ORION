from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.security.approval import ApprovalDecision, ApprovalStatus
from orion.core.security.approval_repository_memory import (
    InMemoryApprovalRepository,
)
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel


def create_service() -> tuple[
    ApprovalService,
    InMemoryApprovalRepository,
]:
    repository = InMemoryApprovalRepository()
    return ApprovalService(repository), repository


def test_create_request_persists_pending_request() -> None:
    service, repository = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        execution_id=uuid4(),
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    stored = repository.get(request.id)

    assert stored == request
    assert request.status is ApprovalStatus.PENDING


def test_create_request_rejects_low_risk() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError):
        service.create_request(
            agent_id=uuid4(),
            tool_name="read_file",
            action="execute",
            risk_level=ToolRiskLevel.LOW,
        )


def test_create_request_rejects_medium_risk() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError):
        service.create_request(
            agent_id=uuid4(),
            tool_name="search",
            action="execute",
            risk_level=ToolRiskLevel.MEDIUM,
        )


def test_approve_changes_request_to_approved() -> None:
    service, repository = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    record = service.approve(
        request_id=request.id,
        approver="operator",
        reason="Approved for the requested action.",
    )

    stored = repository.get(request.id)

    assert record.decision is ApprovalDecision.APPROVE
    assert record.approver == "operator"
    assert stored is not None
    assert stored.status is ApprovalStatus.APPROVED


def test_deny_changes_request_to_denied() -> None:
    service, repository = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        tool_name="delete_resource",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
    )

    record = service.deny(
        request_id=request.id,
        approver="operator",
        reason="Operation was not approved.",
    )

    stored = repository.get(request.id)

    assert record.decision is ApprovalDecision.DENY
    assert stored is not None
    assert stored.status is ApprovalStatus.DENIED


def test_approved_request_cannot_be_approved_again() -> None:
    service, _ = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    service.approve(
        request_id=request.id,
        approver="operator",
    )

    with pytest.raises(ValueError, match="no longer pending"):
        service.approve(
            request_id=request.id,
            approver="operator",
        )


def test_denied_request_cannot_be_approved() -> None:
    service, _ = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    service.deny(
        request_id=request.id,
        approver="operator",
    )

    with pytest.raises(ValueError, match="no longer pending"):
        service.approve(
            request_id=request.id,
            approver="operator",
        )


def test_expired_request_cannot_be_approved() -> None:
    service, repository = create_service()

    request = service.create_request(
        agent_id=uuid4(),
        tool_name="delete_resource",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="expired"):
        service.approve(
            request_id=request.id,
            approver="operator",
        )

    stored = repository.get(request.id)

    assert stored is not None
    assert stored.status is ApprovalStatus.EXPIRED


def test_unknown_request_is_rejected() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError, match="was not found"):
        service.approve(
            request_id=uuid4(),
            approver="operator",
        )

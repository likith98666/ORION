from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.security.approval import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
)
from orion.core.security.risk import ToolRiskLevel


def test_approval_request_is_created_as_pending() -> None:
    agent_id = uuid4()

    request = ApprovalRequest.create(
        agent_id=agent_id,
        execution_id=uuid4(),
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    assert request.agent_id == agent_id
    assert request.tool_name == "send_message"
    assert request.action == "execute"
    assert request.risk_level is ToolRiskLevel.HIGH
    assert request.status is ApprovalStatus.PENDING
    assert request.created_at.tzinfo is not None


def test_approval_request_strips_identifiers() -> None:
    request = ApprovalRequest.create(
        agent_id=uuid4(),
        tool_name="  send_message  ",
        action="  execute  ",
        risk_level=ToolRiskLevel.CRITICAL,
    )

    assert request.tool_name == "send_message"
    assert request.action == "execute"


def test_approval_request_detects_expiration() -> None:
    request = ApprovalRequest.create(
        agent_id=uuid4(),
        tool_name="delete_resource",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert request.is_expired is True


def test_approval_request_without_expiry_is_not_expired() -> None:
    request = ApprovalRequest.create(
        agent_id=uuid4(),
        tool_name="delete_resource",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
    )

    assert request.is_expired is False


def test_approval_request_rejects_empty_tool_name() -> None:
    with pytest.raises(ValueError):
        ApprovalRequest.create(
            agent_id=uuid4(),
            tool_name="   ",
            action="execute",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_approval_request_rejects_empty_action() -> None:
    with pytest.raises(ValueError):
        ApprovalRequest.create(
            agent_id=uuid4(),
            tool_name="send_message",
            action="   ",
            risk_level=ToolRiskLevel.HIGH,
        )


def test_approval_record_accepts_approval_decision() -> None:
    request_id = uuid4()

    record = ApprovalRecord(
        request_id=request_id,
        decision=ApprovalDecision.APPROVE,
        approver="operator",
        decided_at=datetime.now(UTC),
        reason="Approved for the requested operation.",
    )

    assert record.request_id == request_id
    assert record.decision is ApprovalDecision.APPROVE
    assert record.approver == "operator"


def test_approval_record_rejects_empty_approver() -> None:
    with pytest.raises(ValueError):
        ApprovalRecord(
            request_id=uuid4(),
            decision=ApprovalDecision.DENY,
            approver="   ",
            decided_at=datetime.now(UTC),
        )


def test_approval_record_rejects_empty_reason() -> None:
    with pytest.raises(ValueError):
        ApprovalRecord(
            request_id=uuid4(),
            decision=ApprovalDecision.DENY,
            approver="operator",
            decided_at=datetime.now(UTC),
            reason="   ",
        )

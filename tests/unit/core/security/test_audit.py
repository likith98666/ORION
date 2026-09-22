from datetime import UTC, datetime
from uuid import uuid4

import pytest

from orion.core.security.audit import AuditEvent, AuditEventType
from orion.core.security.risk import ToolRiskLevel


def test_audit_event_create_generates_identity_and_timestamp() -> None:
    event = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_STARTED,
        agent_id=uuid4(),
        execution_id=uuid4(),
        tool_name="web_search",
        action="execute",
        risk_level=ToolRiskLevel.LOW,
        outcome="started",
    )

    assert isinstance(event.id, type(uuid4()))
    assert event.timestamp.tzinfo is not None
    assert event.event_type == AuditEventType.TOOL_EXECUTION_STARTED
    assert event.tool_name == "web_search"


def test_audit_event_is_immutable() -> None:
    event = AuditEvent.create(AuditEventType.AUTHORIZATION_ALLOWED)

    with pytest.raises(AttributeError):
        event.outcome = "changed"


def test_audit_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AuditEvent(
            id=uuid4(),
            event_type=AuditEventType.AUTHORIZATION_ALLOWED,
            timestamp=datetime.now(),
        )


def test_audit_event_rejects_empty_tool_name() -> None:
    with pytest.raises(ValueError, match="tool name"):
        AuditEvent.create(
            AuditEventType.TOOL_EXECUTION_STARTED,
            tool_name="   ",
        )


def test_audit_event_rejects_empty_action() -> None:
    with pytest.raises(ValueError, match="action"):
        AuditEvent.create(
            AuditEventType.AUTHORIZATION_ALLOWED,
            action="   ",
        )


def test_audit_event_rejects_empty_outcome() -> None:
    with pytest.raises(ValueError, match="outcome"):
        AuditEvent.create(
            AuditEventType.TOOL_EXECUTION_COMPLETED,
            outcome="   ",
        )


def test_audit_event_copies_details() -> None:
    details = {"key": "value"}
    event = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_COMPLETED,
        details=details,
    )

    details["key"] = "changed"

    assert event.details["key"] == "value"


def test_audit_event_rejects_invalid_details() -> None:
    with pytest.raises(TypeError, match="dictionary"):
        AuditEvent(
            id=uuid4(),
            event_type=AuditEventType.AUTHORIZATION_ALLOWED,
            timestamp=datetime.now(UTC),
            details=[],
        )

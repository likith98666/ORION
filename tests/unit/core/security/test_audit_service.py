from uuid import uuid4

from orion.core.security.audit import AuditEventType
from orion.core.security.audit_repository_memory import InMemoryAuditRepository
from orion.core.security.audit_service import AuditService
from orion.core.security.redaction import REDACTED_VALUE, RedactionEngine
from orion.core.security.risk import ToolRiskLevel


def test_record_persists_audit_event() -> None:
    repository = InMemoryAuditRepository()
    service = AuditService(repository)

    event = service.record(
        AuditEventType.TOOL_EXECUTION_STARTED,
        agent_id=uuid4(),
        execution_id=uuid4(),
        tool_name="web_search",
        action="execute",
        risk_level=ToolRiskLevel.LOW,
        outcome="started",
    )

    assert repository.get(event.id) == event


def test_record_redacts_secret_details() -> None:
    repository = InMemoryAuditRepository()
    service = AuditService(
        repository,
        RedactionEngine(("super-secret",)),
    )

    event = service.record(
        AuditEventType.TOOL_EXECUTION_FAILED,
        details={
            "error": "API failed with super-secret",
            "nested": {
                "credential": "super-secret",
            },
        },
    )

    assert event.details == {
        "error": f"API failed with {REDACTED_VALUE}",
        "nested": {
            "credential": REDACTED_VALUE,
        },
    }


def test_record_preserves_non_sensitive_metadata() -> None:
    repository = InMemoryAuditRepository()
    service = AuditService(repository)

    event = service.record(
        AuditEventType.TOOL_EXECUTION_COMPLETED,
        details={
            "duration_ms": 120,
            "success": True,
        },
    )

    assert event.details == {
        "duration_ms": 120,
        "success": True,
    }


def test_record_returns_persisted_redacted_event() -> None:
    repository = InMemoryAuditRepository()
    service = AuditService(
        repository,
        RedactionEngine(("token-value",)),
    )

    event = service.record(
        AuditEventType.SECRET_REDACTED,
        details={"token": "token-value"},
    )

    stored = repository.get(event.id)

    assert stored is not None
    assert stored.details["token"] == REDACTED_VALUE
    assert stored == event

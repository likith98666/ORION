from typing import Any
from uuid import UUID

from orion.core.security.audit import AuditEvent, AuditEventType
from orion.core.security.audit_repository import AuditRepository
from orion.core.security.redaction import RedactionEngine
from orion.core.security.risk import ToolRiskLevel


class AuditService:
    """Creates redacted security audit events."""

    def __init__(
        self,
        repository: AuditRepository,
        redaction_engine: RedactionEngine | None = None,
    ) -> None:
        self._repository = repository
        self._redaction_engine = redaction_engine or RedactionEngine()

    def register_secret(self, secret: str) -> None:
        """Register a resolved secret for subsequent redaction."""
        self._redaction_engine.register(secret)

    def redact(self, value: Any) -> Any:
        """Redact known secrets from a value."""
        return self._redaction_engine.redact(value)

    def record(
        self,
        event_type: AuditEventType,
        *,
        agent_id: UUID | None = None,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_name: str | None = None,
        action: str | None = None,
        risk_level: ToolRiskLevel | None = None,
        outcome: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create, redact, persist, and return an audit event."""
        event = AuditEvent.create(
            event_type,
            agent_id=agent_id,
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            outcome=outcome,
            details=details,
        )

        redacted_event = AuditEvent(
            id=event.id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            agent_id=event.agent_id,
            task_id=event.task_id,
            execution_id=event.execution_id,
            tool_name=event.tool_name,
            action=event.action,
            risk_level=event.risk_level,
            outcome=event.outcome,
            details=self.redact(event.details),
        )

        self._repository.save(redacted_event)

        return redacted_event

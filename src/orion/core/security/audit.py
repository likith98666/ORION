from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from orion.core.security.risk import ToolRiskLevel


class AuditEventType(str, Enum):
    AUTHORIZATION_ALLOWED = "authorization_allowed"
    AUTHORIZATION_DENIED = "authorization_denied"
    AUTHORIZATION_APPROVAL_REQUIRED = "authorization_approval_required"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    SECRET_REDACTED = "secret_redacted"


@dataclass(frozen=True)
class AuditEvent:
    id: UUID
    event_type: AuditEventType
    timestamp: datetime
    agent_id: UUID | None = None
    task_id: UUID | None = None
    execution_id: UUID | None = None
    tool_name: str | None = None
    action: str | None = None
    risk_level: ToolRiskLevel | None = None
    outcome: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID.")

        if not isinstance(self.event_type, AuditEventType):
            raise TypeError("event_type must be an AuditEventType.")

        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime.")

        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware.")

        for name, value in (
            ("tool_name", self.tool_name),
            ("action", self.action),
            ("outcome", self.outcome),
        ):
            if value is not None:
                if not isinstance(value, str):
                    raise TypeError(f"{name} must be a string or None.")
                if not value.strip():
                    raise ValueError(f"{name.replace('_', ' ')} must not be empty.")

        if not isinstance(self.details, dict):
            raise TypeError("details must be a dictionary.")

        object.__setattr__(self, "details", dict(self.details))

    @classmethod
    def create(
        cls,
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
    ) -> "AuditEvent":
        return cls(
            id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(UTC),
            agent_id=agent_id,
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            outcome=outcome,
            details={} if details is None else details,
        )

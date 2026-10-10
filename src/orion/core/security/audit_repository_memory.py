from uuid import UUID

from orion.core.security.audit import AuditEvent
from orion.core.security.audit_repository import AuditRepository


class InMemoryAuditRepository(AuditRepository):
    """In-memory audit repository for deterministic tests and local execution."""

    def __init__(self) -> None:
        self._events: dict[UUID, AuditEvent] = {}

    def save(self, event: AuditEvent) -> None:
        if not isinstance(event, AuditEvent):
            raise TypeError("Audit repository accepts only AuditEvent instances.")

        self._events[event.id] = event

    def get(self, event_id: UUID) -> AuditEvent | None:
        if not isinstance(event_id, UUID):
            raise TypeError("Audit event id must be a UUID.")

        return self._events.get(event_id)

    def list_for_agent(self, agent_id: UUID) -> list[AuditEvent]:
        if not isinstance(agent_id, UUID):
            raise TypeError("Agent id must be a UUID.")

        return [event for event in self._events.values() if event.agent_id == agent_id]

    def list_for_execution(self, execution_id: UUID) -> list[AuditEvent]:
        if not isinstance(execution_id, UUID):
            raise TypeError("Execution id must be a UUID.")

        return [event for event in self._events.values() if event.execution_id == execution_id]

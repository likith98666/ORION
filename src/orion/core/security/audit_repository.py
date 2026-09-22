from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.security.audit import AuditEvent


class AuditRepository(ABC):
    """Persistence boundary for ORION security audit events."""

    @abstractmethod
    def save(self, event: AuditEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, event_id: UUID) -> AuditEvent | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_agent(self, agent_id: UUID) -> list[AuditEvent]:
        raise NotImplementedError

    @abstractmethod
    def list_for_execution(self, execution_id: UUID) -> list[AuditEvent]:
        raise NotImplementedError

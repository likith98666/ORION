from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.memory.models import MemoryRecord, MemoryType


class MemoryRepository(ABC):
    """Persistence boundary for ORION memory records."""

    @abstractmethod
    def save(self, memory: MemoryRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, memory_id: UUID) -> MemoryRecord | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, memory_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_task(self, task_id: UUID) -> list[MemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_for_agent(self, agent_id: UUID) -> list[MemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_by_type(
        self,
        memory_type: MemoryType,
    ) -> list[MemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[MemoryRecord]:
        raise NotImplementedError

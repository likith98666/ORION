from uuid import UUID

from orion.core.memory.models import MemoryRecord, MemoryType
from orion.core.memory.repository import MemoryRepository


class InMemoryMemoryRepository(MemoryRepository):
    """In-memory persistence for ORION memory records."""

    def __init__(self) -> None:
        self._memories: dict[UUID, MemoryRecord] = {}

    def save(self, memory: MemoryRecord) -> None:
        self._memories[memory.id] = memory

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        return self._memories.get(memory_id)

    def delete(self, memory_id: UUID) -> None:
        self._memories.pop(memory_id, None)

    def list_for_task(self, task_id: UUID) -> list[MemoryRecord]:
        return [memory for memory in self._memories.values() if memory.task_id == task_id]

    def list_for_agent(self, agent_id: UUID) -> list[MemoryRecord]:
        return [memory for memory in self._memories.values() if memory.agent_id == agent_id]

    def list_by_type(
        self,
        memory_type: MemoryType,
    ) -> list[MemoryRecord]:
        return [memory for memory in self._memories.values() if memory.memory_type == memory_type]

    def list_all(self) -> list[MemoryRecord]:
        return list(self._memories.values())

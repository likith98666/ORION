from dataclasses import dataclass
from uuid import UUID

from orion.core.memory.retrieval_models import MemoryRetrievalResult


@dataclass(frozen=True)
class ExecutionMemoryContext:
    """Bounded memory context selected for a single agent execution."""

    task_id: UUID
    agent_id: UUID
    memories: tuple[MemoryRetrievalResult, ...] = ()
    max_memories: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID.")

        if not isinstance(self.agent_id, UUID):
            raise TypeError("agent_id must be a UUID.")

        if not isinstance(self.memories, tuple):
            raise TypeError("memories must be a tuple.")

        if not isinstance(self.max_memories, int):
            raise TypeError("max_memories must be an integer.")

        if self.max_memories < 1 or self.max_memories > 100:
            raise ValueError("max_memories must be between 1 and 100.")

        if len(self.memories) > self.max_memories:
            raise ValueError(
                "memories cannot exceed max_memories."
            )

        memory_ids: set[UUID] = set()

        for result in self.memories:
            if not isinstance(result, MemoryRetrievalResult):
                raise TypeError(
                    "memories must contain only MemoryRetrievalResult instances."
                )

            memory_id = result.memory.id

            if memory_id in memory_ids:
                raise ValueError(
                    f"Duplicate memory in execution context: {memory_id}"
                )

            memory_ids.add(memory_id)

    @property
    def is_empty(self) -> bool:
        """Return whether no memories were selected."""

        return not self.memories

    @property
    def memory_count(self) -> int:
        """Return the number of selected memories."""

        return len(self.memories)

from datetime import datetime
from typing import Any
from uuid import UUID

from orion.core.agents.executions import AgentExecution
from orion.core.memory.models import (
    MemoryImportance,
    MemoryRecord,
    MemoryType,
)
from orion.core.memory.repository import MemoryRepository
from orion.core.memory.retrieval import MemoryRetrieval
from orion.core.memory.retrieval_models import (
    ExecutionMemoryQuery,
    MemoryQuery,
    MemoryRetrievalResult,
)


class MemoryService:
    """Application service for ORION memory operations."""

    def __init__(
        self,
        repository: MemoryRepository,
        retrieval: MemoryRetrieval | None = None,
    ) -> None:
        self._repository = repository
        self._retrieval = retrieval or MemoryRetrieval()

    def remember(
        self,
        content: str,
        memory_type: MemoryType,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        task_id: UUID | None = None,
        agent_id: UUID | None = None,
        source_execution_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Create and persist a memory record."""

        memory = MemoryRecord.create(
            content=content,
            memory_type=memory_type,
            importance=importance,
            task_id=task_id,
            agent_id=agent_id,
            source_execution_id=source_execution_id,
            metadata=metadata,
        )

        self._repository.save(memory)

        return memory

    def remember_execution(
        self,
        execution: AgentExecution,
        task_id: UUID | None = None,
    ) -> MemoryRecord:
        """Convert an agent execution outcome into episodic memory."""

        if execution.status.value == "completed":
            content = f"Agent execution completed successfully. Output: {execution.output or ''}"
            importance = MemoryImportance.MEDIUM
        elif execution.status.value == "failed":
            content = f"Agent execution failed. Error: {execution.error_message or 'Unknown error'}"
            importance = MemoryImportance.HIGH
        else:
            content = f"Agent execution ended with status '{execution.status.value}'."
            importance = MemoryImportance.LOW

        return self.remember(
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=importance,
            task_id=task_id,
            agent_id=execution.agent_id,
            source_execution_id=execution.id,
            metadata={
                "execution_status": execution.status.value,
                "agent_task_id": str(execution.agent_task_id),
                "model_name": execution.model_name,
                "provider_name": execution.provider_name,
                "input_tokens": execution.input_tokens,
                "output_tokens": execution.output_tokens,
                "latency_ms": execution.latency_ms,
            },
        )

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        """Retrieve a memory record by ID."""

        memory = self._repository.get(memory_id)

        if memory is not None:
            self._mark_accessed(memory)

        return memory

    def retrieve(
        self,
        query: MemoryQuery,
        *,
        now: datetime | None = None,
    ) -> list[MemoryRetrievalResult]:
        """Retrieve and rank memories using strict query semantics."""

        memories = self._repository.list_all()
        results = self._retrieval.retrieve(
            memories,
            query,
            now=now,
        )

        for result in results:
            self._mark_accessed(result.memory)

        return results

    def retrieve_for_execution(
        self,
        query: ExecutionMemoryQuery,
        *,
        now: datetime | None = None,
    ) -> list[MemoryRetrievalResult]:
        """Retrieve memories for execution context.

        Task and agent identifiers are ranking context rather than hard
        filters. Other query constraints remain strict.
        """

        memories = self._repository.list_all()
        results = self._retrieval.retrieve_for_execution(
            memories,
            query,
            now=now,
        )

        for result in results:
            self._mark_accessed(result.memory)

        return results

    def list_for_task(self, task_id: UUID) -> list[MemoryRecord]:
        """Retrieve memories associated with a task."""

        memories = self._repository.list_for_task(task_id)

        for memory in memories:
            self._mark_accessed(memory)

        return memories

    def list_for_agent(self, agent_id: UUID) -> list[MemoryRecord]:
        """Retrieve memories associated with an agent."""

        memories = self._repository.list_for_agent(agent_id)

        for memory in memories:
            self._mark_accessed(memory)

        return memories

    def list_by_type(
        self,
        memory_type: MemoryType,
    ) -> list[MemoryRecord]:
        """Retrieve memories of a specific type."""

        memories = self._repository.list_by_type(memory_type)

        for memory in memories:
            self._mark_accessed(memory)

        return memories

    def delete(self, memory_id: UUID) -> None:
        """Delete a memory record."""

        self._repository.delete(memory_id)

    def _mark_accessed(self, memory: MemoryRecord) -> None:
        memory.access_count += 1
        memory.last_accessed_at = datetime.now()
        self._repository.save(memory)

from datetime import timedelta

from orion.core.agents.tasks import AgentTask
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.models import MemoryImportance, MemoryType
from orion.core.memory.retrieval_models import ExecutionMemoryQuery
from orion.core.memory.service import MemoryService


class MemoryContextProvider:
    """Build bounded, execution-aware memory context for an agent task."""

    DEFAULT_MAX_MEMORIES = 5

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        max_memories: int = DEFAULT_MAX_MEMORIES,
        memory_types: frozenset[MemoryType] | None = None,
        minimum_importance: MemoryImportance | None = None,
        max_age: timedelta | None = None,
    ) -> None:
        if max_memories < 1 or max_memories > 100:
            raise ValueError("max_memories must be between 1 and 100.")

        self._memory_service = memory_service
        self._max_memories = max_memories
        self._memory_types = memory_types or frozenset()
        self._minimum_importance = minimum_importance
        self._max_age = max_age

    def provide(self, task: AgentTask) -> ExecutionMemoryContext:
        """Retrieve bounded memory context relevant to the execution task."""

        if task.assigned_agent_id is None:
            raise ValueError(
                "Memory context requires an assigned agent."
            )

        query = ExecutionMemoryQuery(
            query=task.description,
            task_id=task.task_id,
            agent_id=task.assigned_agent_id,
            memory_types=self._memory_types,
            minimum_importance=self._minimum_importance,
            max_age=self._max_age,
            limit=self._max_memories,
        )

        results = self._memory_service.retrieve_for_execution(query)

        return ExecutionMemoryContext(
            task_id=task.task_id,
            agent_id=task.assigned_agent_id,
            memories=tuple(results),
            max_memories=self._max_memories,
        )

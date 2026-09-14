from uuid import UUID

from orion.core.agents.task_repository import AgentTaskRepository
from orion.core.agents.tasks import AgentTask


class InMemoryAgentTaskRepository(AgentTaskRepository):
    """In-memory implementation of the ORION agent task repository."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, AgentTask] = {}

    def save(self, task: AgentTask) -> None:
        """Save an agent task."""
        self._tasks[task.id] = task

    def get(self, task_id: UUID) -> AgentTask | None:
        """Get an agent task by ID."""
        return self._tasks.get(task_id)

    def delete(self, task_id: UUID) -> None:
        """Delete an agent task."""
        self._tasks.pop(task_id, None)

    def list_for_task(self, task_id: UUID) -> list[AgentTask]:
        """List all agent tasks belonging to a parent task."""
        return [
            task
            for task in self._tasks.values()
            if task.task_id == task_id
        ]
from uuid import UUID

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.permissions import AgentPermission
from orion.core.agents.task_manager import AgentTaskManager
from orion.core.agents.task_repository import AgentTaskRepository
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


class AgentTaskService:
    def __init__(self, repository: AgentTaskRepository) -> None:
        self._repository = repository
        self._manager = AgentTaskManager()

    def create_task(
        self,
        task_id: UUID,
        description: str,
        required_capability: AgentCapability,
        plan_step_id: UUID | None = None,
        required_permissions: frozenset[AgentPermission] | None = None,
    ) -> AgentTask:
        task = AgentTask.create(
            task_id=task_id,
            plan_step_id=plan_step_id,
            description=description,
            required_capability=required_capability,
            required_permissions=required_permissions,
        )

        self._repository.save(task)

        return task

    def get_task(self, task_id: UUID) -> AgentTask | None:
        return self._repository.get(task_id)

    def update_status(
        self,
        task_id: UUID,
        status: AgentTaskStatus,
    ) -> AgentTask:
        task = self._repository.get(task_id)

        if task is None:
            raise ValueError(f"Agent task not found: {task_id}")

        updated_task = self._manager.update_status(task, status)

        self._repository.save(updated_task)

        return updated_task

    def list_for_task(self, task_id: UUID) -> list[AgentTask]:
        return self._repository.list_for_task(task_id)

from orion.core.agents.assigner import AgentAssigner
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.task_manager import AgentTaskManager
from orion.core.agents.task_repository import AgentTaskRepository
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


class AgentAssignmentService:
    def __init__(
        self,
        task_repository: AgentTaskRepository,
        capability_registry: AgentCapabilityRegistry,
    ) -> None:
        self._task_repository = task_repository
        self._assigner = AgentAssigner(capability_registry)
        self._task_manager = AgentTaskManager()

    def assign_task(self, task: AgentTask) -> AgentTask:
        if task.status != AgentTaskStatus.PENDING:
            raise ValueError(
    "Only pending tasks can be assigned"
)

        assignment = self._assigner.assign(task)

        task.assigned_agent_id = assignment.agent_id

        updated_task = self._task_manager.update_status(
            task,
            AgentTaskStatus.ASSIGNED,
        )

        self._task_repository.save(updated_task)

        return updated_task
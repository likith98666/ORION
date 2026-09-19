from orion.core.agents.assignment import AgentAssignment
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import AgentStatus
from orion.core.agents.task_repository import AgentTaskRepository
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


class AgentAssigner:
    """Assigns tasks to active capable agents using current workload."""

    def __init__(
        self,
        capability_registry: AgentCapabilityRegistry,
        task_repository: AgentTaskRepository,
    ) -> None:
        self._capability_registry = capability_registry
        self._task_repository = task_repository

    def assign(self, task: AgentTask) -> AgentAssignment:
        """Assign a task to the least-loaded active capable agent."""

        agents = self._capability_registry.find_by_capability(
            task.required_capability
        )

        if not agents:
            raise ValueError(
                f"No agent available with capability "
                f"'{task.required_capability.value}'."
            )

        available_agents = [
            agent
            for agent in agents
            if agent.status == AgentStatus.ACTIVE
        ]

        if not available_agents:
            raise ValueError(
                f"No active agent available with capability "
                f"'{task.required_capability.value}'."
            )

        all_tasks = self._task_repository.list_all()

        loads = {
            agent.id: sum(
                1
                for existing_task in all_tasks
                if (
                    existing_task.assigned_agent_id == agent.id
                    and existing_task.status
                    in {
                        AgentTaskStatus.ASSIGNED,
                        AgentTaskStatus.RUNNING,
                    }
                )
            )
            for agent in available_agents
        }

        agent = min(
            available_agents,
            key=lambda candidate: loads[candidate.id],
        )

        return AgentAssignment.create(
            agent=agent,
            capability=task.required_capability,
        )

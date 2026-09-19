from orion.core.agents.assignment import AgentAssignment
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import AgentStatus
from orion.core.agents.tasks import AgentTask


class AgentAssigner:
    """Assigns agent tasks to active agents with the required capability."""

    def __init__(
        self,
        capability_registry: AgentCapabilityRegistry,
    ) -> None:
        self._capability_registry = capability_registry

    def assign(self, task: AgentTask) -> AgentAssignment:
        """Assign a task to the first active agent with the required capability."""

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

        agent = available_agents[0]

        return AgentAssignment.create(
            agent=agent,
            capability=task.required_capability,
        )

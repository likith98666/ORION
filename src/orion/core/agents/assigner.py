from orion.core.agents.assignment import AgentAssignment
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.tasks import AgentTask


class AgentAssigner:
    """Assigns agent tasks to capable ORION agents."""

    def __init__(
        self,
        capability_registry: AgentCapabilityRegistry,
    ) -> None:
        self._capability_registry = capability_registry

    def assign(self, task: AgentTask) -> AgentAssignment:
        """Assign a task to an available agent with the required capability."""

        agents = self._capability_registry.find_by_capability(
            task.required_capability
        )

        if not agents:
            raise ValueError(
                f"No agent available with capability "
                f"'{task.required_capability.value}'."
            )

        agent = agents[0]

        return AgentAssignment.create(
            agent=agent,
            capability=task.required_capability,
        )
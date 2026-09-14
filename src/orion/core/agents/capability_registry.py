from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent


class AgentCapabilityRegistry:
    """Find agents based on their capabilities."""

    def __init__(self) -> None:
        self._agents: list[Agent] = []

    def register(self, agent: Agent) -> None:
        """Register an agent for capability-based lookup."""

        if agent in self._agents:
            raise ValueError(
                f"Agent '{agent.name}' is already registered."
            )

        self._agents.append(agent)

    def find_by_capability(
        self,
        capability: AgentCapability,
    ) -> list[Agent]:
        """Return all agents that have the requested capability."""

        return [
            agent
            for agent in self._agents
            if capability in agent.capabilities
        ]

    def list_capabilities(self) -> frozenset[AgentCapability]:
        """Return every capability provided by registered agents."""

        capabilities: set[AgentCapability] = set()

        for agent in self._agents:
            capabilities.update(agent.capabilities)

        return frozenset(capabilities)
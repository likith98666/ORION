from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.agents.repository import AgentRepository


class InMemoryAgentRepository(AgentRepository):
    """In-memory implementation of the ORION agent repository."""

    def __init__(self) -> None:
        self._agents: dict[UUID, Agent] = {}

    def save(self, agent: Agent) -> None:
        """Save an agent."""
        self._agents[agent.id] = agent

    def get(self, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def delete(self, agent_id: UUID) -> None:
        """Delete an agent."""
        self._agents.pop(agent_id, None)

    def list_all(self) -> list[Agent]:
        """List all agents."""
        return list(self._agents.values())
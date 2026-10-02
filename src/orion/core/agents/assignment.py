from dataclasses import dataclass
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent


@dataclass(frozen=True)
class AgentAssignment:
    """Represents an agent assigned to a specific capability."""

    id: UUID
    agent_id: UUID
    capability: AgentCapability

    @classmethod
    def create(
        cls,
        agent: Agent,
        capability: AgentCapability,
    ) -> "AgentAssignment":
        """Create a validated agent assignment."""

        if capability not in agent.capabilities:
            raise ValueError(f"Agent '{agent.name}' does not have capability '{capability.value}'.")

        return cls(
            id=uuid4(),
            agent_id=agent.id,
            capability=capability,
        )

from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.agents.models import Agent


class AgentRepository(ABC):
    """Abstract repository for storing ORION agents."""

    @abstractmethod
    def save(self, agent: Agent) -> None:
        """Save an agent."""

    @abstractmethod
    def get(self, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""

    @abstractmethod
    def delete(self, agent_id: UUID) -> None:
        """Delete an agent."""

    @abstractmethod
    def list_all(self) -> list[Agent]:
        """List all agents."""
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import Agent
from orion.core.agents.registry import AgentRegistry


class AgentService:
    def __init__(
        self,
        registry: AgentRegistry,
        capability_registry: AgentCapabilityRegistry,
    ) -> None:
        self._registry = registry
        self._capability_registry = capability_registry

    def register_agent(self, agent: Agent) -> Agent:
        self._registry.register(agent)
        self._capability_registry.register(agent)
        return agent

    def get_agent(self, name: str) -> Agent | None:
        return self._registry.get(name)

    def find_agents_by_capability(
        self,
        capability: AgentCapability,
    ) -> list[Agent]:
        return self._capability_registry.find_by_capability(capability)

    def list_agent_names(self) -> list[str]:
        return self._registry.list_names()

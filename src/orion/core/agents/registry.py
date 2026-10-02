from orion.core.agents.models import Agent


class AgentRegistry:
    """Registry for managing ORION agents."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent."""

        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered.")

        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        """Retrieve an agent by name."""

        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError("Agent name cannot be empty.")

        if cleaned_name not in self._agents:
            raise KeyError(f"Agent '{cleaned_name}' is not registered.")

        return self._agents[cleaned_name]

    def list_names(self) -> list[str]:
        """Return the names of all registered agents."""

        return list(self._agents.keys())

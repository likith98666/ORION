import pytest

from orion.core.agents.models import Agent
from orion.core.agents.registry import AgentRegistry


def create_test_agent(
    name: str = "Researcher",
) -> Agent:
    return Agent.create(
        name=name,
        description="Researches information and gathers evidence.",
        capabilities=frozenset({"research", "web_search"}),
    )


def test_registry_starts_empty() -> None:
    registry = AgentRegistry()

    assert registry.list_names() == []


def test_registry_can_register_agent() -> None:
    registry = AgentRegistry()
    agent = create_test_agent()

    registry.register(agent)

    assert registry.get("Researcher") == agent


def test_registry_can_get_agent() -> None:
    registry = AgentRegistry()
    agent = create_test_agent()

    registry.register(agent)

    result = registry.get("Researcher")

    assert result is agent


def test_registry_get_trims_name() -> None:
    registry = AgentRegistry()
    agent = create_test_agent()

    registry.register(agent)

    result = registry.get("   Researcher   ")

    assert result is agent


def test_registry_rejects_empty_name() -> None:
    registry = AgentRegistry()

    with pytest.raises(
        ValueError,
        match="Agent name cannot be empty",
    ):
        registry.get("   ")


def test_registry_rejects_unknown_agent() -> None:
    registry = AgentRegistry()

    with pytest.raises(
        KeyError,
        match="Agent 'Unknown' is not registered",
    ):
        registry.get("Unknown")


def test_registry_rejects_duplicate_agent() -> None:
    registry = AgentRegistry()

    first_agent = create_test_agent("Researcher")
    second_agent = create_test_agent("Researcher")

    registry.register(first_agent)

    with pytest.raises(
        ValueError,
        match="Agent 'Researcher' is already registered",
    ):
        registry.register(second_agent)


def test_registry_can_list_agent_names() -> None:
    registry = AgentRegistry()

    researcher = create_test_agent("Researcher")
    analyst = create_test_agent("Analyst")
    writer = create_test_agent("Writer")

    registry.register(researcher)
    registry.register(analyst)
    registry.register(writer)

    assert registry.list_names() == [
        "Researcher",
        "Analyst",
        "Writer",
    ]
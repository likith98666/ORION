import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import Agent
from orion.core.agents.registry import AgentRegistry
from orion.core.agents.service import AgentService


def create_test_agent(
    name: str,
    capabilities: frozenset[AgentCapability],
) -> Agent:
    return Agent.create(
        name=name,
        description=f"{name} agent.",
        capabilities=capabilities,
    )


def create_service() -> AgentService:
    return AgentService(
        registry=AgentRegistry(),
        capability_registry=AgentCapabilityRegistry(),
    )


def test_service_can_register_agent() -> None:
    service = create_service()

    agent = create_test_agent(
        "Researcher",
        frozenset(
            {
                AgentCapability.RESEARCH,
                AgentCapability.WEB_SEARCH,
            }
        ),
    )

    service.register_agent(agent)

    assert service.get_agent("Researcher") is agent


def test_service_can_find_agents_by_capability() -> None:
    service = create_service()

    researcher = create_test_agent(
        "Researcher",
        frozenset(
            {
                AgentCapability.RESEARCH,
                AgentCapability.WEB_SEARCH,
            }
        ),
    )

    analyst = create_test_agent(
        "Analyst",
        frozenset(
            {
                AgentCapability.RESEARCH,
                AgentCapability.DATA_ANALYSIS,
            }
        ),
    )

    service.register_agent(researcher)
    service.register_agent(analyst)

    result = service.find_agents_by_capability(AgentCapability.RESEARCH)

    assert result == [researcher, analyst]


def test_service_returns_empty_for_unused_capability() -> None:
    service = create_service()

    agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    service.register_agent(agent)

    result = service.find_agents_by_capability(AgentCapability.CODE_EXECUTION)

    assert result == []


def test_service_can_list_agent_names() -> None:
    service = create_service()

    researcher = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    analyst = create_test_agent(
        "Analyst",
        frozenset({AgentCapability.DATA_ANALYSIS}),
    )

    service.register_agent(researcher)
    service.register_agent(analyst)

    assert service.list_agent_names() == [
        "Researcher",
        "Analyst",
    ]


def test_service_can_retrieve_agent_with_trimmed_name() -> None:
    service = create_service()

    agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    service.register_agent(agent)

    assert service.get_agent("   Researcher   ") is agent


def test_service_rejects_duplicate_agent() -> None:
    service = create_service()

    first_agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    second_agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.WEB_SEARCH}),
    )

    service.register_agent(first_agent)

    with pytest.raises(
        ValueError,
        match="Agent 'Researcher' is already registered",
    ):
        service.register_agent(second_agent)

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import Agent


def create_test_agent(
    name: str,
    capabilities: frozenset[AgentCapability],
) -> Agent:
    return Agent.create(
        name=name,
        description=f"{name} agent.",
        capabilities=capabilities,
    )


def test_registry_starts_empty() -> None:
    registry = AgentCapabilityRegistry()

    assert registry.list_capabilities() == frozenset()


def test_registry_can_register_agent() -> None:
    registry = AgentCapabilityRegistry()
    agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(agent)

    assert registry.find_by_capability(
        AgentCapability.RESEARCH
    ) == [agent]


def test_registry_finds_multiple_agents_with_same_capability() -> None:
    registry = AgentCapabilityRegistry()

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

    registry.register(researcher)
    registry.register(analyst)

    result = registry.find_by_capability(
        AgentCapability.RESEARCH
    )

    assert result == [researcher, analyst]


def test_registry_returns_empty_for_unused_capability() -> None:
    registry = AgentCapabilityRegistry()

    agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(agent)

    assert registry.find_by_capability(
        AgentCapability.CODE_EXECUTION
    ) == []


def test_registry_lists_all_capabilities() -> None:
    registry = AgentCapabilityRegistry()

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
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.RESEARCH,
            }
        ),
    )

    registry.register(researcher)
    registry.register(analyst)

    assert registry.list_capabilities() == frozenset(
        {
            AgentCapability.RESEARCH,
            AgentCapability.WEB_SEARCH,
            AgentCapability.DATA_ANALYSIS,
        }
    )


def test_registry_rejects_duplicate_agent() -> None:
    registry = AgentCapabilityRegistry()

    agent = create_test_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(agent)

    try:
        registry.register(agent)
    except ValueError as exc:
        assert str(exc) == "Agent 'Researcher' is already registered."
    else:
        raise AssertionError("Duplicate agent should be rejected.")
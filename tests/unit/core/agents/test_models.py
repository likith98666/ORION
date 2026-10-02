import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent, AgentStatus


def test_agent_can_be_created() -> None:
    agent = Agent.create(
        name="Researcher",
        description="Researches information and gathers evidence.",
        capabilities=frozenset(
            {
                AgentCapability.WEB_SEARCH,
                AgentCapability.RESEARCH,
            }
        ),
    )

    assert agent.name == "Researcher"
    assert agent.description == "Researches information and gathers evidence."
    assert agent.capabilities == frozenset(
        {
            AgentCapability.WEB_SEARCH,
            AgentCapability.RESEARCH,
        }
    )
    assert agent.status == AgentStatus.ACTIVE
    assert agent.id is not None
    assert agent.created_at is not None


def test_agent_name_is_trimmed() -> None:
    agent = Agent.create(
        name="   Researcher   ",
        description="Researches information.",
        capabilities=frozenset({AgentCapability.RESEARCH}),
    )

    assert agent.name == "Researcher"


def test_agent_description_is_trimmed() -> None:
    agent = Agent.create(
        name="Researcher",
        description="   Researches information.   ",
        capabilities=frozenset({AgentCapability.RESEARCH}),
    )

    assert agent.description == "Researches information."


def test_agent_rejects_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="Agent name cannot be empty",
    ):
        Agent.create(
            name="",
            description="Researches information.",
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_whitespace_name() -> None:
    with pytest.raises(
        ValueError,
        match="Agent name cannot be empty",
    ):
        Agent.create(
            name="   ",
            description="Researches information.",
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_name_over_200_characters() -> None:
    with pytest.raises(
        ValueError,
        match="Agent name cannot exceed 200 characters",
    ):
        Agent.create(
            name="x" * 201,
            description="Researches information.",
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_empty_description() -> None:
    with pytest.raises(
        ValueError,
        match="Agent description cannot be empty",
    ):
        Agent.create(
            name="Researcher",
            description="",
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_whitespace_description() -> None:
    with pytest.raises(
        ValueError,
        match="Agent description cannot be empty",
    ):
        Agent.create(
            name="Researcher",
            description="   ",
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_description_over_2000_characters() -> None:
    with pytest.raises(
        ValueError,
        match="Agent description cannot exceed 2,000 characters",
    ):
        Agent.create(
            name="Researcher",
            description="x" * 2_001,
            capabilities=frozenset({AgentCapability.RESEARCH}),
        )


def test_agent_rejects_empty_capabilities() -> None:
    with pytest.raises(
        ValueError,
        match="Agent must have at least one capability",
    ):
        Agent.create(
            name="Researcher",
            description="Researches information.",
            capabilities=frozenset(),
        )


def test_agent_capabilities_are_preserved() -> None:
    agent = Agent.create(
        name="Researcher",
        description="Researches information.",
        capabilities=frozenset(
            {
                AgentCapability.WEB_SEARCH,
                AgentCapability.RESEARCH,
            }
        ),
    )

    assert agent.capabilities == frozenset(
        {
            AgentCapability.WEB_SEARCH,
            AgentCapability.RESEARCH,
        }
    )

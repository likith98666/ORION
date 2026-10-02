import pytest

from orion.core.agents.assignment import AgentAssignment
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent


def create_test_agent() -> Agent:
    return Agent.create(
        name="Researcher",
        description="Researches information and gathers evidence.",
        capabilities=frozenset(
            {
                AgentCapability.RESEARCH,
                AgentCapability.WEB_SEARCH,
            }
        ),
    )


def test_assignment_can_be_created() -> None:
    agent = create_test_agent()

    assignment = AgentAssignment.create(
        agent=agent,
        capability=AgentCapability.RESEARCH,
    )

    assert assignment.id is not None
    assert assignment.agent_id == agent.id
    assert assignment.capability == AgentCapability.RESEARCH


def test_assignment_rejects_unsupported_capability() -> None:
    agent = create_test_agent()

    with pytest.raises(
        ValueError,
        match="Agent 'Researcher' does not have capability 'data_analysis'",
    ):
        AgentAssignment.create(
            agent=agent,
            capability=AgentCapability.DATA_ANALYSIS,
        )


def test_assignment_is_immutable() -> None:
    agent = create_test_agent()

    assignment = AgentAssignment.create(
        agent=agent,
        capability=AgentCapability.RESEARCH,
    )

    with pytest.raises(AttributeError):
        assignment.capability = AgentCapability.WEB_SEARCH  # type: ignore[misc]

from uuid import uuid4

from orion.core.agents.memory_repository import InMemoryAgentRepository
from orion.core.agents.models import Agent


def create_test_agent(
    name: str = "Researcher",
) -> Agent:
    return Agent.create(
        name=name,
        description="Researches information and gathers evidence.",
        capabilities=frozenset({"research", "web_search"}),
    )


def test_repository_starts_empty() -> None:
    repository = InMemoryAgentRepository()

    assert repository.list_all() == []


def test_repository_can_save_agent() -> None:
    repository = InMemoryAgentRepository()
    agent = create_test_agent()

    repository.save(agent)

    assert repository.get(agent.id) == agent


def test_repository_can_get_missing_agent() -> None:
    repository = InMemoryAgentRepository()

    result = repository.get(uuid4())

    assert result is None


def test_repository_can_delete_agent() -> None:
    repository = InMemoryAgentRepository()
    agent = create_test_agent()

    repository.save(agent)
    repository.delete(agent.id)

    assert repository.get(agent.id) is None


def test_repository_delete_missing_agent_does_nothing() -> None:
    repository = InMemoryAgentRepository()

    repository.delete(uuid4())

    assert repository.list_all() == []


def test_repository_can_list_all_agents() -> None:
    repository = InMemoryAgentRepository()

    first_agent = create_test_agent("Researcher")
    second_agent = create_test_agent("Analyst")

    repository.save(first_agent)
    repository.save(second_agent)

    agents = repository.list_all()

    assert agents == [first_agent, second_agent]


def test_repository_save_updates_existing_agent() -> None:
    repository = InMemoryAgentRepository()
    agent = create_test_agent()

    repository.save(agent)

    agent.description = "Updated research specialist."
    repository.save(agent)

    assert repository.get(agent.id) == agent
    assert len(repository.list_all()) == 1

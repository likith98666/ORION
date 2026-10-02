from abc import ABC

from orion.core.agents.repository import AgentRepository


def test_agent_repository_is_abstract() -> None:
    assert issubclass(AgentRepository, ABC)


def test_agent_repository_cannot_be_instantiated() -> None:
    try:
        AgentRepository()
    except TypeError:
        pass
    else:
        raise AssertionError("AgentRepository should be abstract.")

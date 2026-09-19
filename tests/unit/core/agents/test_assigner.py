import pytest

from orion.core.agents.assigner import AgentAssigner
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.models import Agent, AgentStatus
from orion.core.agents.tasks import AgentTask


def create_agent(
    name: str,
    capabilities: frozenset[AgentCapability],
) -> Agent:
    return Agent.create(
        name=name,
        description=f"{name} agent.",
        capabilities=capabilities,
    )


def create_task(
    capability: AgentCapability,
) -> AgentTask:
    from uuid import uuid4

    return AgentTask.create(
        task_id=uuid4(),
        description="Execute this agent task.",
        required_capability=capability,
    )


def test_assigner_assigns_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    researcher = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    registry.register(researcher)

    assignment = AgentAssigner(registry).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == researcher.id
    assert assignment.capability == AgentCapability.RESEARCH


def test_assigner_selects_first_active_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    first = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    second = create_agent(
        "Senior Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(first)
    registry.register(second)

    assignment = AgentAssigner(registry).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == first.id


def test_assigner_skips_inactive_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    inactive = create_agent(
        "Inactive Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    inactive.status = AgentStatus.INACTIVE

    active = create_agent(
        "Active Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(inactive)
    registry.register(active)

    assignment = AgentAssigner(registry).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == active.id


def test_assigner_skips_disabled_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    disabled = create_agent(
        "Disabled Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    disabled.status = AgentStatus.DISABLED

    active = create_agent(
        "Active Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(disabled)
    registry.register(active)

    assignment = AgentAssigner(registry).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == active.id


def test_assigner_ignores_agents_without_required_capability() -> None:
    registry = AgentCapabilityRegistry()
    analyst = create_agent(
        "Analyst",
        frozenset({AgentCapability.DATA_ANALYSIS}),
    )
    researcher = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    registry.register(analyst)
    registry.register(researcher)

    assignment = AgentAssigner(registry).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == researcher.id


def test_assigner_rejects_task_without_active_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    inactive = create_agent(
        "Inactive Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    inactive.status = AgentStatus.INACTIVE

    registry.register(inactive)

    with pytest.raises(
        ValueError,
        match="No active agent available with capability 'research'",
    ):
        AgentAssigner(registry).assign(
            create_task(AgentCapability.RESEARCH)
        )


def test_assigner_rejects_task_without_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    analyst = create_agent(
        "Analyst",
        frozenset({AgentCapability.DATA_ANALYSIS}),
    )

    registry.register(analyst)

    with pytest.raises(
        ValueError,
        match="No agent available with capability 'research'",
    ):
        AgentAssigner(registry).assign(
            create_task(AgentCapability.RESEARCH)
        )

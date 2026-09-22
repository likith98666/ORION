from uuid import uuid4

import pytest

from orion.core.agents.assigner import AgentAssigner
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.memory_task_repository import (
    InMemoryAgentTaskRepository,
)
from orion.core.agents.models import Agent, AgentStatus
from orion.core.agents.permissions import AgentPermission
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


def create_agent(
    name: str,
    capabilities: frozenset[AgentCapability],
    permissions: frozenset[AgentPermission] | None = None,
) -> Agent:
    from orion.core.agents.permission_policy import AgentPermissionPolicy

    return Agent.create(
        name=name,
        description=f"{name} agent.",
        capabilities=capabilities,
        permission_policy=AgentPermissionPolicy.create(
            permissions or frozenset()
        ),
    )


def create_task(
    capability: AgentCapability,
    required_permissions: frozenset[AgentPermission] | None = None,
) -> AgentTask:
    return AgentTask.create(
        task_id=uuid4(),
        description="Execute this agent task.",
        required_capability=capability,
        required_permissions=required_permissions,
    )


def create_assigner(
    registry: AgentCapabilityRegistry,
    repository: InMemoryAgentTaskRepository,
) -> AgentAssigner:
    return AgentAssigner(
        capability_registry=registry,
        task_repository=repository,
    )


def test_assigner_assigns_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    researcher = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    registry.register(researcher)

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == researcher.id
    assert assignment.capability == AgentCapability.RESEARCH


def test_assigner_selects_first_active_capable_agent_when_load_is_equal() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == first.id


def test_assigner_selects_least_loaded_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    busy_task = create_task(AgentCapability.RESEARCH)
    busy_task.assigned_agent_id = first.id
    busy_task.status = AgentTaskStatus.RUNNING
    repository.save(busy_task)

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == second.id


def test_assigner_counts_assigned_tasks_as_load() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    assigned_task = create_task(AgentCapability.RESEARCH)
    assigned_task.assigned_agent_id = first.id
    assigned_task.status = AgentTaskStatus.ASSIGNED
    repository.save(assigned_task)

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == second.id


def test_assigner_ignores_completed_tasks_when_calculating_load() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    completed_task = create_task(AgentCapability.RESEARCH)
    completed_task.assigned_agent_id = first.id
    completed_task.status = AgentTaskStatus.COMPLETED
    repository.save(completed_task)

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == first.id


def test_assigner_skips_inactive_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == active.id


def test_assigner_skips_disabled_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == active.id


def test_assigner_ignores_agents_without_required_capability() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == researcher.id


def test_assigner_allows_task_without_required_permissions() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    researcher = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    registry.register(researcher)

    assignment = create_assigner(registry, repository).assign(
        create_task(AgentCapability.RESEARCH)
    )

    assert assignment.agent_id == researcher.id


def test_assigner_selects_agent_with_required_permission() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    restricted = create_agent(
        "Restricted Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    authorized = create_agent(
        "Authorized Researcher",
        frozenset({AgentCapability.RESEARCH}),
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    registry.register(restricted)
    registry.register(authorized)

    assignment = create_assigner(registry, repository).assign(
        create_task(
            AgentCapability.RESEARCH,
            frozenset({AgentPermission.WEB_ACCESS}),
        )
    )

    assert assignment.agent_id == authorized.id


def test_assigner_skips_agent_missing_required_permission() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    unauthorized = create_agent(
        "Unauthorized Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    authorized = create_agent(
        "Authorized Researcher",
        frozenset({AgentCapability.RESEARCH}),
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    registry.register(unauthorized)
    registry.register(authorized)

    assignment = create_assigner(registry, repository).assign(
        create_task(
            AgentCapability.RESEARCH,
            frozenset({AgentPermission.WEB_ACCESS}),
        )
    )

    assert assignment.agent_id == authorized.id


def test_assigner_requires_all_required_permissions() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    partial = create_agent(
        "Partial Researcher",
        frozenset({AgentCapability.RESEARCH}),
        frozenset({AgentPermission.WEB_ACCESS}),
    )
    authorized = create_agent(
        "Authorized Researcher",
        frozenset({AgentCapability.RESEARCH}),
        frozenset(
            {
                AgentPermission.WEB_ACCESS,
                AgentPermission.READ_FILES,
            }
        ),
    )

    registry.register(partial)
    registry.register(authorized)

    assignment = create_assigner(registry, repository).assign(
        create_task(
            AgentCapability.RESEARCH,
            frozenset(
                {
                    AgentPermission.WEB_ACCESS,
                    AgentPermission.READ_FILES,
                }
            ),
        )
    )

    assert assignment.agent_id == authorized.id


def test_assigner_rejects_task_without_authorized_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    unauthorized = create_agent(
        "Unauthorized Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )
    registry.register(unauthorized)

    with pytest.raises(
        ValueError,
        match="No active agent available with capability 'research'",
    ):
        create_assigner(registry, repository).assign(
            create_task(
                AgentCapability.RESEARCH,
                frozenset({AgentPermission.WEB_ACCESS}),
            )
        )


def test_assigner_rejects_task_without_active_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

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
        create_assigner(registry, repository).assign(
            create_task(AgentCapability.RESEARCH)
        )


def test_assigner_rejects_task_without_capable_agent() -> None:
    registry = AgentCapabilityRegistry()
    repository = InMemoryAgentTaskRepository()

    analyst = create_agent(
        "Analyst",
        frozenset({AgentCapability.DATA_ANALYSIS}),
    )

    registry.register(analyst)

    with pytest.raises(
        ValueError,
        match="No agent available with capability 'research'",
    ):
        create_assigner(registry, repository).assign(
            create_task(AgentCapability.RESEARCH)
        )

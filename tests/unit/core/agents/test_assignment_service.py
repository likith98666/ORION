from uuid import uuid4

import pytest

from orion.core.agents.assignment_service import AgentAssignmentService
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.capability_registry import AgentCapabilityRegistry
from orion.core.agents.memory_task_repository import (
    InMemoryAgentTaskRepository,
)
from orion.core.agents.models import Agent
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


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
    return AgentTask.create(
        task_id=uuid4(),
        description="Execute this task.",
        required_capability=capability,
    )


def create_service(
    agent: Agent,
) -> tuple[AgentAssignmentService, InMemoryAgentTaskRepository]:
    repository = InMemoryAgentTaskRepository()
    capability_registry = AgentCapabilityRegistry()
    capability_registry.register(agent)

    service = AgentAssignmentService(
        task_repository=repository,
        capability_registry=capability_registry,
    )

    return service, repository


def test_assignment_service_assigns_agent() -> None:
    agent = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    service, repository = create_service(agent)
    task = create_task(AgentCapability.RESEARCH)

    result = service.assign_task(task)

    assert result.status == AgentTaskStatus.ASSIGNED
    assert result.assigned_agent_id == agent.id
    assert repository.get(task.id) is task


def test_assignment_service_persists_assignment() -> None:
    agent = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    service, repository = create_service(agent)
    task = create_task(AgentCapability.RESEARCH)

    service.assign_task(task)

    stored_task = repository.get(task.id)

    assert stored_task is not None
    assert stored_task.status == AgentTaskStatus.ASSIGNED
    assert stored_task.assigned_agent_id == agent.id


def test_assignment_service_rejects_non_pending_task() -> None:
    agent = create_agent(
        "Researcher",
        frozenset({AgentCapability.RESEARCH}),
    )

    service, _ = create_service(agent)
    task = create_task(AgentCapability.RESEARCH)

    task.status = AgentTaskStatus.RUNNING

    with pytest.raises(
        ValueError,
        match="Only pending tasks can be assigned",
    ):
        service.assign_task(task)


def test_assignment_service_rejects_missing_capable_agent() -> None:
    agent = create_agent(
        "Analyst",
        frozenset({AgentCapability.DATA_ANALYSIS}),
    )

    service, _ = create_service(agent)
    task = create_task(AgentCapability.RESEARCH)

    with pytest.raises(
        ValueError,
        match="No agent available with capability 'research'",
    ):
        service.assign_task(task)
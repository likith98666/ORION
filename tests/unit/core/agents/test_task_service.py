from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.memory_task_repository import (
    InMemoryAgentTaskRepository,
)
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTaskStatus


def create_service() -> AgentTaskService:
    return AgentTaskService(
        repository=InMemoryAgentTaskRepository(),
    )


def test_service_can_create_task() -> None:
    service = create_service()
    parent_task_id = uuid4()

    task = service.create_task(
        task_id=parent_task_id,
        description="Research AI companies.",
        required_capability=AgentCapability.RESEARCH,
    )

    assert task.task_id == parent_task_id
    assert task.plan_step_id is None
    assert task.description == "Research AI companies."
    assert task.required_capability == AgentCapability.RESEARCH
    assert task.status == AgentTaskStatus.PENDING


def test_service_can_create_task_for_plan_step() -> None:
    service = create_service()
    parent_task_id = uuid4()
    plan_step_id = uuid4()

    task = service.create_task(
        task_id=parent_task_id,
        plan_step_id=plan_step_id,
        description="Research AI companies.",
        required_capability=AgentCapability.RESEARCH,
    )

    assert task.task_id == parent_task_id
    assert task.plan_step_id == plan_step_id


def test_service_can_get_task() -> None:
    service = create_service()

    task = service.create_task(
        task_id=uuid4(),
        description="Analyze market data.",
        required_capability=AgentCapability.DATA_ANALYSIS,
    )

    result = service.get_task(task.id)

    assert result is task


def test_service_returns_none_for_unknown_task() -> None:
    service = create_service()

    assert service.get_task(uuid4()) is None


def test_service_can_update_task_status() -> None:
    service = create_service()

    task = service.create_task(
        task_id=uuid4(),
        description="Research competitors.",
        required_capability=AgentCapability.RESEARCH,
    )

    result = service.update_status(
        task.id,
        AgentTaskStatus.ASSIGNED,
    )

    assert result.status == AgentTaskStatus.ASSIGNED
    assert service.get_task(task.id) is result


def test_service_rejects_invalid_status_transition() -> None:
    service = create_service()

    task = service.create_task(
        task_id=uuid4(),
        description="Research competitors.",
        required_capability=AgentCapability.RESEARCH,
    )

    with pytest.raises(
        ValueError,
        match="Invalid agent task transition: pending -> running",
    ):
        service.update_status(
            task.id,
            AgentTaskStatus.RUNNING,
        )


def test_service_rejects_unknown_task_status_update() -> None:
    service = create_service()

    with pytest.raises(
        ValueError,
        match="Agent task not found",
    ):
        service.update_status(
            uuid4(),
            AgentTaskStatus.ASSIGNED,
        )


def test_service_can_list_tasks_for_parent_task() -> None:
    service = create_service()
    parent_task_id = uuid4()

    first = service.create_task(
        task_id=parent_task_id,
        description="Research competitors.",
        required_capability=AgentCapability.RESEARCH,
    )

    second = service.create_task(
        task_id=parent_task_id,
        description="Analyze competitors.",
        required_capability=AgentCapability.DATA_ANALYSIS,
    )

    result = service.list_for_task(parent_task_id)

    assert result == [first, second]


def test_service_does_not_list_tasks_from_another_parent() -> None:
    service = create_service()

    parent_task_id = uuid4()

    task = service.create_task(
        task_id=parent_task_id,
        description="Research competitors.",
        required_capability=AgentCapability.RESEARCH,
    )

    result = service.list_for_task(uuid4())

    assert result == []
    assert service.get_task(task.id) is task

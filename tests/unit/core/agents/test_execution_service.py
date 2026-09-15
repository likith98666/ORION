from uuid import uuid4

import pytest

from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.executions import AgentExecutionStatus


def create_service() -> AgentExecutionService:
    return AgentExecutionService(
        InMemoryAgentExecutionRepository()
    )


def test_create_execution_persists_execution():
    service = create_service()
    agent_task_id = uuid4()
    agent_id = uuid4()

    execution = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=agent_id,
    )

    assert execution.agent_task_id == agent_task_id
    assert execution.agent_id == agent_id
    assert execution.status == AgentExecutionStatus.RUNNING
    assert service.get_execution(execution.id) == execution


def test_get_missing_execution_returns_none():
    service = create_service()

    assert service.get_execution(uuid4()) is None


def test_update_status_persists_execution():
    service = create_service()

    execution = service.create_execution(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    updated = service.update_status(
        execution.id,
        AgentExecutionStatus.COMPLETED,
    )

    assert updated.status == AgentExecutionStatus.COMPLETED
    assert service.get_execution(execution.id).status == (
        AgentExecutionStatus.COMPLETED
    )


def test_update_missing_execution_raises_error():
    service = create_service()

    with pytest.raises(ValueError, match="not found"):
        service.update_status(
            uuid4(),
            AgentExecutionStatus.COMPLETED,
        )


def test_list_executions_for_agent_task():
    service = create_service()
    agent_task_id = uuid4()

    first = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=uuid4(),
    )
    second = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=uuid4(),
    )
    service.create_execution(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    executions = service.list_for_agent_task(agent_task_id)

    assert executions == [first, second]

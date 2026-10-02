from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)


def test_create_execution() -> None:
    agent_task_id = uuid4()
    agent_id = uuid4()

    execution = AgentExecution.create(
        agent_task_id=agent_task_id,
        agent_id=agent_id,
    )

    assert execution.id is not None
    assert execution.agent_task_id == agent_task_id
    assert execution.agent_id == agent_id
    assert execution.status == AgentExecutionStatus.RUNNING
    assert execution.started_at is not None
    assert execution.completed_at is None
    assert execution.output is None
    assert execution.error_message is None


def test_each_execution_gets_a_unique_id() -> None:
    agent_task_id = uuid4()
    agent_id = uuid4()

    first = AgentExecution.create(agent_task_id, agent_id)
    second = AgentExecution.create(agent_task_id, agent_id)

    assert first.id != second.id


def test_each_execution_gets_its_own_start_time() -> None:
    agent_task_id = uuid4()
    agent_id = uuid4()

    first = AgentExecution.create(agent_task_id, agent_id)
    second = AgentExecution.create(agent_task_id, agent_id)

    assert first.started_at is not second.started_at


def test_agent_execution_creates_telemetry_context() -> None:
    task_id = uuid4()
    agent_id = uuid4()

    execution = AgentExecution.create(
        agent_task_id=task_id,
        agent_id=agent_id,
    )

    assert execution.telemetry_context is not None
    assert execution.telemetry_context.task_id == task_id
    assert execution.telemetry_context.execution_id == execution.id
    assert execution.telemetry_context.agent_id == agent_id


def test_agent_execution_telemetry_context_is_immutable() -> None:
    execution = AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )

    assert execution.telemetry_context is not None

    with pytest.raises(FrozenInstanceError):
        execution.telemetry_context.task_id = uuid4()  # type: ignore[misc]

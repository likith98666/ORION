from uuid import uuid4

import pytest

from orion.core.agents.execution_manager import AgentExecutionManager
from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)


def create_execution() -> AgentExecution:
    return AgentExecution.create(
        agent_task_id=uuid4(),
        agent_id=uuid4(),
    )


def test_running_execution_can_complete():
    manager = AgentExecutionManager()
    execution = create_execution()

    updated = manager.update_status(
        execution,
        AgentExecutionStatus.COMPLETED,
    )

    assert updated.status == AgentExecutionStatus.COMPLETED


def test_running_execution_can_fail():
    manager = AgentExecutionManager()
    execution = create_execution()

    updated = manager.update_status(
        execution,
        AgentExecutionStatus.FAILED,
    )

    assert updated.status == AgentExecutionStatus.FAILED


def test_running_execution_can_be_cancelled():
    manager = AgentExecutionManager()
    execution = create_execution()

    updated = manager.update_status(
        execution,
        AgentExecutionStatus.CANCELLED,
    )

    assert updated.status == AgentExecutionStatus.CANCELLED


@pytest.mark.parametrize(
    "status",
    [
        AgentExecutionStatus.RUNNING,
        AgentExecutionStatus.COMPLETED,
        AgentExecutionStatus.FAILED,
        AgentExecutionStatus.CANCELLED,
    ],
)
def test_terminal_execution_cannot_transition(
    status: AgentExecutionStatus,
):
    manager = AgentExecutionManager()

    for terminal_status in (
        AgentExecutionStatus.COMPLETED,
        AgentExecutionStatus.FAILED,
        AgentExecutionStatus.CANCELLED,
    ):
        execution = create_execution()
        execution.status = terminal_status

        with pytest.raises(ValueError):
            manager.update_status(execution, status)

from uuid import uuid4

from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)


def test_create_execution():
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


def test_each_execution_gets_a_unique_id():
    agent_task_id = uuid4()
    agent_id = uuid4()

    first = AgentExecution.create(agent_task_id, agent_id)
    second = AgentExecution.create(agent_task_id, agent_id)

    assert first.id != second.id


def test_each_execution_gets_its_own_start_time():
    agent_task_id = uuid4()
    agent_id = uuid4()

    first = AgentExecution.create(agent_task_id, agent_id)
    second = AgentExecution.create(agent_task_id, agent_id)

    assert first.started_at is not second.started_at

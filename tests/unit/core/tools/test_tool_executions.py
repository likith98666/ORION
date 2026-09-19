from uuid import uuid4

from orion.core.tools.execution_repository_memory import (
    InMemoryToolExecutionRepository,
)
from orion.core.tools.executions import (
    ToolExecution,
    ToolExecutionStatus,
)


def test_tool_execution_starts_pending():
    agent_id = uuid4()

    execution = ToolExecution.create(
        tool_name="echo",
        agent_id=agent_id,
        arguments={"value": "hello"},
    )

    assert execution.status == ToolExecutionStatus.PENDING
    assert execution.tool_name == "echo"
    assert execution.agent_id == agent_id
    assert execution.arguments == {"value": "hello"}
    assert execution.output is None
    assert execution.error is None


def test_tool_execution_preserves_agent_execution_link():
    agent_id = uuid4()
    execution_id = uuid4()

    execution = ToolExecution.create(
        tool_name="echo",
        agent_id=agent_id,
        arguments={"value": "hello"},
        execution_id=execution_id,
    )

    assert execution.execution_id == execution_id


def test_tool_execution_repository_persists_lifecycle_record():
    repository = InMemoryToolExecutionRepository()
    agent_id = uuid4()

    execution = ToolExecution.create(
        tool_name="echo",
        agent_id=agent_id,
        arguments={"value": "hello"},
    )

    repository.save(execution)

    stored = repository.get(execution.id)

    assert stored is execution
    assert repository.list_for_agent(agent_id) == [execution]


def test_tool_execution_repository_isolates_agents():
    repository = InMemoryToolExecutionRepository()

    first_agent = uuid4()
    second_agent = uuid4()

    first_execution = ToolExecution.create(
        tool_name="echo",
        agent_id=first_agent,
        arguments={},
    )
    second_execution = ToolExecution.create(
        tool_name="echo",
        agent_id=second_agent,
        arguments={},
    )

    repository.save(first_execution)
    repository.save(second_execution)

    assert repository.list_for_agent(first_agent) == [first_execution]
    assert repository.list_for_agent(second_agent) == [second_execution]


def test_tool_execution_can_transition_to_completed():
    execution = ToolExecution.create(
        tool_name="echo",
        agent_id=uuid4(),
        arguments={},
    )

    execution.status = ToolExecutionStatus.RUNNING
    execution.output = "hello"
    execution.status = ToolExecutionStatus.COMPLETED

    assert execution.status == ToolExecutionStatus.COMPLETED
    assert execution.output == "hello"


def test_tool_execution_can_transition_to_failed():
    execution = ToolExecution.create(
        tool_name="echo",
        agent_id=uuid4(),
        arguments={},
    )

    execution.status = ToolExecutionStatus.RUNNING
    execution.error = "tool failed"
    execution.status = ToolExecutionStatus.FAILED

    assert execution.status == ToolExecutionStatus.FAILED
    assert execution.error == "tool failed"

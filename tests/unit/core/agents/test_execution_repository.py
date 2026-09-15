from uuid import uuid4

from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.executions import AgentExecution


def test_save_and_get_execution():
    repository = InMemoryAgentExecutionRepository()
    execution = AgentExecution.create(uuid4(), uuid4())

    repository.save(execution)

    assert repository.get(execution.id) == execution


def test_get_missing_execution_returns_none():
    repository = InMemoryAgentExecutionRepository()

    assert repository.get(uuid4()) is None


def test_delete_execution():
    repository = InMemoryAgentExecutionRepository()
    execution = AgentExecution.create(uuid4(), uuid4())

    repository.save(execution)
    repository.delete(execution.id)

    assert repository.get(execution.id) is None


def test_list_executions_for_agent_task():
    repository = InMemoryAgentExecutionRepository()
    agent_task_id = uuid4()

    first = AgentExecution.create(agent_task_id, uuid4())
    second = AgentExecution.create(agent_task_id, uuid4())
    other = AgentExecution.create(uuid4(), uuid4())

    repository.save(first)
    repository.save(second)
    repository.save(other)

    executions = repository.list_for_agent_task(agent_task_id)

    assert executions == [first, second]

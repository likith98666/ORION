from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.execution_repository_memory import (
    InMemoryToolExecutionRepository,
)
from orion.core.tools.executions import ToolExecutionStatus
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def create_agent() -> Agent:
    return Agent.create(
        name="lifecycle-agent",
        description="Tool lifecycle test agent",
        capabilities=frozenset({AgentCapability.RESEARCH}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.READ_FILES})
        ),
    )


def create_registry(handler):
    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=handler,
        )
    )
    return registry


def test_tool_executor_persists_completed_lifecycle():
    agent = create_agent()
    repository = InMemoryToolExecutionRepository()

    executor = ToolExecutor(
        create_registry(lambda arguments: arguments["value"]),
        execution_repository=repository,
    )

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={"value": "hello"},
    )

    assert result.success is True
    assert result.execution_id is not None

    execution = repository.get(result.execution_id)

    assert execution is not None
    assert execution.status == ToolExecutionStatus.COMPLETED
    assert execution.output == "hello"
    assert execution.arguments == {"value": "hello"}
    assert execution.agent_id == agent.id


def test_tool_executor_persists_failed_lifecycle():
    agent = create_agent()
    repository = InMemoryToolExecutionRepository()

    def failing_tool(arguments):
        raise RuntimeError("boom")

    executor = ToolExecutor(
        create_registry(failing_tool),
        execution_repository=repository,
    )

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={},
    )

    assert result.success is False
    assert result.execution_id is not None
    assert result.error == "boom"

    execution = repository.get(result.execution_id)

    assert execution is not None
    assert execution.status == ToolExecutionStatus.FAILED
    assert execution.error == "boom"


def test_tool_executor_links_agent_execution():
    agent = create_agent()
    repository = InMemoryToolExecutionRepository()
    parent_execution_id = uuid4()

    executor = ToolExecutor(
        create_registry(lambda arguments: "ok"),
        execution_repository=repository,
    )

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={},
        execution_id=parent_execution_id,
    )

    assert result.execution_id is not None

    execution = repository.get(result.execution_id)

    assert execution is not None
    assert execution.execution_id == parent_execution_id


def test_tool_executor_preserves_existing_behavior_without_repository():
    agent = create_agent()

    executor = ToolExecutor(
        create_registry(lambda arguments: arguments["value"])
    )

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={"value": "hello"},
    )

    assert result.success is True
    assert result.output == "hello"
    assert result.execution_id is None


def test_tool_executor_failure_without_repository_does_not_crash():
    agent = create_agent()

    def failing_tool(arguments):
        raise ValueError("failing without repository")

    executor = ToolExecutor(create_registry(failing_tool))

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={},
    )

    assert result.success is False
    assert result.error == "failing without repository"
    assert result.execution_id is None

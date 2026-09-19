from uuid import uuid4

import pytest

from orion.core.agents.agent_executor import AgentExecutor
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permissions import AgentPermission
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.tasks import AgentTask
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


class FakeAgentRepository:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def get(self, agent_id):
        if agent_id == self._agent.id:
            return self._agent
        return None


def create_agent(
    permissions: frozenset[AgentPermission],
) -> Agent:
    return Agent.create(
        name="tool-agent",
        description="Agent used for tool integration tests",
        capabilities=frozenset({AgentCapability.RESEARCH}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def create_task(agent: Agent) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Use a tool",
        required_capability=AgentCapability.RESEARCH,
    )
    task.assigned_agent_id = agent.id
    return task


def create_executor(
    agent: Agent,
    tool_executor: ToolExecutor | None,
) -> AgentExecutor:
    return AgentExecutor(
        agent_repository=FakeAgentRepository(agent),
        execution_service=None,
        model_runtime=None,
        tool_executor=tool_executor,
    )


def test_agent_executor_delegates_authorized_tool_execution():
    agent = create_agent(frozenset({AgentPermission.READ_FILES}))

    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=lambda arguments: arguments["value"],
        )
    )

    executor = create_executor(
        agent,
        ToolExecutor(registry),
    )

    result = executor.execute_tool(
        task=create_task(agent),
        tool_name="echo",
        arguments={"value": "hello"},
    )

    assert result.success is True
    assert result.output == "hello"


def test_agent_executor_preserves_tool_permission_enforcement():
    agent = create_agent(frozenset())

    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=lambda arguments: arguments["value"],
        )
    )

    executor = create_executor(
        agent,
        ToolExecutor(registry),
    )

    with pytest.raises(PermissionError):
        executor.execute_tool(
            task=create_task(agent),
            tool_name="echo",
            arguments={"value": "hello"},
        )


def test_agent_executor_requires_tool_executor():
    agent = create_agent(frozenset())

    executor = create_executor(agent, None)

    with pytest.raises(ValueError, match="Tool executor is required"):
        executor.execute_tool(
            task=create_task(agent),
            tool_name="echo",
            arguments={},
        )


def test_agent_executor_rejects_unassigned_tool_task():
    agent = create_agent(frozenset({AgentPermission.READ_FILES}))

    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=lambda arguments: arguments["value"],
        )
    )

    task = AgentTask.create(
        task_id=uuid4(),
        description="Use a tool",
        required_capability=AgentCapability.RESEARCH,
    )

    executor = create_executor(
        agent,
        ToolExecutor(registry),
    )

    with pytest.raises(ValueError, match="has no assigned agent"):
        executor.execute_tool(
            task=task,
            tool_name="echo",
            arguments={"value": "hello"},
        )

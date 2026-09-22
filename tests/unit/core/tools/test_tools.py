import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent_with_permission(permission: AgentPermission) -> Agent:
    return Agent.create(
        name="Test Agent",
        description="Agent used for tool tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({permission}),
        ),
    )


def _tool(permission: AgentPermission = AgentPermission.WEB_ACCESS) -> ToolDefinition:
    return ToolDefinition(
        name="test_tool",
        description="Test tool.",
        permission=permission,
        handler=lambda arguments: arguments.get("value"),
    )


def test_register_and_get_tool() -> None:
    registry = InMemoryToolRegistry()
    tool = _tool()

    registry.register(tool)

    assert registry.get("test_tool") is tool


def test_duplicate_registration_rejected() -> None:
    registry = InMemoryToolRegistry()
    tool = _tool()

    registry.register(tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool)


def test_authorized_tool_execution() -> None:
    registry = InMemoryToolRegistry()
    tool = _tool()
    registry.register(tool)

    agent = _agent_with_permission(AgentPermission.WEB_ACCESS)

    result = ToolExecutor(registry).execute(
        agent=agent,
        tool_name="test_tool",
        arguments={"value": "hello"},
    )

    assert result.success is True
    assert result.output == "hello"


def test_unauthorized_tool_execution_rejected() -> None:
    registry = InMemoryToolRegistry()
    tool = _tool()
    registry.register(tool)

    agent = Agent.create(
        name="Unauthorized Agent",
        description="Agent without tool permission.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(frozenset()),
    )

    with pytest.raises(PermissionError, match="not authorized"):
        ToolExecutor(registry).execute(
            agent=agent,
            tool_name="test_tool",
            arguments={"value": "hello"},
        )


def test_missing_tool_rejected() -> None:
    registry = InMemoryToolRegistry()

    agent = _agent_with_permission(AgentPermission.WEB_ACCESS)

    with pytest.raises(ValueError, match="was not found"):
        ToolExecutor(registry).execute(
            agent=agent,
            tool_name="missing_tool",
            arguments={},
        )


def test_tool_execution_failure_is_structured() -> None:
    registry = InMemoryToolRegistry()

    failing_tool = ToolDefinition(
        name="failing_tool",
        description="Tool that always fails.",
        permission=AgentPermission.WEB_ACCESS,
        handler=lambda arguments: 1 / 0,
    )

    registry.register(failing_tool)

    agent = _agent_with_permission(AgentPermission.WEB_ACCESS)

    result = ToolExecutor(registry).execute(
        agent=agent,
        tool_name="failing_tool",
        arguments={},
    )

    assert result.success is False
    assert result.error

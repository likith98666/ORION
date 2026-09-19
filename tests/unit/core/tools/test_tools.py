from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permissions import AgentPermission
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def create_agent(
    permissions: frozenset[AgentPermission],
) -> Agent:
    return Agent.create(
        name="test-agent",
        description="Tool execution test agent",
        capabilities=frozenset({AgentCapability.RESEARCH}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def test_register_and_get_tool():
    registry = InMemoryToolRegistry()

    tool = ToolDefinition(
        name="echo",
        description="Echo input",
        permission=AgentPermission.READ_FILES,
        handler=lambda arguments: arguments["value"],
    )

    registry.register(tool)

    assert registry.get("echo") is tool
    assert registry.list_tools() == (tool,)


def test_duplicate_tool_registration_is_rejected():
    registry = InMemoryToolRegistry()

    tool = ToolDefinition(
        name="echo",
        description="Echo input",
        permission=AgentPermission.READ_FILES,
        handler=lambda arguments: arguments["value"],
    )

    registry.register(tool)

    try:
        registry.register(tool)
        assert False
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_authorized_agent_can_execute_tool():
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=lambda arguments: arguments["value"],
        )
    )

    executor = ToolExecutor(registry)
    agent = create_agent(frozenset({AgentPermission.READ_FILES}))

    result = executor.execute(
        agent=agent,
        tool_name="echo",
        arguments={"value": "hello"},
    )

    assert result.success is True
    assert result.output == "hello"
    assert result.error is None


def test_unauthorized_agent_cannot_execute_tool():
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo input",
            permission=AgentPermission.READ_FILES,
            handler=lambda arguments: arguments["value"],
        )
    )

    executor = ToolExecutor(registry)
    agent = create_agent(frozenset())

    try:
        executor.execute(
            agent=agent,
            tool_name="echo",
            arguments={"value": "hello"},
        )
        assert False
    except PermissionError as exc:
        assert "not authorized" in str(exc)


def test_missing_tool_is_rejected():
    registry = InMemoryToolRegistry()
    executor = ToolExecutor(registry)
    agent = create_agent(frozenset())

    try:
        executor.execute(
            agent=agent,
            tool_name="missing",
            arguments={},
        )
        assert False
    except ValueError as exc:
        assert "was not found" in str(exc)


def test_tool_failure_is_returned_as_structured_result():
    registry = InMemoryToolRegistry()

    def failing_tool(arguments):
        raise RuntimeError("tool failed")

    registry.register(
        ToolDefinition(
            name="failing",
            description="Always fails",
            permission=AgentPermission.READ_FILES,
            handler=failing_tool,
        )
    )

    executor = ToolExecutor(registry)
    agent = create_agent(frozenset({AgentPermission.READ_FILES}))

    result = executor.execute(
        agent=agent,
        tool_name="failing",
        arguments={},
    )

    assert result.success is False
    assert result.output is None
    assert result.error == "tool failed"

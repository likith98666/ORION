import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.input_validator import ToolInputValidationError
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent() -> Agent:
    return Agent.create(
        name="Boundary Agent",
        description="Agent for input-boundary tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WEB_ACCESS}),
        ),
    )


def _schema() -> ToolInputSchema:
    return ToolInputSchema(
        fields=(
            ToolInputField(
                name="query",
                input_type=ToolInputType.STRING,
                required=True,
                max_length=100,
            ),
            ToolInputField(
                name="limit",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
        ),
    )


def _registry(handler=lambda arguments: arguments["query"]) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="search",
            description="Search tool.",
            permission=AgentPermission.WEB_ACCESS,
            handler=handler,
            input_schema=_schema(),
        )
    )

    return registry


def test_valid_arguments_are_accepted() -> None:
    result = ToolExecutor(_registry()).execute(
        agent=_agent(),
        tool_name="search",
        arguments={"query": "ORION", "limit": 5},
    )

    assert result.success is True
    assert result.output == "ORION"


def test_missing_required_argument_is_rejected() -> None:
    with pytest.raises(
        ToolInputValidationError,
        match="Required tool argument 'query' is missing",
    ):
        ToolExecutor(_registry()).execute(
            agent=_agent(),
            tool_name="search",
            arguments={"limit": 5},
        )


def test_unknown_argument_is_rejected() -> None:
    with pytest.raises(
        ToolInputValidationError,
        match="Unknown tool argument field",
    ):
        ToolExecutor(_registry()).execute(
            agent=_agent(),
            tool_name="search",
            arguments={
                "query": "ORION",
                "unexpected": "payload",
            },
        )


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(
        ToolInputValidationError,
        match="must be of type 'integer'",
    ):
        ToolExecutor(_registry()).execute(
            agent=_agent(),
            tool_name="search",
            arguments={
                "query": "ORION",
                "limit": "five",
            },
        )


def test_string_length_is_bounded() -> None:
    with pytest.raises(
        ToolInputValidationError,
        match="maximum string length",
    ):
        ToolExecutor(_registry()).execute(
            agent=_agent(),
            tool_name="search",
            arguments={
                "query": "x" * 101,
            },
        )


def test_non_dictionary_arguments_are_rejected() -> None:
    with pytest.raises(
        ToolInputValidationError,
        match="must be a dictionary",
    ):
        ToolExecutor(_registry()).execute(
            agent=_agent(),
            tool_name="search",
            arguments=[],
        )


def test_nested_depth_is_bounded() -> None:
    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="payload",
                input_type=ToolInputType.DICT,
                required=True,
            ),
        ),
        max_depth=2,
    )

    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="nested",
            description="Nested input test.",
            permission=AgentPermission.WEB_ACCESS,
            handler=lambda arguments: arguments,
            input_schema=schema,
        )
    )

    payload = {"a": {"b": {"c": "too-deep"}}}

    with pytest.raises(
        ToolInputValidationError,
        match="maximum nesting depth",
    ):
        ToolExecutor(registry).execute(
            agent=_agent(),
            tool_name="nested",
            arguments={"payload": payload},
        )


def test_large_collections_are_rejected() -> None:
    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="items",
                input_type=ToolInputType.LIST,
                required=True,
                max_items=3,
            ),
        ),
    )

    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="collection",
            description="Collection input test.",
            permission=AgentPermission.WEB_ACCESS,
            handler=lambda arguments: arguments,
            input_schema=schema,
        )
    )

    with pytest.raises(
        ToolInputValidationError,
        match="maximum collection size",
    ):
        ToolExecutor(registry).execute(
            agent=_agent(),
            tool_name="collection",
            arguments={"items": [1, 2, 3, 4]},
        )


def test_validation_happens_before_authorization() -> None:
    registry = _registry()

    unauthorized = Agent.create(
        name="Unauthorized",
        description="Agent without permission.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(frozenset()),
    )

    with pytest.raises(
        ToolInputValidationError,
        match="Required tool argument",
    ):
        ToolExecutor(registry).execute(
            agent=unauthorized,
            tool_name="search",
            arguments={},
        )

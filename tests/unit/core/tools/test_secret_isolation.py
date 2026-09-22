import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import InMemorySecretProvider, SecretReference
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.execution_repository_memory import InMemoryToolExecutionRepository
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent() -> Agent:
    return Agent.create(
        name="Secret Agent",
        description="Agent for secret-isolation tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.EXTERNAL_API}),
        ),
    )


def _registry(handler) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="external_api",
            description="Secret-backed external API tool.",
            permission=AgentPermission.EXTERNAL_API,
            handler=handler,
            input_schema=ToolInputSchema(
                fields=(
                    ToolInputField(
                        name="api_token",
                        input_type=ToolInputType.SECRET_REFERENCE,
                        required=True,
                    ),
                    ToolInputField(
                        name="payload",
                        input_type=ToolInputType.STRING,
                        required=True,
                    ),
                ),
            ),
        )
    )

    return registry


def test_secret_reference_is_resolved_only_for_handler() -> None:
    received = {}

    def handler(arguments):
        received.update(arguments)
        return arguments["api_token"]

    registry = _registry(handler)
    provider = InMemorySecretProvider(
        {"github_token": "super-secret-value"}
    )

    result = ToolExecutor(
        registry,
        secret_provider=provider,
    ).execute(
        agent=_agent(),
        tool_name="external_api",
        arguments={
            "api_token": SecretReference("github_token"),
            "payload": "hello",
        },
    )

    assert result.success is True
    assert result.output == "super-secret-value"
    assert received["api_token"] == "super-secret-value"


def test_raw_secret_is_never_persisted_in_tool_arguments() -> None:
    repository = InMemoryToolExecutionRepository()
    provider = InMemorySecretProvider(
        {"github_token": "super-secret-value"}
    )

    ToolExecutor(
        _registry(lambda arguments: "ok"),
        execution_repository=repository,
        secret_provider=provider,
    ).execute(
        agent=_agent(),
        tool_name="external_api",
        arguments={
            "api_token": SecretReference("github_token"),
            "payload": "hello",
        },
    )

    execution = next(iter(repository._executions.values()))

    assert execution.arguments["api_token"] == SecretReference(
        "github_token"
    )
    assert execution.arguments["api_token"].name == "github_token"
    assert "super-secret-value" not in str(execution.arguments)


def test_secret_reference_requires_secret_provider() -> None:
    executor = ToolExecutor(_registry(lambda arguments: "ok"))

    result = executor.execute(
        agent=_agent(),
        tool_name="external_api",
        arguments={
            "api_token": SecretReference("github_token"),
            "payload": "hello",
        },
    )

    assert result.success is False
    assert result.error is not None
    assert "SecretProvider is required" in result.error


def test_missing_secret_fails_without_calling_handler() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "should not execute"

    executor = ToolExecutor(
        _registry(handler),
        secret_provider=InMemorySecretProvider(),
    )

    result = executor.execute(
        agent=_agent(),
        tool_name="external_api",
        arguments={
            "api_token": SecretReference("missing"),
            "payload": "hello",
        },
    )

    assert result.success is False
    assert "was not found" in result.error
    assert called is False


def test_plain_string_cannot_be_used_as_secret_reference() -> None:
    executor = ToolExecutor(
        _registry(lambda arguments: "should not execute"),
        secret_provider=InMemorySecretProvider(
            {"github_token": "super-secret-value"}
        ),
    )

    with pytest.raises(
        ValueError,
        match="secret_reference",
    ):
        executor.execute(
            agent=_agent(),
            tool_name="external_api",
            arguments={
                "api_token": "super-secret-value",
                "payload": "hello",
            },
        )

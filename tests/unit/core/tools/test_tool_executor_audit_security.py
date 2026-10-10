from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    AuditEventType,
    AuditService,
    InMemoryAuditRepository,
    InMemorySecretProvider,
    SecretReference,
)
from orion.core.security.redaction import REDACTED_VALUE
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.execution_repository_memory import (
    InMemoryToolExecutionRepository,
)
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.memory_registry import InMemoryToolRegistry

SECRET = "super-secret-value"


def _agent() -> Agent:
    return Agent.create(
        name="Audit Secret Agent",
        description="Agent for audit secret-redaction tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.EXTERNAL_API}),
        ),
    )


def _registry(handler) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="secret_tool",
            description="Secret-bearing tool.",
            permission=AgentPermission.EXTERNAL_API,
            handler=handler,
            input_schema=ToolInputSchema(
                fields=(
                    ToolInputField(
                        name="api_token",
                        input_type=ToolInputType.SECRET_REFERENCE,
                        required=True,
                    ),
                ),
            ),
        )
    )

    return registry


def _executor(handler):
    execution_repository = InMemoryToolExecutionRepository()
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)

    executor = ToolExecutor(
        _registry(handler),
        execution_repository=execution_repository,
        secret_provider=InMemorySecretProvider(
            {"github_token": SECRET},
        ),
        audit_service=audit_service,
    )

    return executor, execution_repository, audit_repository


def _arguments() -> dict:
    return {
        "api_token": SecretReference("github_token"),
    }


def _execute_with_parent_id(executor, **kwargs):
    parent_execution_id = uuid4()

    result = executor.execute(
        execution_id=parent_execution_id,
        **kwargs,
    )

    return result, parent_execution_id


def test_secret_in_output_is_redacted_from_lifecycle() -> None:
    executor, execution_repository, _ = _executor(
        lambda arguments: arguments["api_token"],
    )

    result = executor.execute(
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    assert result.success is True
    assert result.output == SECRET

    execution = execution_repository.get(result.execution_id)

    assert execution is not None
    assert execution.output == REDACTED_VALUE
    assert SECRET not in str(execution.output)


def test_secret_inside_nested_output_is_redacted() -> None:
    executor, execution_repository, _ = _executor(
        lambda arguments: {
            "token": arguments["api_token"],
            "nested": [
                arguments["api_token"],
                {"credential": arguments["api_token"]},
            ],
        },
    )

    result = executor.execute(
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    assert result.success is True
    assert result.output["token"] == SECRET

    execution = execution_repository.get(result.execution_id)

    assert execution is not None
    assert execution.output == {
        "token": REDACTED_VALUE,
        "nested": [
            REDACTED_VALUE,
            {"credential": REDACTED_VALUE},
        ],
    }


def test_secret_in_error_is_redacted_from_lifecycle() -> None:
    def failing_handler(arguments):
        raise RuntimeError(f"Remote API rejected credential {arguments['api_token']}")

    executor, execution_repository, _ = _executor(failing_handler)

    result = executor.execute(
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    assert result.success is False
    assert SECRET in result.error

    execution = execution_repository.get(result.execution_id)

    assert execution is not None
    assert execution.error == (f"Remote API rejected credential {REDACTED_VALUE}")
    assert SECRET not in execution.error


def test_secret_is_redacted_from_audit_output() -> None:
    executor, _, audit_repository = _executor(
        lambda arguments: arguments["api_token"],
    )

    result, parent_execution_id = _execute_with_parent_id(
        executor,
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    events = audit_repository.list_for_execution(parent_execution_id)

    completed = [
        event for event in events if event.event_type == AuditEventType.TOOL_EXECUTION_COMPLETED
    ]

    assert len(completed) == 1
    assert completed[0].details["output"] == REDACTED_VALUE
    assert SECRET not in str(completed[0].details)
    assert result.execution_id != parent_execution_id


def test_secret_is_redacted_from_audit_error() -> None:
    def failing_handler(arguments):
        raise RuntimeError(f"Authentication failed with {arguments['api_token']}")

    executor, _, audit_repository = _executor(failing_handler)

    result, parent_execution_id = _execute_with_parent_id(
        executor,
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    events = audit_repository.list_for_execution(parent_execution_id)

    failed = [event for event in events if event.event_type == AuditEventType.TOOL_EXECUTION_FAILED]

    assert len(failed) == 1
    assert failed[0].details["error"] == (f"Authentication failed with {REDACTED_VALUE}")
    assert SECRET not in str(failed[0].details)
    assert result.execution_id != parent_execution_id


def test_audit_records_started_and_completed() -> None:
    executor, _, audit_repository = _executor(
        lambda arguments: "ok",
    )

    _, parent_execution_id = _execute_with_parent_id(
        executor,
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    events = audit_repository.list_for_execution(parent_execution_id)

    assert [event.event_type for event in events] == [
        AuditEventType.TOOL_EXECUTION_STARTED,
        AuditEventType.TOOL_EXECUTION_COMPLETED,
    ]


def test_audit_records_started_and_failed() -> None:
    def failing_handler(arguments):
        raise RuntimeError("tool failed")

    executor, _, audit_repository = _executor(failing_handler)

    _, parent_execution_id = _execute_with_parent_id(
        executor,
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    events = audit_repository.list_for_execution(parent_execution_id)

    assert [event.event_type for event in events] == [
        AuditEventType.TOOL_EXECUTION_STARTED,
        AuditEventType.TOOL_EXECUTION_FAILED,
    ]


def test_audit_never_contains_secret_value() -> None:
    executor, _, audit_repository = _executor(
        lambda arguments: {
            "token": arguments["api_token"],
            "message": f"used {arguments['api_token']}",
        },
    )

    _, parent_execution_id = _execute_with_parent_id(
        executor,
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    events = audit_repository.list_for_execution(parent_execution_id)

    assert events

    for event in events:
        assert SECRET not in str(event.details)


def test_missing_secret_does_not_reach_handler() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "should not execute"

    execution_repository = InMemoryToolExecutionRepository()
    audit_repository = InMemoryAuditRepository()

    executor = ToolExecutor(
        _registry(handler),
        execution_repository=execution_repository,
        secret_provider=InMemorySecretProvider(),
        audit_service=AuditService(audit_repository),
    )

    result = executor.execute(
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
    )

    assert result.success is False
    assert called is False


def test_audit_uses_parent_execution_id_for_correlation() -> None:
    executor, execution_repository, audit_repository = _executor(
        lambda arguments: "ok",
    )

    parent_execution_id = uuid4()

    result = executor.execute(
        agent=_agent(),
        tool_name="secret_tool",
        arguments=_arguments(),
        execution_id=parent_execution_id,
    )

    assert result.success is True
    assert result.execution_id is not None
    assert result.execution_id != parent_execution_id

    lifecycle = execution_repository.get(result.execution_id)

    assert lifecycle is not None
    assert lifecycle.execution_id == parent_execution_id

    events = audit_repository.list_for_execution(parent_execution_id)

    assert [event.event_type for event in events] == [
        AuditEventType.TOOL_EXECUTION_STARTED,
        AuditEventType.TOOL_EXECUTION_COMPLETED,
    ]

    for event in events:
        assert event.execution_id == parent_execution_id

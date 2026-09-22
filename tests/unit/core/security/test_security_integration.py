from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    ApprovalRequiredError,
    ApprovalService,
    AuditEventType,
    AuditService,
    AuthorizationService,
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemorySecretProvider,
    SecretReference,
)
from orion.core.security.redaction import REDACTED_VALUE
from orion.core.security.risk import ToolRiskLevel
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

SECRET = "integration-secret-value"


def _agent(
    permissions: frozenset[AgentPermission],
) -> Agent:
    return Agent.create(
        name="Security Integration Agent",
        description="Agent used for end-to-end security integration tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def _registry(handler) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="secure_external_action",
            description="High-risk secret-backed external action.",
            permission=AgentPermission.EXTERNAL_API,
            handler=handler,
            risk_level=ToolRiskLevel.HIGH,
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


def _services():
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)

    approval_repository = InMemoryApprovalRepository()
    approval_service = ApprovalService(
        approval_repository,
        audit_service=audit_service,
    )

    authorization_service = AuthorizationService(
        audit_service=audit_service,
    )

    execution_repository = InMemoryToolExecutionRepository()

    return (
        audit_repository,
        approval_service,
        authorization_service,
        execution_repository,
    )


def _executor(handler):
    (
        audit_repository,
        approval_service,
        authorization_service,
        execution_repository,
    ) = _services()

    audit_service = AuditService(audit_repository)

    executor = ToolExecutor(
        _registry(handler),
        execution_repository=execution_repository,
        authorization_service=authorization_service,
        approval_service=approval_service,
        secret_provider=InMemorySecretProvider(
            {"integration_token": SECRET},
        ),
        audit_service=audit_service,
    )

    return (
        executor,
        approval_service,
        audit_repository,
        execution_repository,
    )


def _arguments() -> dict:
    return {
        "api_token": SecretReference("integration_token"),
        "payload": "perform secure action",
    }


def test_high_risk_security_chain_is_enforced_end_to_end() -> None:
    received = {}

    def handler(arguments):
        received.update(arguments)
        return {
            "status": "executed",
            "token": arguments["api_token"],
        }

    (
        executor,
        approval_service,
        audit_repository,
        execution_repository,
    ) = _executor(handler)

    agent = _agent(frozenset({AgentPermission.EXTERNAL_API}))
    parent_execution_id = uuid4()

    with pytest.raises(ApprovalRequiredError) as exc_info:
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=parent_execution_id,
        )

    request_id = exc_info.value.request_id
    request = approval_service._repository.get(request_id)

    assert request is not None
    assert request.status.value == "pending"
    assert request.execution_id == parent_execution_id

    approval_events = audit_repository.list_for_execution(
        parent_execution_id,
    )

    assert [
        event.event_type
        for event in approval_events
    ] == [
        AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED,
        AuditEventType.APPROVAL_REQUESTED,
    ]

    approval_service.approve(
        request_id=request_id,
        approver="integration-test",
        reason="Approved for end-to-end security validation.",
    )

    events_after_approval = audit_repository.list_for_execution(
        parent_execution_id,
    )

    assert [
        event.event_type
        for event in events_after_approval
    ] == [
        AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED,
        AuditEventType.APPROVAL_REQUESTED,
        AuditEventType.APPROVAL_GRANTED,
    ]

    result = executor.execute(
        agent=agent,
        tool_name="secure_external_action",
        arguments=_arguments(),
        execution_id=parent_execution_id,
        approval_id=request_id,
    )

    assert result.success is True
    assert result.output == {
        "status": "executed",
        "token": SECRET,
    }

    assert received == {
        "api_token": SECRET,
        "payload": "perform secure action",
    }

    assert result.execution_id is not None
    assert result.execution_id != parent_execution_id

    lifecycle = execution_repository.get(result.execution_id)

    assert lifecycle is not None
    assert lifecycle.execution_id == parent_execution_id
    assert lifecycle.status.value == "completed"
    assert lifecycle.output == {
        "status": "executed",
        "token": REDACTED_VALUE,
    }

    final_events = audit_repository.list_for_execution(
        parent_execution_id,
    )

    assert [
        event.event_type
        for event in final_events
    ] == [
        AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED,
        AuditEventType.APPROVAL_REQUESTED,
        AuditEventType.APPROVAL_GRANTED,
        AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED,
        AuditEventType.TOOL_EXECUTION_STARTED,
        AuditEventType.TOOL_EXECUTION_COMPLETED,
    ]

    for event in final_events:
        assert event.execution_id == parent_execution_id
        assert SECRET not in str(event.details)

    assert final_events[-1].details["output"] == {
        "status": "executed",
        "token": REDACTED_VALUE,
    }


def test_unauthorized_agent_is_denied_before_handler() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "should never execute"

    (
        executor,
        _,
        audit_repository,
        _,
    ) = _executor(handler)

    agent = _agent(frozenset())
    parent_execution_id = uuid4()

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=parent_execution_id,
        )

    assert called is False

    events = audit_repository.list_for_execution(
        parent_execution_id,
    )

    assert [
        event.event_type
        for event in events
    ] == [
        AuditEventType.AUTHORIZATION_DENIED,
    ]

    assert events[0].execution_id == parent_execution_id

from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    AuditEventType,
    AuditService,
    AuthorizationService,
    InMemoryAuditRepository,
    SecurityContext,
)
from orion.core.security.models import AuthorizationRequest
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent(
    permissions: frozenset[AgentPermission],
) -> Agent:
    return Agent.create(
        name="Adversarial Security Agent",
        description="Agent used for adversarial authorization tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def _registry(handler):
    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="privileged_external_action",
            description="Privileged external action.",
            permission=AgentPermission.EXTERNAL_API,
            handler=handler,
            risk_level=ToolRiskLevel.LOW,
            input_schema=ToolInputSchema(
                fields=(
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


def _build(handler):
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    authorization_service = AuthorizationService(
        audit_service=audit_service,
    )
    executor = ToolExecutor(
        _registry(handler),
        authorization_service=authorization_service,
        audit_service=audit_service,
    )
    return executor, authorization_service, audit_repository


def test_capability_cannot_substitute_for_permission() -> None:
    handler_called = False

    def handler(arguments):
        nonlocal handler_called
        handler_called = True
        return "executed"

    executor, _, _ = _build(handler)

    agent = _agent(permissions=frozenset())

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="privileged_external_action",
            arguments={"payload": "test"},
        )

    assert handler_called is False


def test_unrelated_permission_cannot_escalate_to_external_api() -> None:
    handler_called = False

    def handler(arguments):
        nonlocal handler_called
        handler_called = True
        return "executed"

    executor, _, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.READ_FILES}),
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="privileged_external_action",
            arguments={"payload": "test"},
        )

    assert handler_called is False


def test_authorization_rejects_spoofed_agent_context() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    authorization_service = AuthorizationService(
        audit_service=audit_service,
    )

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    request = AuthorizationRequest(
        context=SecurityContext(
            agent_id=uuid4(),
            task_id=None,
            execution_id=uuid4(),
        ),
        resource="privileged_external_action",
        action="execute",
    )

    result = authorization_service.authorize(
        agent=agent,
        request=request,
        required_permission=AgentPermission.EXTERNAL_API,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.allowed is False
    assert result.decision.value == "deny"
    assert "does not match" in result.reason

    events = audit_repository.list_for_agent(agent.id)

    assert events
    assert events[-1].event_type == AuditEventType.AUTHORIZATION_DENIED


def test_authorization_rejects_missing_execution_context_when_spoofed() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    authorization_service = AuthorizationService(
        audit_service=audit_service,
    )

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    request = AuthorizationRequest(
        context=SecurityContext(
            agent_id=agent.id,
            task_id=None,
            execution_id=None,
        ),
        resource="privileged_external_action",
        action="execute",
    )

    result = authorization_service.authorize(
        agent=agent,
        request=request,
        required_permission=AgentPermission.EXTERNAL_API,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.allowed is True


def test_extra_permissions_do_not_bypass_tool_permission() -> None:
    handler_called = False

    def handler(arguments):
        nonlocal handler_called
        handler_called = True
        return "executed"

    executor, _, _ = _build(handler)

    agent = _agent(
        permissions=frozenset(
            {
                AgentPermission.READ_FILES,
                AgentPermission.WRITE_FILES,
                AgentPermission.WEB_ACCESS,
            }
        ),
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="privileged_external_action",
            arguments={"payload": "test"},
        )

    assert handler_called is False


def test_authorization_denial_precedes_tool_execution() -> None:
    handler_called = False

    def handler(arguments):
        nonlocal handler_called
        handler_called = True
        return "executed"

    executor, _, audit_repository = _build(handler)

    agent = _agent(permissions=frozenset())

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="privileged_external_action",
            arguments={"payload": "test"},
        )

    assert handler_called is False

    events = audit_repository.list_for_agent(agent.id)

    assert events
    assert events[-1].event_type == AuditEventType.AUTHORIZATION_DENIED

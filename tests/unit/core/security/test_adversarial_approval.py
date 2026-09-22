from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    ApprovalService,
    AuditEventType,
    AuditService,
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemorySecretProvider,
    SecretReference,
)
from orion.core.security.authorization import AuthorizationService
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.memory_registry import InMemoryToolRegistry

SECRET = "adversarial-secret"


def _agent(
    *,
    permissions: frozenset[AgentPermission],
    name: str = "Adversarial Agent",
) -> Agent:
    return Agent.create(
        name=name,
        description="Agent used for adversarial security tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def _registry(handler) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    registry.register(
        ToolDefinition(
            name="secure_external_action",
            description="High-risk external action.",
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


def _build(handler):
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

    executor = ToolExecutor(
        _registry(handler),
        authorization_service=authorization_service,
        approval_service=approval_service,
        secret_provider=InMemorySecretProvider(
            {"integration_token": SECRET},
        ),
        audit_service=audit_service,
    )

    return executor, approval_service, audit_repository


def _arguments() -> dict:
    return {
        "api_token": SecretReference("integration_token"),
        "payload": "adversarial action",
    }


def _create_approval(
    approval_service: ApprovalService,
    *,
    agent_id,
    execution_id,
    tool_name="secure_external_action",
    risk_level=ToolRiskLevel.HIGH,
):
    return approval_service.create_request(
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name=tool_name,
        action="execute",
        risk_level=risk_level,
    )


def test_approval_cannot_cross_execution_context() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    approved_execution = uuid4()
    attacker_execution = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=approved_execution,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=attacker_execution,
            approval_id=request.id,
        )

    assert called is False


def test_approval_cannot_cross_agent_context() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    owner = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
        name="Approval Owner",
    )
    attacker = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
        name="Attacker",
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=owner.id,
        execution_id=execution_id,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=attacker,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert called is False


def test_approval_cannot_be_replayed_after_consumption() -> None:
    call_count = 0

    def handler(arguments):
        nonlocal call_count
        call_count += 1
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=execution_id,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    first = executor.execute(
        agent=agent,
        tool_name="secure_external_action",
        arguments=_arguments(),
        execution_id=execution_id,
        approval_id=request.id,
    )

    assert first.success is True
    assert call_count == 1

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert call_count == 1


def test_denied_approval_cannot_be_used() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=execution_id,
    )

    approval_service.deny(
        request_id=request.id,
        approver="security-test",
        reason="Denied during adversarial test.",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert called is False


def test_expired_approval_cannot_be_used() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=execution_id,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    approved = approval_service._repository.get(request.id)
    assert approved is not None

    approval_service._repository.save(
        type(approved)(
            id=approved.id,
            agent_id=approved.agent_id,
            execution_id=approved.execution_id,
            tool_name=approved.tool_name,
            action=approved.action,
            risk_level=approved.risk_level,
            created_at=approved.created_at,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            status=approved.status,
        )
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert called is False


def test_approval_cannot_be_used_for_different_tool() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name="different_tool",
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert called is False


def test_approval_cannot_be_used_for_different_risk_level() -> None:
    called = False

    def handler(arguments):
        nonlocal called
        called = True
        return "executed"

    executor, approval_service, _ = _build(handler)

    agent = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )

    execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=agent.id,
        execution_id=execution_id,
        risk_level=ToolRiskLevel.CRITICAL,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=agent,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=execution_id,
            approval_id=request.id,
        )

    assert called is False


def test_adversarial_approval_failures_do_not_execute_handler() -> None:
    calls = []

    def handler(arguments):
        calls.append(arguments)
        return "executed"

    executor, approval_service, audit_repository = _build(handler)

    owner = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
    )
    attacker = _agent(
        permissions=frozenset({AgentPermission.EXTERNAL_API}),
        name="Attacker",
    )

    execution_id = uuid4()
    attacker_execution_id = uuid4()

    request = _create_approval(
        approval_service,
        agent_id=owner.id,
        execution_id=execution_id,
    )

    approval_service.approve(
        request_id=request.id,
        approver="security-test",
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent=attacker,
            tool_name="secure_external_action",
            arguments=_arguments(),
            execution_id=attacker_execution_id,
            approval_id=request.id,
        )

    assert calls == []

    events = audit_repository.list_for_execution(
        attacker_execution_id,
    )

    assert events
    assert events[-1].event_type == (
        AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED
    )

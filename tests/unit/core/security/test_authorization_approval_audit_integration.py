from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.security.approval_service import ApprovalService
from orion.core.security.audit import AuditEventType
from orion.core.security.audit_repository_memory import InMemoryAuditRepository
from orion.core.security.audit_service import AuditService
from orion.core.security.authorization import AuthorizationService
from orion.core.security.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    SecurityContext,
)
from orion.core.security.risk import ToolRiskLevel
from orion.core.security.risk_policy import ToolRiskPolicy


def make_agent(
    *,
    permissions: set[AgentPermission] | None = None,
) -> Agent:
    return Agent.create(
        name="audit-test-agent",
        description="Agent used for authorization audit tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(permissions=frozenset(permissions or set())),
    )


def make_request(
    agent_id,
    *,
    execution_id=None,
    action="execute",
):
    return AuthorizationRequest(
        context=SecurityContext(
            agent_id=agent_id,
            task_id=uuid4(),
            execution_id=execution_id,
        ),
        resource="test_tool",
        action=action,
    )


def test_authorization_allowed_is_audited() -> None:
    repository = InMemoryAuditRepository()
    audit_service = AuditService(repository)
    agent = make_agent(permissions={AgentPermission.READ_FILES})
    service = AuthorizationService(
        risk_policy=ToolRiskPolicy(),
        audit_service=audit_service,
    )

    request = make_request(agent.id)

    result = service.authorize(
        agent=agent,
        request=request,
        required_permission=AgentPermission.READ_FILES,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.decision is AuthorizationDecision.ALLOW

    events = repository.list_for_agent(agent.id)
    assert len(events) == 1
    assert events[0].event_type is AuditEventType.AUTHORIZATION_ALLOWED
    assert events[0].agent_id == agent.id


def test_authorization_denied_permission_is_audited() -> None:
    repository = InMemoryAuditRepository()
    audit_service = AuditService(repository)
    agent = make_agent()
    service = AuthorizationService(
        risk_policy=ToolRiskPolicy(),
        audit_service=audit_service,
    )

    request = make_request(agent.id)

    result = service.authorize(
        agent=agent,
        request=request,
        required_permission=AgentPermission.WRITE_FILES,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.decision is AuthorizationDecision.DENY

    events = repository.list_for_agent(agent.id)
    assert len(events) == 1
    assert events[0].event_type is AuditEventType.AUTHORIZATION_DENIED


def test_authorization_approval_required_is_audited() -> None:
    repository = InMemoryAuditRepository()
    audit_service = AuditService(repository)
    agent = make_agent(permissions={AgentPermission.WRITE_FILES})
    service = AuthorizationService(
        risk_policy=ToolRiskPolicy(),
        audit_service=audit_service,
    )

    request = make_request(agent.id)

    result = service.authorize(
        agent=agent,
        request=request,
        required_permission=AgentPermission.WRITE_FILES,
        risk_level=ToolRiskLevel.HIGH,
    )

    assert result.decision is AuthorizationDecision.REQUIRE_APPROVAL

    events = repository.list_for_agent(agent.id)
    assert len(events) == 1
    assert events[0].event_type is AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED


def test_approval_request_is_audited() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    approval_repository = InMemoryApprovalRepository()

    service = ApprovalService(
        approval_repository,
        audit_service=audit_service,
    )

    agent_id = uuid4()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name="dangerous_tool",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    events = audit_repository.list_for_agent(agent_id)

    assert len(events) == 1
    assert events[0].event_type is AuditEventType.APPROVAL_REQUESTED
    assert events[0].execution_id == execution_id
    assert events[0].details["approval_request_id"] == str(request.id)


def test_approval_grant_is_audited() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    approval_repository = InMemoryApprovalRepository()

    service = ApprovalService(
        approval_repository,
        audit_service=audit_service,
    )

    agent_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        tool_name="dangerous_tool",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
    )

    record = service.approve(
        request_id=request.id,
        approver="security-admin",
        reason="Approved for controlled execution.",
    )

    events = audit_repository.list_for_agent(agent_id)

    assert len(events) == 2
    assert events[0].event_type is AuditEventType.APPROVAL_REQUESTED
    assert events[1].event_type is AuditEventType.APPROVAL_GRANTED
    assert events[1].details["approver"] == record.approver
    assert events[1].details["reason"] == record.reason
    assert events[1].details["approval_request_id"] == str(request.id)


def test_approval_denial_is_audited() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    approval_repository = InMemoryApprovalRepository()

    service = ApprovalService(
        approval_repository,
        audit_service=audit_service,
    )

    agent_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        tool_name="dangerous_tool",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    record = service.deny(
        request_id=request.id,
        approver="security-admin",
        reason="Rejected by policy.",
    )

    events = audit_repository.list_for_agent(agent_id)

    assert len(events) == 2
    assert events[0].event_type is AuditEventType.APPROVAL_REQUESTED
    assert events[1].event_type is AuditEventType.APPROVAL_DENIED
    assert events[1].details["approver"] == record.approver
    assert events[1].details["reason"] == record.reason
    assert events[1].details["approval_request_id"] == str(request.id)


def test_approval_lifecycle_remains_consistent_with_audit() -> None:
    audit_repository = InMemoryAuditRepository()
    audit_service = AuditService(audit_repository)
    approval_repository = InMemoryApprovalRepository()

    service = ApprovalService(
        approval_repository,
        audit_service=audit_service,
    )

    agent_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        tool_name="critical_tool",
        action="execute",
        risk_level=ToolRiskLevel.CRITICAL,
    )

    service.approve(
        request_id=request.id,
        approver="security-admin",
        reason="Approved.",
    )

    consumed = service.consume_approval(request_id=request.id)

    assert consumed.status is ApprovalStatus.CONSUMED

    events = audit_repository.list_for_agent(agent_id)

    assert [event.event_type for event in events] == [
        AuditEventType.APPROVAL_REQUESTED,
        AuditEventType.APPROVAL_GRANTED,
    ]

    assert events[0].details["approval_request_id"] == str(request.id)
    assert events[1].details["approval_request_id"] == str(request.id)

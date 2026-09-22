from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationService,
    SecurityContext,
    ToolRiskPolicy,
)
from orion.core.tools.risk import ToolRiskLevel


def _agent_with_permissions(
    permissions: frozenset[AgentPermission],
) -> Agent:
    return Agent.create(
        name="Security Test Agent",
        description="Agent used for authorization tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(permissions),
    )


def _request(agent_id) -> AuthorizationRequest:
    return AuthorizationRequest(
        context=SecurityContext(agent_id=agent_id),
        resource="test_tool",
        action="execute",
    )


def test_authorization_allows_granted_low_risk_permission() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.decision == AuthorizationDecision.ALLOW
    assert result.allowed is True


def test_authorization_denies_missing_permission() -> None:
    agent = _agent_with_permissions(frozenset())

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.decision == AuthorizationDecision.DENY
    assert result.allowed is False


def test_authorization_reason_is_present() -> None:
    agent = _agent_with_permissions(frozenset())

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
    )

    assert result.reason


def test_authorization_does_not_grant_unrelated_permission() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.READ_FILES}),
    )

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
    )

    assert result.decision == AuthorizationDecision.DENY


def test_authorization_denies_mismatched_security_context() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(uuid4()),
        required_permission=AgentPermission.WEB_ACCESS,
    )

    assert result.decision == AuthorizationDecision.DENY
    assert result.allowed is False
    assert "does not match" in result.reason


def test_high_risk_authorization_requires_approval() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
        risk_level=ToolRiskLevel.HIGH,
    )

    assert result.decision == AuthorizationDecision.REQUIRE_APPROVAL
    assert result.allowed is False
    assert "requires approval" in result.reason


def test_critical_risk_authorization_requires_approval() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    result = AuthorizationService().authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
        risk_level=ToolRiskLevel.CRITICAL,
    )

    assert result.decision == AuthorizationDecision.REQUIRE_APPROVAL
    assert result.allowed is False


def test_custom_risk_policy_is_used() -> None:
    agent = _agent_with_permissions(
        frozenset({AgentPermission.WEB_ACCESS}),
    )

    policy = ToolRiskPolicy(
        low_decision=AuthorizationDecision.DENY,
    )

    result = AuthorizationService(
        risk_policy=policy,
    ).authorize(
        agent=agent,
        request=_request(agent.id),
        required_permission=AgentPermission.WEB_ACCESS,
        risk_level=ToolRiskLevel.LOW,
    )

    assert result.decision == AuthorizationDecision.DENY

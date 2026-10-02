from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.agents.permissions import AgentPermission
from orion.core.security.audit import AuditEventType
from orion.core.security.audit_service import AuditService
from orion.core.security.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
)
from orion.core.security.risk import ToolRiskLevel
from orion.core.security.risk_policy import ToolRiskPolicy


class AuthorizationService:
    """Central authorization authority for ORION security decisions."""

    def __init__(
        self,
        risk_policy: ToolRiskPolicy | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._risk_policy = risk_policy or ToolRiskPolicy()
        self._audit_service = audit_service

    def authorize(
        self,
        agent: Agent,
        request: AuthorizationRequest,
        required_permission: AgentPermission,
        risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
    ) -> AuthorizationResult:
        """Authorize an operation using identity, permission, and risk policy."""

        if request.context.agent_id != agent.id:
            result = AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason=(
                    "Security context agent does not match "
                    "the authorization subject."
                ),
            )
            self._record_audit(
                event_type=AuditEventType.AUTHORIZATION_DENIED,
                agent_id=agent.id,
                execution_id=request.context.execution_id,
                resource=request.resource,
                action=request.action,
                risk_level=risk_level,
                outcome="denied",
                reason=result.reason,
            )
            return result

        if not agent.permission_policy.allows(required_permission):
            result = AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason=(
                    f"Agent '{agent.name}' is not authorized for "
                    f"permission '{required_permission.value}'."
                ),
            )
            self._record_audit(
                event_type=AuditEventType.AUTHORIZATION_DENIED,
                agent_id=agent.id,
                execution_id=request.context.execution_id,
                resource=request.resource,
                action=request.action,
                risk_level=risk_level,
                outcome="denied",
                reason=result.reason,
            )
            return result

        decision = self._risk_policy.decide(risk_level)

        if decision == AuthorizationDecision.ALLOW:
            result = AuthorizationResult(
                decision=decision,
                reason=(
                    f"Agent '{agent.name}' is authorized for "
                    f"action '{request.action}' on resource "
                    f"'{request.resource}' with risk level "
                    f"'{risk_level.name}'."
                ),
            )
            self._record_audit(
                event_type=AuditEventType.AUTHORIZATION_ALLOWED,
                agent_id=agent.id,
                execution_id=request.context.execution_id,
                resource=request.resource,
                action=request.action,
                risk_level=risk_level,
                outcome="allowed",
                reason=result.reason,
            )
            return result

        if decision == AuthorizationDecision.REQUIRE_APPROVAL:
            result = AuthorizationResult(
                decision=decision,
                reason=(
                    f"Action '{request.action}' on resource "
                    f"'{request.resource}' requires approval because "
                    f"its risk level is '{risk_level.name}'."
                ),
            )
            self._record_audit(
                event_type=AuditEventType.AUTHORIZATION_APPROVAL_REQUIRED,
                agent_id=agent.id,
                execution_id=request.context.execution_id,
                resource=request.resource,
                action=request.action,
                risk_level=risk_level,
                outcome="approval_required",
                reason=result.reason,
            )
            return result

        result = AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason=(
                f"Action '{request.action}' on resource "
                f"'{request.resource}' was denied by the risk policy."
            ),
        )
        self._record_audit(
            event_type=AuditEventType.AUTHORIZATION_DENIED,
            agent_id=agent.id,
            execution_id=request.context.execution_id,
            resource=request.resource,
            action=request.action,
            risk_level=risk_level,
            outcome="denied",
            reason=result.reason,
        )
        return result

    def _record_audit(
        self,
        *,
        event_type: AuditEventType,
        agent_id: UUID,
        execution_id: UUID | None,
        resource: str,
        action: str,
        risk_level: ToolRiskLevel,
        outcome: str,
        reason: str,
    ) -> None:
        if self._audit_service is None:
            return

        self._audit_service.record(
            event_type=event_type,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name=resource,
            action=action,
            risk_level=risk_level,
            outcome=outcome,
            details={"reason": reason},
        )

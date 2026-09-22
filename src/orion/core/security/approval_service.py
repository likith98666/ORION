from datetime import datetime
from uuid import UUID

from orion.core.security.approval import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
)
from orion.core.security.approval_repository import ApprovalRepository
from orion.core.security.audit import AuditEventType
from orion.core.security.audit_service import AuditService
from orion.core.security.risk import ToolRiskLevel


class ApprovalService:
    """Creates and resolves approval requests for high-risk actions."""

    def __init__(
        self,
        repository: ApprovalRepository,
        audit_service: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service

    def create_request(
        self,
        *,
        agent_id: UUID,
        tool_name: str,
        action: str,
        risk_level: ToolRiskLevel,
        execution_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> ApprovalRequest:
        """Create and persist a pending approval request."""

        if risk_level not in (
            ToolRiskLevel.HIGH,
            ToolRiskLevel.CRITICAL,
        ):
            raise ValueError(
                "Approval requests are only valid for HIGH or CRITICAL risk."
            )

        request = ApprovalRequest.create(
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            expires_at=expires_at,
        )

        self._repository.save(request)

        self._record_audit(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            request=request,
            outcome="requested",
            details={"approval_request_id": str(request.id)},
        )

        return request

    def approve(
        self,
        *,
        request_id: UUID,
        approver: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """Approve a pending, non-expired request."""

        request = self._get_pending_request(request_id)

        record = ApprovalRecord(
            request_id=request.id,
            decision=ApprovalDecision.APPROVE,
            approver=approver,
            decided_at=datetime.now(request.created_at.tzinfo),
            reason=reason,
        )

        self._repository.save(
            ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                action=request.action,
                risk_level=request.risk_level,
                created_at=request.created_at,
                expires_at=request.expires_at,
                status=ApprovalStatus.APPROVED,
            )
        )

        self._record_audit(
            event_type=AuditEventType.APPROVAL_GRANTED,
            request=request,
            outcome="approved",
            details={
                "approver": approver,
                "reason": reason,
                "approval_request_id": str(request.id),
            },
        )

        return record

    def deny(
        self,
        *,
        request_id: UUID,
        approver: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """Deny a pending, non-expired request."""

        request = self._get_pending_request(request_id)

        record = ApprovalRecord(
            request_id=request.id,
            decision=ApprovalDecision.DENY,
            approver=approver,
            decided_at=datetime.now(request.created_at.tzinfo),
            reason=reason,
        )

        self._repository.save(
            ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                action=request.action,
                risk_level=request.risk_level,
                created_at=request.created_at,
                expires_at=request.expires_at,
                status=ApprovalStatus.DENIED,
            )
        )

        self._record_audit(
            event_type=AuditEventType.APPROVAL_DENIED,
            request=request,
            outcome="denied",
            details={
                "approver": approver,
                "reason": reason,
                "approval_request_id": str(request.id),
            },
        )

        return record

    def validate_approval(
        self,
        *,
        request_id: UUID,
        agent_id: UUID,
        execution_id: UUID | None,
        tool_name: str,
        action: str,
        risk_level: ToolRiskLevel,
    ) -> ApprovalRequest:
        """Validate an approved request against the exact action context."""

        request = self._repository.get(request_id)

        if request is None:
            raise PermissionError(
                f"Approval request '{request_id}' was not found."
            )

        if request.status is not ApprovalStatus.APPROVED:
            raise PermissionError("Approval request is not approved.")

        if request.is_expired:
            raise PermissionError("Approval request has expired.")

        if request.agent_id != agent_id:
            raise PermissionError(
                "Approval request does not belong to this agent."
            )

        if request.execution_id != execution_id:
            raise PermissionError(
                "Approval request does not belong to this execution."
            )

        if request.tool_name != tool_name.strip():
            raise PermissionError(
                "Approval request does not match the requested tool."
            )

        if request.action != action.strip():
            raise PermissionError(
                "Approval request does not match the requested action."
            )

        if request.risk_level is not risk_level:
            raise PermissionError(
                "Approval request does not match the requested risk level."
            )

        return request

    def consume_approval(
        self,
        *,
        request_id: UUID,
    ) -> ApprovalRequest:
        """Consume an approved request so it cannot be replayed."""

        request = self._repository.get(request_id)

        if request is None:
            raise PermissionError(
                f"Approval request '{request_id}' was not found."
            )

        if request.status is not ApprovalStatus.APPROVED:
            raise PermissionError(
                "Approval request is not available for consumption."
            )

        if request.is_expired:
            expired = ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                action=request.action,
                risk_level=request.risk_level,
                created_at=request.created_at,
                expires_at=request.expires_at,
                status=ApprovalStatus.EXPIRED,
            )
            self._repository.save(expired)
            raise PermissionError("Approval request has expired.")

        consumed = ApprovalRequest(
            id=request.id,
            agent_id=request.agent_id,
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            action=request.action,
            risk_level=request.risk_level,
            created_at=request.created_at,
            expires_at=request.expires_at,
            status=ApprovalStatus.CONSUMED,
        )
        self._repository.save(consumed)

        return consumed

    def _record_audit(
        self,
        *,
        event_type: AuditEventType,
        request: ApprovalRequest,
        outcome: str,
        details: dict,
    ) -> None:
        if self._audit_service is None:
            return

        self._audit_service.record(
            event_type=event_type,
            agent_id=request.agent_id,
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            action=request.action,
            risk_level=request.risk_level,
            outcome=outcome,
            details=details,
        )

    def _get_pending_request(
        self,
        request_id: UUID,
    ) -> ApprovalRequest:
        request = self._repository.get(request_id)

        if request is None:
            raise ValueError(
                f"Approval request '{request_id}' was not found."
            )

        if request.status is not ApprovalStatus.PENDING:
            raise ValueError("Approval request is no longer pending.")

        if request.is_expired:
            expired = ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                action=request.action,
                risk_level=request.risk_level,
                created_at=request.created_at,
                expires_at=request.expires_at,
                status=ApprovalStatus.EXPIRED,
            )

            self._repository.save(expired)

            raise ValueError("Approval request has expired.")

        return request

"""ApprovalService integration for reviewable patch proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel
from orion.core.swe.cognitive.patch_contracts import PatchProposal


@dataclass(frozen=True)
class PatchApprovalPackage:
    """Structured, reviewable package binding a PatchProposal to an ApprovalRequest."""

    request_id: UUID
    patch_proposal: PatchProposal
    agent_id: UUID
    execution_id: UUID | None
    tool_name: str
    action: str
    risk_level: ToolRiskLevel
    created_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Return True if the proposal has been explicitly approved."""
        return self.status == ApprovalStatus.APPROVED

    @property
    def is_denied(self) -> bool:
        """Return True if the proposal has been explicitly denied."""
        return self.status == ApprovalStatus.DENIED

    def to_dict(self) -> dict[str, Any]:
        """Serialize the approval package for review, telemetry, and reporting."""
        return {
            "request_id": str(self.request_id),
            "patch_proposal": self.patch_proposal.to_dict(),
            "agent_id": str(self.agent_id),
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "tool_name": self.tool_name,
            "action": self.action,
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "affected_files": list(self.patch_proposal.affected_files),
            "diff_summary": self.patch_proposal.unified_diff,
            "rationale": self.patch_proposal.rationale,
            "validation_steps": list(self.patch_proposal.validation_steps),
        }


def request_patch_approval(
    patch_proposal: PatchProposal,
    agent: Agent,
    approval_service: ApprovalService,
    execution_id: UUID | None = None,
    tool_name: str = "apply_change",
    action: str = "apply_patch",
) -> PatchApprovalPackage:
    """Submit a validated PatchProposal to ApprovalService for authorization gating."""
    if not isinstance(patch_proposal, PatchProposal):
        raise TypeError("patch_proposal must be a PatchProposal instance.")
    if not isinstance(agent, Agent):
        raise TypeError("agent must be an Agent instance.")
    if not isinstance(approval_service, ApprovalService):
        raise TypeError("approval_service must be an ApprovalService instance.")

    request = approval_service.create_request(
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name=tool_name,
        action=action,
        risk_level=ToolRiskLevel.HIGH,
    )

    return PatchApprovalPackage(
        request_id=request.id,
        patch_proposal=patch_proposal,
        agent_id=agent.id,
        execution_id=execution_id,
        tool_name=tool_name,
        action=action,
        risk_level=ToolRiskLevel.HIGH,
        created_at=request.created_at,
        status=request.status,
    )


def refresh_patch_approval(
    package: PatchApprovalPackage,
    approval_service: ApprovalService,
) -> PatchApprovalPackage:
    """Fetch the latest status of an approval request and return an updated package."""
    req = approval_service._repository.get(package.request_id)
    if req is None:
        return package

    return PatchApprovalPackage(
        request_id=package.request_id,
        patch_proposal=package.patch_proposal,
        agent_id=package.agent_id,
        execution_id=package.execution_id,
        tool_name=package.tool_name,
        action=package.action,
        risk_level=package.risk_level,
        created_at=package.created_at,
        status=req.status,
    )

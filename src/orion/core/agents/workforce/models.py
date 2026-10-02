"""Data models, contracts, and verdicts for V4 Advanced Multi-Agent Engineering."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class WorkforceRole(str, Enum):
    """Specialized roles within the ORION multi-agent engineering workforce."""

    ARCHITECT = "architect"
    INVESTIGATOR = "investigator"
    IMPLEMENTER = "implementer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    SECURITY_ANALYST = "security_analyst"
    VERIFICATION_AUTHORITY = "verification_authority"


class AgentPermissionLevel(str, Enum):
    """Strictly partitioned privilege boundaries for agents."""

    READ_ONLY = "read_only"
    PROPOSE_PATCH = "propose_patch"
    APPLY_PATCH = "apply_patch"
    EXECUTE_TESTS = "execute_tests"
    VERIFY = "verify"


class WorkforcePermissionError(PermissionError):
    """Raised when an agent attempts an action exceeding its assigned contract permissions."""


@dataclass(frozen=True)
class WorkforceAgentContract:
    """Formal specification of an agent's identity, permissions, tools, and budget."""

    agent_id: UUID
    role: WorkforceRole
    permission_level: AgentPermissionLevel
    allowed_tools: frozenset[str]
    budget_timeout_seconds: float = 60.0
    evidence_prefix: str = "agent"

    def validate_tool(self, tool_name: str) -> None:
        """Verify that the tool is strictly authorized under this agent's contract."""
        if tool_name not in self.allowed_tools:
            raise WorkforcePermissionError(
                f"Agent '{self.role.value}' ({self.agent_id}) is forbidden from using tool "
                f"'{tool_name}'. Allowed: {sorted(self.allowed_tools)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert contract to dictionary."""
        return {
            "agent_id": str(self.agent_id),
            "role": self.role.value,
            "permission_level": self.permission_level.value,
            "allowed_tools": sorted(self.allowed_tools),
            "budget_timeout_seconds": self.budget_timeout_seconds,
            "evidence_prefix": self.evidence_prefix,
        }


@dataclass
class AgentProposal:
    """A solution or patch formulated by an agent candidate for peer review."""

    proposal_id: UUID
    agent_id: UUID
    role: WorkforceRole
    target_files: tuple[str, ...]
    patch_content: str
    rationale: str
    assumptions: tuple[str, ...] = ()
    confidence_score: float = 1.0
    evidence_items: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0.")

    def to_dict(self) -> dict[str, Any]:
        """Convert proposal to dictionary."""
        return {
            "proposal_id": str(self.proposal_id),
            "agent_id": str(self.agent_id),
            "role": self.role.value,
            "target_files": list(self.target_files),
            "patch_content": self.patch_content,
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
            "confidence_score": self.confidence_score,
            "evidence_items": list(self.evidence_items),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class ReviewVerdict:
    """Outcome of an independent multi-stage review pass."""

    verdict_id: UUID
    reviewer_id: UUID
    status: str  # "APPROVED", "CHANGES_REQUESTED", "REJECTED"
    security_clean: bool
    code_quality_clean: bool
    comments: tuple[str, ...]
    risk_level: str  # "low", "medium", "high", "critical"

    def to_dict(self) -> dict[str, Any]:
        """Convert review verdict to dictionary."""
        return {
            "verdict_id": str(self.verdict_id),
            "reviewer_id": str(self.reviewer_id),
            "status": self.status,
            "security_clean": self.security_clean,
            "code_quality_clean": self.code_quality_clean,
            "comments": list(self.comments),
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True)
class ConflictResolution:
    """Outcome of an evidence-backed resolution between competing agent proposals."""

    resolution_id: UUID
    competing_proposals: tuple[UUID, ...]
    selected_proposal_id: UUID | None
    rationale: str
    requires_human_approval: bool
    evaluation_matrix: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert conflict resolution to dictionary."""
        return {
            "resolution_id": str(self.resolution_id),
            "competing_proposals": [str(p) for p in self.competing_proposals],
            "selected_proposal_id": (
                str(self.selected_proposal_id) if self.selected_proposal_id else None
            ),
            "rationale": self.rationale,
            "requires_human_approval": self.requires_human_approval,
            "evaluation_matrix": dict(self.evaluation_matrix),
        }

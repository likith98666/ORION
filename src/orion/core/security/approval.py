from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from orion.core.security.risk import ToolRiskLevel


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"


class ApprovalRequiredError(PermissionError):
    """Raised when a high-risk action requires human approval."""

    def __init__(self, request_id: UUID) -> None:
        self.request_id = request_id
        super().__init__(f"Tool execution requires approval. Approval request: {request_id}")


@dataclass(frozen=True)
class ApprovalRequest:
    id: UUID
    agent_id: UUID
    execution_id: UUID | None
    tool_name: str
    action: str
    risk_level: ToolRiskLevel
    created_at: datetime
    expires_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID.")
        if not isinstance(self.agent_id, UUID):
            raise TypeError("agent_id must be a UUID.")
        if self.execution_id is not None and not isinstance(self.execution_id, UUID):
            raise TypeError("execution_id must be a UUID or None.")
        if not self.tool_name.strip():
            raise ValueError("tool_name must not be empty.")
        if not self.action.strip():
            raise ValueError("action must not be empty.")
        if not isinstance(self.risk_level, ToolRiskLevel):
            raise TypeError("risk_level must be a ToolRiskLevel.")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime.")
        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise TypeError("expires_at must be a datetime.")
        if not isinstance(self.status, ApprovalStatus):
            raise TypeError("status must be an ApprovalStatus.")

    @classmethod
    def create(
        cls,
        *,
        agent_id: UUID,
        execution_id: UUID | None = None,
        tool_name: str,
        action: str,
        risk_level: ToolRiskLevel,
        expires_at: datetime | None = None,
    ) -> "ApprovalRequest":
        return cls(
            id=uuid4(),
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name=tool_name.strip(),
            action=action.strip(),
            risk_level=risk_level,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at


@dataclass(frozen=True)
class ApprovalRecord:
    request_id: UUID
    decision: ApprovalDecision
    approver: str
    decided_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise TypeError("request_id must be a UUID.")
        if not isinstance(self.decision, ApprovalDecision):
            raise TypeError("decision must be an ApprovalDecision.")
        if not self.approver.strip():
            raise ValueError("approver must not be empty.")
        if not isinstance(self.decided_at, datetime):
            raise TypeError("decided_at must be a datetime.")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason must not be empty when provided.")

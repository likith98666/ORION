from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class AuthorizationDecision(str, Enum):
    """Possible outcomes of an ORION security authorization check."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class SecurityContext:
    """Trusted execution context used during security decisions."""

    agent_id: UUID
    task_id: UUID | None = None
    execution_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, UUID):
            raise TypeError("agent_id must be a UUID.")

        if self.task_id is not None and not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID or None.")

        if self.execution_id is not None and not isinstance(self.execution_id, UUID):
            raise TypeError("execution_id must be a UUID or None.")


@dataclass(frozen=True)
class AuthorizationRequest:
    """Request to authorize a security-sensitive ORION operation."""

    context: SecurityContext
    resource: str
    action: str

    def __post_init__(self) -> None:
        resource = self.resource.strip()
        action = self.action.strip()

        if not resource:
            raise ValueError("Authorization resource cannot be empty.")

        if not action:
            raise ValueError("Authorization action cannot be empty.")

        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "action", action)


@dataclass(frozen=True)
class AuthorizationResult:
    """Auditable result of an ORION authorization decision."""

    decision: AuthorizationDecision
    reason: str

    def __post_init__(self) -> None:
        reason = self.reason.strip()

        if not reason:
            raise ValueError("Authorization reason cannot be empty.")

        object.__setattr__(self, "reason", reason)

    @property
    def allowed(self) -> bool:
        """Return whether the authorization decision permits execution."""
        return self.decision == AuthorizationDecision.ALLOW

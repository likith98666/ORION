from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class PolicyAction(str, Enum):
    """Action outcome decided by the Policy Engine."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    MODIFY = "modify"


class PolicyEffect(str, Enum):
    """Effect applied when a policy rule matches."""

    PERMIT = "permit"
    FORBID = "forbid"
    CHALLENGE = "challenge"
    SANITIZE = "sanitize"


class PolicyRiskTier(str, Enum):
    """Risk tier assessed for policy context."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def level(self) -> int:
        levels = {
            PolicyRiskTier.LOW: 1,
            PolicyRiskTier.MEDIUM: 2,
            PolicyRiskTier.HIGH: 3,
            PolicyRiskTier.CRITICAL: 4,
        }
        return levels[self]


@dataclass(frozen=True)
class PolicyContext:
    """Execution context evaluated against security and operational policies."""

    subject: str
    action: str
    resource: str
    tenant_id: str = "default"
    environment: str = "sandbox"
    risk_tier: PolicyRiskTier = PolicyRiskTier.LOW
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("Policy subject cannot be empty.")
        if not self.action.strip():
            raise ValueError("Policy action cannot be empty.")
        if not self.resource.strip():
            raise ValueError("Policy resource cannot be empty.")


@dataclass
class PolicyRule:
    """Security or operational rule enforced by the Policy Engine."""

    rule_id: str
    name: str
    description: str
    effect: PolicyEffect
    priority: int = 100
    enabled: bool = True
    subjects: tuple[str, ...] = field(default_factory=tuple)
    actions: tuple[str, ...] = field(default_factory=tuple)
    resource_patterns: tuple[str, ...] = field(default_factory=tuple)
    forbidden_payload_patterns: tuple[str, ...] = field(default_factory=tuple)
    min_risk_tier: PolicyRiskTier | None = None
    environments: tuple[str, ...] = field(default_factory=tuple)
    modifications: dict[str, Any] | None = None
    reason: str = "Policy rule matched"

    def matches(self, context: PolicyContext) -> bool:
        """Evaluate whether this rule matches the supplied context."""
        if not self.enabled:
            return False

        if self.environments and context.environment not in self.environments:
            return False

        if self.subjects and context.subject not in self.subjects:
            return False

        if self.actions and context.action not in self.actions:
            return False

        if self.min_risk_tier and context.risk_tier.level < self.min_risk_tier.level:
            return False

        if self.resource_patterns:
            matched_resource = False
            for pat in self.resource_patterns:
                if re.search(pat, context.resource, re.IGNORECASE):
                    matched_resource = True
                    break
            if not matched_resource:
                return False

        if self.forbidden_payload_patterns:
            matched_payload = False
            payload_str = str(context.parameters)
            for pat in self.forbidden_payload_patterns:
                if re.search(pat, payload_str, re.IGNORECASE):
                    matched_payload = True
                    break
            if not matched_payload:
                return False

        return True


@dataclass(frozen=True)
class PolicyDecision:
    """Immutable record of an evaluated policy decision."""

    decision: PolicyAction
    allowed: bool
    requires_approval: bool
    reason: str
    evaluation_context: PolicyContext
    rule_id: str | None = None
    modified_parameters: dict[str, Any] | None = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    audit_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "decision": self.decision.value,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "modified_parameters": self.modified_parameters,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "subject": self.evaluation_context.subject,
                "action": self.evaluation_context.action,
                "resource": self.evaluation_context.resource,
                "tenant_id": self.evaluation_context.tenant_id,
                "environment": self.evaluation_context.environment,
                "risk_tier": self.evaluation_context.risk_tier.value,
                "parameters": self.evaluation_context.parameters,
                "metadata": self.evaluation_context.metadata,
            },
        }

from dataclasses import dataclass

from orion.core.security.models import AuthorizationDecision
from orion.core.security.risk import ToolRiskLevel


@dataclass(frozen=True)
class ToolRiskPolicy:
    """Immutable policy mapping tool risk levels to security decisions."""

    low_decision: AuthorizationDecision = AuthorizationDecision.ALLOW
    medium_decision: AuthorizationDecision = AuthorizationDecision.ALLOW
    high_decision: AuthorizationDecision = AuthorizationDecision.REQUIRE_APPROVAL
    critical_decision: AuthorizationDecision = AuthorizationDecision.REQUIRE_APPROVAL

    def decide(self, risk_level: ToolRiskLevel) -> AuthorizationDecision:
        """Return the security decision associated with a tool risk level."""

        if not isinstance(risk_level, ToolRiskLevel):
            raise TypeError("Risk level must be a ToolRiskLevel.")

        if risk_level == ToolRiskLevel.LOW:
            return self.low_decision

        if risk_level == ToolRiskLevel.MEDIUM:
            return self.medium_decision

        if risk_level == ToolRiskLevel.HIGH:
            return self.high_decision

        if risk_level == ToolRiskLevel.CRITICAL:
            return self.critical_decision

        raise ValueError(f"Unsupported tool risk level: {risk_level!r}")

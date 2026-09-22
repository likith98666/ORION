import pytest

from orion.core.security import AuthorizationDecision, ToolRiskPolicy
from orion.core.tools.risk import ToolRiskLevel


def test_default_low_risk_is_allowed() -> None:
    policy = ToolRiskPolicy()

    assert policy.decide(ToolRiskLevel.LOW) == AuthorizationDecision.ALLOW


def test_default_medium_risk_is_allowed() -> None:
    policy = ToolRiskPolicy()

    assert policy.decide(ToolRiskLevel.MEDIUM) == AuthorizationDecision.ALLOW


def test_default_high_risk_requires_approval() -> None:
    policy = ToolRiskPolicy()

    assert (
        policy.decide(ToolRiskLevel.HIGH)
        == AuthorizationDecision.REQUIRE_APPROVAL
    )


def test_default_critical_risk_requires_approval() -> None:
    policy = ToolRiskPolicy()

    assert (
        policy.decide(ToolRiskLevel.CRITICAL)
        == AuthorizationDecision.REQUIRE_APPROVAL
    )


def test_policy_is_immutable() -> None:
    policy = ToolRiskPolicy()

    with pytest.raises(AttributeError):
        policy.high_decision = AuthorizationDecision.DENY

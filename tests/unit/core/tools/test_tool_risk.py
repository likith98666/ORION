import pytest

from orion.core.agents.permissions import AgentPermission
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition


def _tool(**overrides) -> ToolDefinition:
    values = {
        "name": "test_tool",
        "description": "Test tool.",
        "permission": AgentPermission.WEB_ACCESS,
        "handler": lambda arguments: arguments,
    }
    values.update(overrides)
    return ToolDefinition(**values)


def test_tool_defaults_to_low_risk() -> None:
    tool = _tool()

    assert tool.risk_level == ToolRiskLevel.LOW


def test_tool_accepts_each_risk_level() -> None:
    for risk_level in ToolRiskLevel:
        tool = _tool(risk_level=risk_level)

        assert tool.risk_level == risk_level


def test_tool_rejects_invalid_risk_level() -> None:
    with pytest.raises(TypeError, match="Tool risk level"):
        _tool(risk_level="high")


def test_risk_levels_have_ordered_severity() -> None:
    assert ToolRiskLevel.LOW < ToolRiskLevel.MEDIUM
    assert ToolRiskLevel.MEDIUM < ToolRiskLevel.HIGH
    assert ToolRiskLevel.HIGH < ToolRiskLevel.CRITICAL

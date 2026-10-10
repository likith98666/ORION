from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.security import AuthorizationDecision, AuthorizationService, ToolRiskPolicy
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry


def _agent() -> Agent:
    return Agent.create(
        name="Risk Test Agent",
        description="Agent used for risk integration tests.",
        capabilities=frozenset({AgentCapability.REASONING}),
        permission_policy=AgentPermissionPolicy.create(
            frozenset({AgentPermission.WEB_ACCESS}),
        ),
    )


def _registry(risk_level: ToolRiskLevel) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="risk_tool",
            description="Tool used for risk integration testing.",
            permission=AgentPermission.WEB_ACCESS,
            handler=lambda arguments: "executed",
            risk_level=risk_level,
        )
    )
    return registry


def test_low_risk_tool_executes() -> None:
    result = ToolExecutor(
        _registry(ToolRiskLevel.LOW),
    ).execute(
        agent=_agent(),
        tool_name="risk_tool",
        arguments={},
    )

    assert result.success is True
    assert result.output == "executed"


def test_high_risk_tool_is_blocked_until_approval() -> None:
    result = None

    try:
        result = ToolExecutor(
            _registry(ToolRiskLevel.HIGH),
        ).execute(
            agent=_agent(),
            tool_name="risk_tool",
            arguments={},
        )
    except PermissionError as exc:
        assert "requires approval" in str(exc)
    else:
        raise AssertionError(f"Expected approval requirement, got result: {result!r}")


def test_injected_risk_policy_controls_execution() -> None:
    policy = ToolRiskPolicy(
        low_decision=AuthorizationDecision.DENY,
    )

    executor = ToolExecutor(
        _registry(ToolRiskLevel.LOW),
        authorization_service=AuthorizationService(
            risk_policy=policy,
        ),
    )

    try:
        executor.execute(
            agent=_agent(),
            tool_name="risk_tool",
            arguments={},
        )
    except PermissionError as exc:
        assert "denied by the risk policy" in str(exc)
    else:
        raise AssertionError("Expected the risk policy to deny execution.")

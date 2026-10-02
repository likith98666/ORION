from __future__ import annotations

import copy
import threading

from orion.core.policy.models import (
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEffect,
    PolicyRiskTier,
    PolicyRule,
)


def get_default_security_rules() -> list[PolicyRule]:
    """Generate default ORION security hardening and guardrail rules."""
    return [
        PolicyRule(
            rule_id="RULE-SEC-001",
            name="Block Credential and Secret Access",
            description=(
                "Blocks unauthorized access or exfiltration of credential, "
                "key, and password files."
            ),
            effect=PolicyEffect.FORBID,
            priority=10,
            enabled=True,
            resource_patterns=(
                r"(\.env|\.aws/credentials|id_rsa|id_ed25519|/etc/passwd|"
                r"/etc/shadow|credentials\.json|\.secret|serviceaccount|secrets/)",
            ),
            reason="Access to sensitive credential and secret files is strictly prohibited.",
        ),
        PolicyRule(
            rule_id="RULE-SEC-002",
            name="Block Catastrophic Shell Execution",
            description=(
                "Blocks system-destructive shell commands such as root-level "
                "file deletion or formatting."
            ),
            effect=PolicyEffect.FORBID,
            priority=10,
            enabled=True,
            actions=("execute_command", "shell_execute", "run_terminal"),
            forbidden_payload_patterns=(
                r"rm\s+-rf\s+[/~]",
                r":\(\)\s*\{",
                r"mkfs\.",
                r"dd\s+if=/dev/zero",
                r"format\s+[a-zA-Z]:",
                r"chmod\s+-R\s+777\s+/",
            ),
            reason="Destructive command pattern identified and blocked by security guardrails.",
        ),
        PolicyRule(
            rule_id="RULE-SEC-003",
            name="Adversarial Prompt Injection Defense",
            description=(
                "Detects and blocks known prompt injection and instruction "
                "override attempts."
            ),
            effect=PolicyEffect.FORBID,
            priority=15,
            enabled=True,
            forbidden_payload_patterns=(
                r"ignore\s+(all\s+)?previous\s+instructions",
                r"system\s+(prompt\s+)?override",
                r"you\s+are\s+now\s+in\s+DAN\s+mode",
                r"bypass\s+(all\s+)?safety\s+filter",
                r"reveal\s+(your\s+)?system\s+instructions",
            ),
            reason="Adversarial prompt injection pattern detected and neutralized.",
        ),
        PolicyRule(
            rule_id="RULE-SEC-004",
            name="Block Metadata Service SSRF",
            description=(
                "Prevents server-side request forgery targeting cloud instance "
                "metadata endpoints."
            ),
            effect=PolicyEffect.FORBID,
            priority=20,
            enabled=True,
            actions=("network_request", "http_request", "fetch_url"),
            resource_patterns=(
                r"169\.254\.169\.254",
                r"metadata\.google\.internal",
                r"100\.100\.100\.200",
            ),
            reason="Network request to cloud instance metadata service blocked (SSRF defense).",
        ),
        PolicyRule(
            rule_id="RULE-SEC-005",
            name="Production Destructive Database Safeguard",
            description=(
                "Requires explicit human approval for destructive database "
                "actions in production."
            ),
            effect=PolicyEffect.CHALLENGE,
            priority=25,
            enabled=True,
            environments=("production", "staging"),
            actions=("db_query", "sql_execute", "database_migration"),
            forbidden_payload_patterns=(
                r"DROP\s+DATABASE",
                r"DROP\s+TABLE",
                r"TRUNCATE\s+TABLE",
            ),
            reason=(
                "Destructive database operations in production require explicit "
                "human authorization."
            ),
        ),
        PolicyRule(
            rule_id="RULE-SEC-006",
            name="Mandatory Approval for Critical Risk Operations",
            description=(
                "Ensures all operations evaluated at critical risk tier "
                "require human operator approval."
            ),
            effect=PolicyEffect.CHALLENGE,
            priority=50,
            enabled=True,
            min_risk_tier=PolicyRiskTier.CRITICAL,
            reason=(
                "Action classified at CRITICAL risk tier; mandatory operator "
                "authorization required."
            ),
        ),
    ]


class PolicyEngine:
    """Central policy evaluation engine enforcing security, permissions, and guardrails."""

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        default_action: PolicyAction = PolicyAction.ALLOW,
    ) -> None:
        self._lock = threading.RLock()
        self._default_action = default_action
        self._rules: dict[str, PolicyRule] = {}
        self._decision_history: list[PolicyDecision] = []

        initial_rules = rules if rules is not None else get_default_security_rules()
        for rule in initial_rules:
            self._rules[rule.rule_id] = rule

    def add_rule(self, rule: PolicyRule) -> None:
        """Add or update an operational or security policy rule."""
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if removed, False if not found."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def get_rule(self, rule_id: str) -> PolicyRule | None:
        """Retrieve a rule by ID."""
        with self._lock:
            return self._rules.get(rule_id)

    def list_rules(self) -> list[PolicyRule]:
        """List all policy rules sorted by priority (lowest integer first)."""
        with self._lock:
            return sorted(self._rules.values(), key=lambda r: r.priority)

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate a context against registered policy rules in priority order."""
        with self._lock:
            sorted_rules = self.list_rules()

            for rule in sorted_rules:
                if rule.matches(context):
                    if rule.effect == PolicyEffect.FORBID:
                        decision = PolicyDecision(
                            decision=PolicyAction.DENY,
                            allowed=False,
                            requires_approval=False,
                            reason=rule.reason,
                            evaluation_context=context,
                            rule_id=rule.rule_id,
                        )
                        self._record_decision(decision)
                        return decision

                    elif rule.effect == PolicyEffect.CHALLENGE:
                        decision = PolicyDecision(
                            decision=PolicyAction.REQUIRE_APPROVAL,
                            allowed=False,
                            requires_approval=True,
                            reason=rule.reason,
                            evaluation_context=context,
                            rule_id=rule.rule_id,
                        )
                        self._record_decision(decision)
                        return decision

                    elif rule.effect == PolicyEffect.SANITIZE:
                        modified_params = copy.deepcopy(context.parameters)
                        if rule.modifications:
                            modified_params.update(rule.modifications)

                        decision = PolicyDecision(
                            decision=PolicyAction.MODIFY,
                            allowed=True,
                            requires_approval=False,
                            reason=rule.reason,
                            evaluation_context=context,
                            rule_id=rule.rule_id,
                            modified_parameters=modified_params,
                        )
                        self._record_decision(decision)
                        return decision

                    elif rule.effect == PolicyEffect.PERMIT:
                        decision = PolicyDecision(
                            decision=PolicyAction.ALLOW,
                            allowed=True,
                            requires_approval=False,
                            reason=rule.reason,
                            evaluation_context=context,
                            rule_id=rule.rule_id,
                        )
                        self._record_decision(decision)
                        return decision

            # Default outcome when no specific rule triggered
            allowed = self._default_action == PolicyAction.ALLOW
            req_approval = self._default_action == PolicyAction.REQUIRE_APPROVAL
            default_decision = PolicyDecision(
                decision=self._default_action,
                allowed=allowed,
                requires_approval=req_approval,
                reason="Default policy action applied (no matching rule).",
                evaluation_context=context,
                rule_id=None,
            )
            self._record_decision(default_decision)
            return default_decision

    def get_decision_history(self, limit: int = 100) -> list[PolicyDecision]:
        """Return the most recent policy evaluation decisions."""
        with self._lock:
            return list(self._decision_history[-limit:])

    def clear_history(self) -> None:
        """Clear decision history log."""
        with self._lock:
            self._decision_history.clear()

    def _record_decision(self, decision: PolicyDecision) -> None:
        self._decision_history.append(decision)
        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-1000:]

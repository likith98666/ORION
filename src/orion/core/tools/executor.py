from dataclasses import dataclass
from typing import Any
from uuid import UUID

from orion.core.agents.models import Agent
from orion.core.policy import (
    PolicyAction,
    PolicyContext,
    PolicyEngine,
    PolicyRiskTier,
)
from orion.core.security import (
    ApprovalRequiredError,
    ApprovalService,
    AuditEventType,
    AuditService,
    AuthorizationRequest,
    AuthorizationService,
    SecretProvider,
    SecretReference,
    SecurityContext,
)
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.execution_repository import ToolExecutionRepository
from orion.core.tools.executions import ToolExecution, ToolExecutionStatus
from orion.core.tools.input_schema import ToolInputType
from orion.core.tools.input_validator import ToolInputValidator
from orion.core.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result of executing a registered ORION tool."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    execution_id: UUID | None = None


class ToolExecutor:
    """Executes registered tools with validation, authorization, and approval."""

    def __init__(
        self,
        registry: ToolRegistry,
        execution_repository: ToolExecutionRepository | None = None,
        authorization_service: AuthorizationService | None = None,
        input_validator: ToolInputValidator | None = None,
        secret_provider: SecretProvider | None = None,
        approval_service: ApprovalService | None = None,
        audit_service: AuditService | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self._registry = registry
        self._execution_repository = execution_repository
        self._authorization_service = authorization_service or AuthorizationService()
        self._input_validator = input_validator or ToolInputValidator()
        self._secret_provider = secret_provider
        self._approval_service = approval_service
        self._audit_service = audit_service
        self._policy_engine = policy_engine

    @property
    def approval_service(self) -> ApprovalService | None:
        """Return configured ApprovalService, if any."""
        return self._approval_service

    def execute(
        self,
        agent: Agent,
        tool_name: str,
        arguments: dict[str, Any],
        execution_id: UUID | None = None,
        approval_id: UUID | None = None,
    ) -> ToolExecutionResult:
        """Validate, authorize, approve, persist, resolve secrets, and execute."""

        tool = self._registry.get(tool_name)

        if tool is None:
            raise ValueError(f"Tool '{tool_name}' was not found.")

        if tool.input_schema is not None:
            self._input_validator.validate(
                arguments=arguments,
                schema=tool.input_schema,
            )

        request = AuthorizationRequest(
            context=SecurityContext(
                agent_id=agent.id,
                execution_id=execution_id,
            ),
            resource=tool.name,
            action="execute",
        )

        authorization = self._authorization_service.authorize(
            agent=agent,
            request=request,
            required_permission=tool.permission,
            risk_level=tool.risk_level,
        )

        if authorization.decision.value == "require_approval":
            self._handle_required_approval(
                agent=agent,
                tool_name=tool.name,
                execution_id=execution_id,
                risk_level=tool.risk_level,
                approval_id=approval_id,
            )
        elif not authorization.allowed:
            raise PermissionError(authorization.reason)

        if self._policy_engine is not None:
            risk_tier_map = {
                ToolRiskLevel.LOW: PolicyRiskTier.LOW,
                ToolRiskLevel.MEDIUM: PolicyRiskTier.MEDIUM,
                ToolRiskLevel.HIGH: PolicyRiskTier.HIGH,
                ToolRiskLevel.CRITICAL: PolicyRiskTier.CRITICAL,
            }
            rt = risk_tier_map.get(tool.risk_level, PolicyRiskTier.LOW)
            pol_ctx = PolicyContext(
                subject=agent.name,
                action="execute_tool",
                resource=tool.name,
                risk_tier=rt,
                parameters=arguments,
            )
            policy_decision = self._policy_engine.evaluate(pol_ctx)
            if policy_decision.decision == PolicyAction.DENY:
                raise PermissionError(f"Policy Engine denied execution: {policy_decision.reason}")
            elif policy_decision.decision == PolicyAction.REQUIRE_APPROVAL:
                self._handle_required_approval(
                    agent=agent,
                    tool_name=tool.name,
                    execution_id=execution_id,
                    risk_level=tool.risk_level,
                    approval_id=approval_id,
                )
            elif (
                policy_decision.decision == PolicyAction.MODIFY
                and policy_decision.modified_parameters is not None
            ):
                arguments = policy_decision.modified_parameters

        lifecycle = None

        if self._execution_repository is not None:
            lifecycle = ToolExecution.create(
                tool_name=tool.name,
                agent_id=agent.id,
                arguments=arguments,
                execution_id=execution_id,
            )

            self._execution_repository.save(lifecycle)

            lifecycle.status = ToolExecutionStatus.RUNNING
            self._execution_repository.save(lifecycle)

        audit_execution_id = execution_id

        self._record_audit(
            AuditEventType.TOOL_EXECUTION_STARTED,
            agent=agent,
            execution_id=audit_execution_id,
            tool_name=tool.name,
            outcome="started",
            details={"arguments": arguments},
        )

        try:
            resolved_arguments = self._resolve_secret_arguments(
                arguments=arguments,
                schema=tool.input_schema,
            )

            output = tool.handler(resolved_arguments)

        except Exception as exc:
            error = str(exc)

            if lifecycle is not None and self._execution_repository is not None:
                lifecycle.status = ToolExecutionStatus.FAILED
                lifecycle.error = self._redact(error)
                self._execution_repository.save(lifecycle)

            self._record_audit(
                AuditEventType.TOOL_EXECUTION_FAILED,
                agent=agent,
                execution_id=audit_execution_id,
                tool_name=tool.name,
                risk_level=tool.risk_level,
                outcome="failed",
                details={"error": error},
            )

            return ToolExecutionResult(
                tool_name=tool.name,
                success=False,
                error=error,
                execution_id=lifecycle.id if lifecycle else None,
            )

        if lifecycle is not None and self._execution_repository is not None:
            lifecycle.status = ToolExecutionStatus.COMPLETED
            lifecycle.output = self._redact(output)
            self._execution_repository.save(lifecycle)

        self._record_audit(
            AuditEventType.TOOL_EXECUTION_COMPLETED,
            agent=agent,
            execution_id=audit_execution_id,
            tool_name=tool.name,
            risk_level=tool.risk_level,
            outcome="completed",
            details={"output": output},
        )

        return ToolExecutionResult(
            tool_name=tool.name,
            success=True,
            output=output,
            execution_id=lifecycle.id if lifecycle else None,
        )

    def _record_audit(
        self,
        event_type: AuditEventType,
        *,
        agent: Agent,
        execution_id: UUID | None,
        tool_name: str,
        outcome: str,
        details: dict[str, Any],
        risk_level: ToolRiskLevel | None = None,
    ) -> None:
        if self._audit_service is None:
            return

        self._audit_service.record(
            event_type,
            agent_id=agent.id,
            execution_id=execution_id,
            tool_name=tool_name,
            action="execute",
            risk_level=risk_level,
            outcome=outcome,
            details=details,
        )

    def _redact(self, value: Any) -> Any:
        if self._audit_service is None:
            return value

        return self._audit_service.redact(value)

    def _handle_required_approval(
        self,
        agent: Agent,
        tool_name: str,
        execution_id: UUID | None,
        risk_level: ToolRiskLevel,
        approval_id: UUID | None,
    ) -> None:
        """Enforce approval before a high-risk tool can execute."""

        if self._approval_service is None:
            raise PermissionError(f"Tool '{tool_name}' requires approval before execution.")

        if approval_id is None:
            request = self._approval_service.create_request(
                agent_id=agent.id,
                execution_id=execution_id,
                tool_name=tool_name,
                action="execute",
                risk_level=risk_level,
            )

            raise ApprovalRequiredError(request_id=request.id)

        self._approval_service.validate_approval(
            request_id=approval_id,
            agent_id=agent.id,
            execution_id=execution_id,
            tool_name=tool_name,
            action="execute",
            risk_level=risk_level,
        )

        self._approval_service.consume_approval(request_id=approval_id)

    def _resolve_secret_arguments(
        self,
        arguments: dict[str, Any],
        schema: Any,
    ) -> dict[str, Any]:
        """Resolve declared secret references in an isolated argument copy."""

        if schema is None:
            return dict(arguments)

        resolved = dict(arguments)
        fields = {field.name: field for field in schema.fields}

        for name, field in fields.items():
            if field.input_type != ToolInputType.SECRET_REFERENCE:
                continue

            if name not in resolved or resolved[name] is None:
                continue

            reference = resolved[name]

            if not isinstance(reference, SecretReference):
                raise TypeError(f"Tool argument '{name}' must contain a SecretReference.")

            if self._secret_provider is None:
                raise RuntimeError("A SecretProvider is required for secret-backed tool arguments.")

            secret = self._secret_provider.get(reference)

            if self._audit_service is not None:
                self._audit_service.register_secret(secret)

            resolved[name] = secret

        return resolved

from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_context import RecoveryContext
from orion.core.recovery.recovery_strategy import (
    RecoveryDecision,
    RecoveryStrategy,
)


class RecoveryEngine:
    """Selects a controlled recovery strategy for a classified failure."""

    _STRATEGY_BY_FAILURE_TYPE = {
        FailureType.AGENT_FAILURE: RecoveryStrategy.CHANGE_AGENT,
        FailureType.MODEL_FAILURE: RecoveryStrategy.CHANGE_MODEL,
        FailureType.TOOL_FAILURE: RecoveryStrategy.CHANGE_TOOL,
        FailureType.DEPENDENCY_FAILURE: RecoveryStrategy.CHANGE_TASK_ORDER,
        FailureType.INVALID_INPUT: RecoveryStrategy.MODIFY_TASK,
        FailureType.CONSTRAINT_VIOLATION: RecoveryStrategy.MODIFY_TASK,
        FailureType.SECURITY_BLOCK: RecoveryStrategy.ESCALATE_TO_HUMAN,
        FailureType.BUDGET_EXCEEDED: RecoveryStrategy.CHANGE_MODEL,
        FailureType.TIMEOUT: RecoveryStrategy.RETRY_CURRENT_TASK,
        FailureType.VERIFICATION_FAILURE: RecoveryStrategy.MODIFY_TASK,
        FailureType.UNKNOWN: RecoveryStrategy.ESCALATE_TO_HUMAN,
    }

    _HUMAN_REQUIRED_FAILURE_TYPES = {
        FailureType.SECURITY_BLOCK,
        FailureType.UNKNOWN,
    }

    def decide(
        self,
        failure: Failure,
        context: RecoveryContext | None = None,
    ) -> RecoveryDecision:
        """Select a recovery strategy using failure and execution context."""

        if not isinstance(failure, Failure):
            raise TypeError("failure must be a Failure instance.")

        if context is None:
            return self._decide_without_context(failure)

        if not isinstance(context, RecoveryContext):
            raise TypeError("context must be a RecoveryContext instance.")

        strategy = self._decide_with_context(failure, context)
        requires_human = strategy == RecoveryStrategy.ESCALATE_TO_HUMAN

        return RecoveryDecision(
            strategy=strategy,
            reason=self._build_reason(failure, context, strategy),
            requires_human=requires_human,
        )

    def _decide_without_context(self, failure: Failure) -> RecoveryDecision:
        """Apply the original failure-to-strategy mapping."""

        strategy = self._STRATEGY_BY_FAILURE_TYPE[failure.failure_type]
        requires_human = (
            failure.failure_type in self._HUMAN_REQUIRED_FAILURE_TYPES
        )

        return RecoveryDecision(
            strategy=strategy,
            reason=(
                f"Failure classified as "
                f"'{failure.failure_type.value}': {failure.message}"
            ),
            requires_human=requires_human,
        )

    def _decide_with_context(
        self,
        failure: Failure,
        context: RecoveryContext,
    ) -> RecoveryStrategy:
        """Select a strategy using available recovery options and limits."""

        if failure.failure_type == FailureType.SECURITY_BLOCK:
            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.UNKNOWN:
            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.TIMEOUT:
            if context.retry_count < context.max_retries:
                return RecoveryStrategy.RETRY_CURRENT_TASK

            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.AGENT_FAILURE:
            if context.alternative_agents_available:
                return RecoveryStrategy.CHANGE_AGENT

            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.TOOL_FAILURE:
            if context.alternative_tools_available:
                return RecoveryStrategy.CHANGE_TOOL

            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.MODEL_FAILURE:
            if context.alternative_models_available:
                return RecoveryStrategy.CHANGE_MODEL

            return RecoveryStrategy.ESCALATE_TO_HUMAN

        if failure.failure_type == FailureType.BUDGET_EXCEEDED:
            return RecoveryStrategy.CHANGE_MODEL

        if failure.failure_type == FailureType.DEPENDENCY_FAILURE:
            return RecoveryStrategy.CHANGE_TASK_ORDER

        if failure.failure_type in {
            FailureType.INVALID_INPUT,
            FailureType.CONSTRAINT_VIOLATION,
            FailureType.VERIFICATION_FAILURE,
        }:
            return RecoveryStrategy.MODIFY_TASK

        return RecoveryStrategy.ESCALATE_TO_HUMAN

    def _build_reason(
        self,
        failure: Failure,
        context: RecoveryContext,
        strategy: RecoveryStrategy,
    ) -> str:
        """Build an auditable explanation for the recovery decision."""

        return (
            f"Failure classified as '{failure.failure_type.value}': "
            f"{failure.message}. "
            f"Recovery strategy: '{strategy.value}'. "
            f"Retry count: {context.retry_count}/{context.max_retries}. "
            f"Alternative agent: {context.alternative_agents_available}. "
            f"Alternative tool: {context.alternative_tools_available}. "
            f"Alternative model: {context.alternative_models_available}. "
            f"Remaining budget: {context.remaining_budget}. "
            f"Remaining time: {context.remaining_time_ms} ms."
        )

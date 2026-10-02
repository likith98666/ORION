from dataclasses import dataclass

from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.recovery.failures import Failure
from orion.core.recovery.recovery_action import RecoveryAction
from orion.core.recovery.recovery_context import RecoveryContext
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.recovery.recovery_strategy import RecoveryDecision


@dataclass(frozen=True)
class RecoveryResult:
    """Result produced when ORION analyzes a failed execution."""

    failure: Failure
    decision: RecoveryDecision
    action: RecoveryAction


class RecoveryCoordinator:
    """Coordinates failed executions with the recovery decision engine."""

    def __init__(
        self,
        recovery_engine: RecoveryEngine | None = None,
    ) -> None:
        self._recovery_engine = recovery_engine or RecoveryEngine()

    def handle_failure(
        self,
        execution: AgentExecution,
        *,
        execution_context: RecoveryExecutionContext | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
        task_criticality: float = 0.5,
        alternative_agents_available: bool = False,
        alternative_tools_available: bool = False,
        alternative_models_available: bool = False,
        remaining_budget: float = 0.0,
        remaining_time_ms: float = 0.0,
    ) -> RecoveryResult:
        """Analyze a failed execution and produce a recovery action."""

        if not isinstance(execution, AgentExecution):
            raise TypeError(
                "execution must be an AgentExecution instance."
            )

        if execution.status != AgentExecutionStatus.FAILED:
            raise ValueError(
                "Recovery can only be initiated for failed executions."
            )

        if execution.failure is None:
            raise ValueError(
                "Failed execution must contain a structured failure."
            )

        if execution_context is not None and not isinstance(
            execution_context,
            RecoveryExecutionContext,
        ):
            raise TypeError(
                "execution_context must be a "
                "RecoveryExecutionContext instance."
            )

        failure = execution.failure

        if execution_context is not None:
            if execution_context.current_execution_id != execution.id:
                raise ValueError(
                    "Recovery execution context does not match "
                    "the failed execution."
                )

            if execution_context.task_id != execution.agent_task_id:
                raise ValueError(
                    "Recovery execution context does not match "
                    "the execution task."
                )

            retry_count = execution_context.recovery_attempt_number

        context = RecoveryContext(
            retry_count=retry_count,
            max_retries=max_retries,
            task_criticality=task_criticality,
            alternative_agents_available=alternative_agents_available,
            alternative_tools_available=alternative_tools_available,
            alternative_models_available=alternative_models_available,
            remaining_budget=remaining_budget,
            remaining_time_ms=remaining_time_ms,
        )

        decision = self._recovery_engine.decide(
            failure,
            context,
        )

        action = RecoveryAction.from_strategy(
            decision.strategy,
        )

        return RecoveryResult(
            failure=failure,
            decision=decision,
            action=action,
        )

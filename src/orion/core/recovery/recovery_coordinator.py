from dataclasses import dataclass

from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure
from orion.core.recovery.recovery_action import RecoveryAction
from orion.core.recovery.recovery_context import RecoveryContext
from orion.core.recovery.recovery_engine import RecoveryEngine


@dataclass(frozen=True)
class RecoveryResult:
    """Result produced when ORION analyzes a failed execution."""

    failure: Failure
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

        failure = execution.failure

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
            action=action,
        )

from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure
from orion.core.recovery.recovery_strategy import RecoveryDecision


@dataclass(frozen=True)
class RecoveryExecutionContext:
    """Tracks the state and history of a task's recovery lifecycle."""

    task_id: UUID
    current_execution_id: UUID
    attempt_number: int = 1
    recovery_attempt_number: int = 0
    failure_history: tuple[Failure, ...] = ()
    recovery_history: tuple[RecoveryDecision, ...] = ()

    @classmethod
    def from_execution(
        cls,
        execution: AgentExecution,
    ) -> "RecoveryExecutionContext":
        """Create an initial recovery context from an execution."""

        if not isinstance(execution, AgentExecution):
            raise TypeError(
                "execution must be an AgentExecution instance."
            )

        failure_history: tuple[Failure, ...] = ()

        if execution.failure is not None:
            failure_history = (execution.failure,)

        return cls(
            task_id=execution.agent_task_id,
            current_execution_id=execution.id,
            failure_history=failure_history,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID.")

        if not isinstance(self.current_execution_id, UUID):
            raise TypeError("current_execution_id must be a UUID.")

        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1.")

        if self.recovery_attempt_number < 0:
            raise ValueError(
                "recovery_attempt_number cannot be negative."
            )

        if self.recovery_attempt_number > self.attempt_number - 1:
            raise ValueError(
                "recovery_attempt_number cannot exceed completed attempts."
            )

        if not isinstance(self.failure_history, tuple):
            raise TypeError("failure_history must be a tuple.")

        if not isinstance(self.recovery_history, tuple):
            raise TypeError("recovery_history must be a tuple.")

        if any(
            not isinstance(failure, Failure)
            for failure in self.failure_history
        ):
            raise TypeError(
                "failure_history must contain only Failure instances."
            )

        if any(
            not isinstance(decision, RecoveryDecision)
            for decision in self.recovery_history
        ):
            raise TypeError(
                "recovery_history must contain only RecoveryDecision instances."
            )

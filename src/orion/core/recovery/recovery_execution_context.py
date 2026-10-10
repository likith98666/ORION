from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.executions import AgentExecution
from orion.core.recovery.failures import Failure
from orion.core.recovery.recovery_strategy import (
    RecoveryDecision,
)


@dataclass(frozen=True)
class RecoveryExecutionContext:
    task_id: UUID
    current_execution_id: UUID
    attempt_number: int = 1
    recovery_attempt_number: int = 0
    failure_history: tuple[Failure, ...] = ()
    recovery_history: tuple[RecoveryDecision, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID")

        if not isinstance(self.current_execution_id, UUID):
            raise TypeError("current_execution_id must be a UUID")

        if not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")

        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")

        if not isinstance(self.recovery_attempt_number, int):
            raise TypeError("recovery_attempt_number must be an integer")

        if self.recovery_attempt_number < 0:
            raise ValueError("recovery_attempt_number cannot be negative")

        if self.recovery_attempt_number > self.attempt_number - 1:
            raise ValueError("recovery_attempt_number cannot exceed completed attempts")

        if not isinstance(self.failure_history, tuple):
            raise TypeError("failure_history must be a tuple")

        if not all(isinstance(failure, Failure) for failure in self.failure_history):
            raise TypeError("failure_history must contain only Failure instances")

        if not isinstance(self.recovery_history, tuple):
            raise TypeError("recovery_history must be a tuple")

        if not all(isinstance(decision, RecoveryDecision) for decision in self.recovery_history):
            raise TypeError("recovery_history must contain only RecoveryDecision instances")

    @classmethod
    def from_execution(
        cls,
        execution: AgentExecution,
    ) -> "RecoveryExecutionContext":
        if not isinstance(execution, AgentExecution):
            raise TypeError("execution must be an AgentExecution instance")

        failure_history: tuple[Failure, ...] = ()

        if execution.failure is not None:
            failure_history = (execution.failure,)

        return cls(
            task_id=execution.agent_task_id,
            current_execution_id=execution.id,
            attempt_number=1,
            recovery_attempt_number=0,
            failure_history=failure_history,
            recovery_history=(),
        )

    def record_failure(
        self,
        failure: Failure,
    ) -> "RecoveryExecutionContext":
        if not isinstance(failure, Failure):
            raise TypeError("failure must be a Failure instance")

        return RecoveryExecutionContext(
            task_id=self.task_id,
            current_execution_id=self.current_execution_id,
            attempt_number=self.attempt_number,
            recovery_attempt_number=self.recovery_attempt_number,
            failure_history=self.failure_history + (failure,),
            recovery_history=self.recovery_history,
        )

    def record_recovery(
        self,
        decision: RecoveryDecision,
    ) -> "RecoveryExecutionContext":
        if not isinstance(decision, RecoveryDecision):
            raise TypeError("decision must be a RecoveryDecision instance")

        return RecoveryExecutionContext(
            task_id=self.task_id,
            current_execution_id=self.current_execution_id,
            attempt_number=self.attempt_number,
            recovery_attempt_number=self.recovery_attempt_number,
            failure_history=self.failure_history,
            recovery_history=self.recovery_history + (decision,),
        )

    def create_next_attempt(
        self,
        *,
        current_execution_id: UUID,
    ) -> "RecoveryExecutionContext":
        if not isinstance(current_execution_id, UUID):
            raise TypeError("current_execution_id must be a UUID")

        if current_execution_id == self.current_execution_id:
            raise ValueError("current_execution_id must be different from the previous execution")

        return RecoveryExecutionContext(
            task_id=self.task_id,
            current_execution_id=current_execution_id,
            attempt_number=self.attempt_number + 1,
            recovery_attempt_number=self.recovery_attempt_number + 1,
            failure_history=self.failure_history,
            recovery_history=self.recovery_history,
        )

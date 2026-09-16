from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator
from orion.core.orchestration.parallel_executor import ParallelExecutor
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext


@dataclass(frozen=True)
class ExecutionLoopResult:
    """Result of executing a collection of assigned agent tasks."""

    executions: tuple[AgentExecution, ...]


class ExecutionLoop:
    """Coordinates execution of assigned agent tasks."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        parallel_executor: ParallelExecutor | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
    ) -> None:
        self._execution_coordinator = execution_coordinator
        self._parallel_executor = parallel_executor
        self._recovery_coordinator = recovery_coordinator

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
    ) -> ExecutionLoopResult:
        """Execute assigned agent tasks."""

        if self._parallel_executor is not None:
            result = self._parallel_executor.execute(
                tasks=tasks,
                model_config=model_config,
            )

            executions = list(result.executions)

            self._handle_failed_executions(executions)

            return ExecutionLoopResult(
                executions=tuple(executions),
            )

        executions: list[AgentExecution] = []

        for task in tasks:
            execution = self._execution_coordinator.execute_task(
                task=task,
                model_config=model_config,
            )
            executions.append(execution)

            self._handle_failed_execution(execution)

        return ExecutionLoopResult(
            executions=tuple(executions),
        )

    def _handle_failed_executions(
        self,
        executions: list[AgentExecution],
    ) -> None:
        """Handle failed executions returned by parallel execution."""

        for execution in executions:
            self._handle_failed_execution(execution)

    def _handle_failed_execution(
        self,
        execution: AgentExecution,
    ) -> None:
        """Send a failed execution to the recovery coordinator."""

        if self._recovery_coordinator is None:
            return

        if execution.status != AgentExecutionStatus.FAILED:
            return

        execution_context = RecoveryExecutionContext.from_execution(
            execution
        )

        self._recovery_coordinator.handle_failure(
            execution=execution,
            execution_context=execution_context,
        )

from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator
from orion.core.orchestration.parallel_executor import ParallelExecutor
from orion.core.orchestration.state_synchronizer import StateSynchronizer
from orion.core.planning.steps import PlanStep
from orion.core.recovery.recovery_action import RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.recovery.recovery_service import RecoveryService


@dataclass(frozen=True)
class ExecutionLoopResult:
    """Result of executing a collection of assigned agent tasks."""

    executions: tuple[AgentExecution, ...]


class ExecutionLoop:
    """Coordinates execution, state synchronization, and recovery."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        parallel_executor: ParallelExecutor | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
        recovery_service: RecoveryService | None = None,
        state_synchronizer: StateSynchronizer | None = None,
    ) -> None:
        self._execution_coordinator = execution_coordinator
        self._parallel_executor = parallel_executor
        self._recovery_coordinator = recovery_coordinator
        self._recovery_service = recovery_service
        self._state_synchronizer = state_synchronizer

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
        plan_steps: list[PlanStep] | None = None,
        alternative_model_configs: tuple[ModelConfig, ...] = (),
    ) -> ExecutionLoopResult:
        """Execute assigned agent tasks with optional recovery alternatives."""

        executions: list[AgentExecution] = []

        if self._parallel_executor is not None:
            result = self._parallel_executor.execute(
                tasks=tasks,
                model_config=model_config,
            )

            executions.extend(result.executions)

            for execution in result.executions:
                task = self._find_task(
                    tasks,
                    execution.agent_task_id,
                )

                self._synchronize_execution(
                    execution=execution,
                    plan_steps=plan_steps,
                )

                recovery_execution = self._handle_failed_execution(
                    execution=execution,
                    task=task,
                    model_config=model_config,
                    alternative_model_configs=alternative_model_configs,
                    plan_steps=plan_steps,
                )

                if recovery_execution is not None:
                    executions.append(recovery_execution)

            return ExecutionLoopResult(
                executions=tuple(executions),
            )

        for task in tasks:
            execution = self._execution_coordinator.execute_task(
                task=task,
                model_config=model_config,
            )

            executions.append(execution)

            self._synchronize_execution(
                execution=execution,
                plan_steps=plan_steps,
            )

            recovery_execution = self._handle_failed_execution(
                execution=execution,
                task=task,
                model_config=model_config,
                alternative_model_configs=alternative_model_configs,
                plan_steps=plan_steps,
            )

            if recovery_execution is not None:
                executions.append(recovery_execution)

        return ExecutionLoopResult(
            executions=tuple(executions),
        )

    def _synchronize_execution(
        self,
        execution: AgentExecution,
        plan_steps: list[PlanStep] | None,
    ) -> None:
        """Synchronize execution state when synchronization is configured."""

        if self._state_synchronizer is None:
            return

        if plan_steps is None:
            raise ValueError(
                "plan_steps are required when state_synchronizer is configured."
            )

        self._state_synchronizer.synchronize(
            execution,
            plan_steps,
        )

    def _handle_failed_execution(
        self,
        execution: AgentExecution,
        task: AgentTask,
        model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...],
        plan_steps: list[PlanStep] | None,
    ) -> AgentExecution | None:
        """Coordinate recovery for a failed execution."""

        if self._recovery_coordinator is None:
            return None

        if execution.status != AgentExecutionStatus.FAILED:
            return None

        execution_context = RecoveryExecutionContext.from_execution(
            execution
        )

        recovery_result = self._recovery_coordinator.handle_failure(
            execution=execution,
            execution_context=execution_context,
        )

        action_type = recovery_result.action.action_type

        if self._recovery_service is None:
            return None

        if action_type not in {
            RecoveryActionType.RETRY_TASK,
            RecoveryActionType.CHANGE_MODEL,
        }:
            return None

        if task.status != AgentTaskStatus.FAILED:
            if self._state_synchronizer is None:
                raise ValueError(
                    "Failed agent task must be synchronized before retry."
                )

            if plan_steps is None:
                raise ValueError(
                    "plan_steps are required before retrying a failed task."
                )

            self._state_synchronizer.synchronize(
                execution,
                plan_steps,
            )

        if action_type == RecoveryActionType.RETRY_TASK:
            return self._recovery_service.retry_task(
                task,
                model_config,
            )

        return self._recovery_service.change_model_and_retry(
            task=task,
            current_model_config=model_config,
            alternative_model_configs=alternative_model_configs,
        )

    @staticmethod
    def _find_task(
        tasks: list[AgentTask],
        task_id,
    ) -> AgentTask:
        """Find the task associated with an execution."""

        for task in tasks:
            if task.id == task_id:
                return task

        raise ValueError(f"Agent task not found: {task_id}")

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
    """Coordinates task execution and bounded iterative recovery."""

    DEFAULT_MAX_RECOVERY_ATTEMPTS = 3

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        parallel_executor: ParallelExecutor | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
        recovery_service: RecoveryService | None = None,
        state_synchronizer: StateSynchronizer | None = None,
        max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    ) -> None:
        if not isinstance(max_recovery_attempts, int):
            raise TypeError("max_recovery_attempts must be an integer.")

        if max_recovery_attempts < 0:
            raise ValueError(
                "max_recovery_attempts cannot be negative."
            )

        self._execution_coordinator = execution_coordinator
        self._parallel_executor = parallel_executor
        self._recovery_coordinator = recovery_coordinator
        self._recovery_service = recovery_service
        self._state_synchronizer = state_synchronizer
        self._max_recovery_attempts = max_recovery_attempts

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
        plan_steps: list[PlanStep] | None = None,
        alternative_model_configs: tuple[ModelConfig, ...] = (),
    ) -> ExecutionLoopResult:
        """Execute tasks and continue through bounded recovery when possible."""

        executions: list[AgentExecution] = []

        if self._parallel_executor is not None:
            result = self._parallel_executor.execute(
                tasks=tasks,
                model_config=model_config,
            )

            for execution in result.executions:
                task = self._find_task(
                    tasks,
                    execution.agent_task_id,
                )

                executions.extend(
                    self._process_execution_with_recovery(
                        execution=execution,
                        task=task,
                        model_config=model_config,
                        alternative_model_configs=alternative_model_configs,
                        plan_steps=plan_steps,
                    )
                )

            return ExecutionLoopResult(
                executions=tuple(executions),
            )

        for task in tasks:
            execution = self._execution_coordinator.execute_task(
                task=task,
                model_config=model_config,
            )

            executions.extend(
                self._process_execution_with_recovery(
                    execution=execution,
                    task=task,
                    model_config=model_config,
                    alternative_model_configs=alternative_model_configs,
                    plan_steps=plan_steps,
                )
            )

        return ExecutionLoopResult(
            executions=tuple(executions),
        )

    def _process_execution_with_recovery(
        self,
        execution: AgentExecution,
        task: AgentTask,
        model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...],
        plan_steps: list[PlanStep] | None,
    ) -> list[AgentExecution]:
        """Process an execution and iteratively apply bounded recovery."""

        executions = [execution]

        self._synchronize_execution(
            execution=execution,
            plan_steps=plan_steps,
        )

        if execution.status != AgentExecutionStatus.FAILED:
            return executions

        if self._recovery_coordinator is None:
            return executions

        if execution.failure is None:
            return executions

        context = RecoveryExecutionContext.from_execution(
            execution
        )

        current_execution = execution
        current_model_config = model_config

        while True:
            if current_execution.status != AgentExecutionStatus.FAILED:
                break

            if current_execution.failure is None:
                break

            if (
                context.recovery_attempt_number
                >= self._max_recovery_attempts
            ):
                break

            recovery_result = self._recovery_coordinator.handle_failure(
                execution=current_execution,
                execution_context=context,
                max_retries=self._max_recovery_attempts,
                alternative_models_available=bool(
                    alternative_model_configs
                ),
            )

            context = context.record_recovery(
                recovery_result.decision
            )

            action_type = recovery_result.action.action_type

            if recovery_result.action.requires_human:
                break

            if self._recovery_service is None:
                break

            if action_type not in {
                RecoveryActionType.RETRY_TASK,
                RecoveryActionType.CHANGE_MODEL,
            }:
                break

            self._synchronize_failed_task_before_retry(
                execution=current_execution,
                task=task,
                plan_steps=plan_steps,
            )

            if action_type == RecoveryActionType.RETRY_TASK:
                next_execution = self._recovery_service.retry_task(
                    task,
                    current_model_config,
                )

            else:
                next_execution = (
                    self._recovery_service.change_model_and_retry(
                        task=task,
                        current_model_config=current_model_config,
                        alternative_model_configs=alternative_model_configs,
                    )
                )

                if next_execution is not None:
                    current_model_config = (
                        self._model_config_after_change(
                            current_model_config=current_model_config,
                            alternative_model_configs=alternative_model_configs,
                        )
                    )

            if next_execution is None:
                break

            executions.append(next_execution)

            context = context.create_next_attempt(
                current_execution_id=next_execution.id,
            )

            current_execution = next_execution

            self._synchronize_execution(
                execution=current_execution,
                plan_steps=plan_steps,
            )

            if current_execution.status != AgentExecutionStatus.FAILED:
                break

            if current_execution.failure is None:
                break

            context = context.record_failure(
                current_execution.failure
            )

        return executions

    @staticmethod
    def _model_config_after_change(
        current_model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...],
    ) -> ModelConfig:
        """Return the selected alternative model configuration."""

        for alternative in alternative_model_configs:
            if (
                alternative.provider_name
                != current_model_config.provider_name
            ):
                return alternative

        return current_model_config

    def _synchronize_failed_task_before_retry(
        self,
        execution: AgentExecution,
        task: AgentTask,
        plan_steps: list[PlanStep] | None,
    ) -> None:
        """Synchronize failed state before retrying when synchronization is configured."""

        if task.status == AgentTaskStatus.FAILED:
            return

        if self._state_synchronizer is None:
            return

        if plan_steps is None:
            raise ValueError(
                "plan_steps are required before retrying a failed task."
            )

        self._state_synchronizer.synchronize(
            execution,
            plan_steps,
        )

    def _synchronize_execution(
        self,
        execution: AgentExecution,
        plan_steps: list[PlanStep] | None,
    ) -> None:
        """Synchronize execution state when a synchronizer is configured."""

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

    @staticmethod
    def _find_task(
        tasks: list[AgentTask],
        task_id,
    ) -> AgentTask:
        """Find the task associated with an execution."""

        for task in tasks:
            if task.id == task_id:
                return task

        raise ValueError(
            f"Agent task not found: {task_id}"
        )

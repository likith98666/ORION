from dataclasses import dataclass
from uuid import UUID

from orion.config.model_config import ModelConfig
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.memory.context_provider import MemoryContextProvider
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.service import MemoryService
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator
from orion.core.orchestration.parallel_executor import ParallelExecutor
from orion.core.orchestration.state_synchronizer import StateSynchronizer
from orion.core.planning.steps import PlanStep
from orion.core.recovery.recovery_action import RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.recovery.recovery_service import RecoveryService
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.failure_adapter import VerificationFailureAdapter
from orion.core.verification.models import VerificationResult, VerificationStatus


@dataclass(frozen=True)
class ExecutionLoopResult:
    """Result of executing a collection of assigned agent tasks."""

    executions: tuple[AgentExecution, ...]


class ExecutionLoop:
    """Coordinates task execution, verification, memory capture, and bounded recovery."""

    DEFAULT_MAX_RECOVERY_ATTEMPTS = 3

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        parallel_executor: ParallelExecutor | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
        recovery_service: RecoveryService | None = None,
        state_synchronizer: StateSynchronizer | None = None,
        memory_service: MemoryService | None = None,
        verification_engine: VerificationEngine | None = None,
        memory_context_provider: MemoryContextProvider | None = None,
        execution_service: AgentExecutionService | None = None,
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
        self._memory_service = memory_service
        self._verification_engine = verification_engine
        self._memory_context_provider = memory_context_provider
        self._execution_service = execution_service or getattr(
            getattr(execution_coordinator, "_agent_executor", None),
            "_execution_service",
            getattr(
                getattr(recovery_service, "_agent_executor", None),
                "_execution_service",
                None,
            ),
        )
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
            memory_contexts = [
                self._provide_memory_context(task)
                for task in tasks
            ]

            result = self._parallel_executor.execute(
                tasks=tasks,
                model_config=model_config,
                memory_contexts=memory_contexts,
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
            memory_context = self._provide_memory_context(task)

            execution = self._execution_coordinator.execute_task(
                task=task,
                model_config=model_config,
                memory_context=memory_context,
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

    def _provide_memory_context(
        self,
        task: AgentTask,
    ) -> ExecutionMemoryContext | None:
        """Provide bounded memory context when memory retrieval is configured."""

        if self._memory_context_provider is None:
            return None

        return self._memory_context_provider.provide(task)

    def _process_execution_with_recovery(
        self,
        execution: AgentExecution,
        task: AgentTask,
        model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...],
        plan_steps: list[PlanStep] | None,
    ) -> list[AgentExecution]:
        """Process an execution, verify output, capture memory, and apply bounded recovery."""

        executions = [execution]

        passed = self._evaluate_execution(
            execution=execution,
            task=task,
            plan_steps=plan_steps,
        )

        if passed:
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

            retry_memory_context = self._provide_memory_context(task)

            if action_type == RecoveryActionType.RETRY_TASK:
                next_execution = self._recovery_service.retry_task(
                    task,
                    current_model_config,
                    memory_context=retry_memory_context,
                )
            else:
                next_execution = (
                    self._recovery_service.change_model_and_retry(
                        task=task,
                        current_model_config=current_model_config,
                        alternative_model_configs=alternative_model_configs,
                        memory_context=retry_memory_context,
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

            retry_passed = self._evaluate_execution(
                execution=current_execution,
                task=task,
                plan_steps=plan_steps,
            )

            if retry_passed:
                break

            if current_execution.failure is None:
                break

            context = context.record_failure(
                current_execution.failure
            )

        return executions

    def _verify_execution(
        self,
        execution: AgentExecution,
        task: AgentTask,
    ) -> VerificationResult | None:
        """Verify execution output when verification is configured."""

        if self._verification_engine is None:
            return None

        if not task.expected_requirements:
            return None

        return self._verification_engine.verify_output(
            execution_id=execution.id,
            output=execution.output,
            expected_requirements=list(task.expected_requirements),
        )

    def _evaluate_execution(
        self,
        execution: AgentExecution,
        task: AgentTask,
        plan_steps: list[PlanStep] | None,
    ) -> bool:
        """Verify execution output, adapt failures if needed, and synchronize state."""

        if execution.status == AgentExecutionStatus.FAILED:
            if execution.runtime_status is None:
                execution.runtime_status = AgentExecutionStatus.FAILED
            self._synchronize_execution(
                execution=execution,
                plan_steps=plan_steps,
            )
            return False

        if execution.runtime_status is None:
            execution.runtime_status = AgentExecutionStatus.COMPLETED

        verification_result = self._verify_execution(
            execution=execution,
            task=task,
        )

        if (
            verification_result is not None
            and verification_result.status == VerificationStatus.FAILED
        ):
            failure = VerificationFailureAdapter.to_failure(
                verification_result
            )
            execution.status = AgentExecutionStatus.FAILED
            execution.verification_status = VerificationStatus.FAILED
            execution.failure = failure
            execution.error_message = failure.message

            if self._execution_service is not None:
                self._execution_service.fail_verification(
                    execution_id=execution.id,
                    failure=failure,
                    verification_result=verification_result,
                )

            self._synchronize_execution(
                execution=execution,
                plan_steps=plan_steps,
            )
            return False

        if (
            verification_result is not None
            and verification_result.status == VerificationStatus.PASSED
        ):
            execution.verification_status = VerificationStatus.PASSED
            if self._execution_service is not None:
                self._execution_service.complete_verification(
                    execution_id=execution.id,
                    verification_result=verification_result,
                )

        self._synchronize_execution(
            execution=execution,
            plan_steps=plan_steps,
        )

        self._remember_execution(
            execution=execution,
            task=task,
        )

        return True

    def _remember_execution(
        self,
        execution: AgentExecution,
        task: AgentTask,
    ) -> None:
        """Persist an execution outcome as episodic memory when configured."""

        if self._memory_service is None:
            return

        self._memory_service.remember_execution(
            execution=execution,
            task_id=task.task_id,
        )

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
        task_id: UUID,
    ) -> AgentTask:
        """Find the task associated with an execution."""

        for task in tasks:
            if task.id == task_id:
                return task

        raise ValueError(
            f"Agent task not found: {task_id}"
        )

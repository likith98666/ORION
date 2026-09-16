from uuid import uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.execution_loop import ExecutionLoop
from orion.core.planning.steps import PlanStep, PlanStepStatus
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)
from orion.core.recovery.recovery_coordinator import RecoveryResult
from orion.core.recovery.recovery_execution_context import (
    RecoveryExecutionContext,
)
from orion.core.recovery.recovery_strategy import (
    RecoveryDecision,
    RecoveryStrategy,
)


class FakeExecutionCoordinator:
    def __init__(self, executions: list[AgentExecution]) -> None:
        self.executions = list(executions)
        self.calls = []
        self.index = 0

    def execute_task(self, task, model_config):
        self.calls.append((task, model_config))

        if self.index >= len(self.executions):
            raise AssertionError(
                "Fake execution coordinator ran out of executions."
            )

        execution = self.executions[self.index]
        self.index += 1
        return execution


class FakeRecoveryCoordinator:
    def __init__(
        self,
        action_types: list[RecoveryActionType],
    ) -> None:
        self.action_types = list(action_types)
        self.calls = []

    def handle_failure(
        self,
        execution,
        *,
        execution_context=None,
        **kwargs,
    ):
        self.calls.append(
            (
                execution,
                execution_context,
            )
        )

        failure = execution.failure

        if failure is None:
            raise AssertionError(
                "Fake recovery coordinator requires a structured failure."
            )

        if not self.action_types:
            raise AssertionError(
                "Fake recovery coordinator ran out of recovery actions."
            )

        action_type = self.action_types.pop(0)

        strategy = {
            RecoveryActionType.RETRY_TASK: (
                RecoveryStrategy.RETRY_CURRENT_TASK
            ),
            RecoveryActionType.CHANGE_AGENT: (
                RecoveryStrategy.CHANGE_AGENT
            ),
            RecoveryActionType.CHANGE_TOOL: (
                RecoveryStrategy.CHANGE_TOOL
            ),
            RecoveryActionType.CHANGE_MODEL: (
                RecoveryStrategy.CHANGE_MODEL
            ),
            RecoveryActionType.MODIFY_TASK: (
                RecoveryStrategy.MODIFY_TASK
            ),
            RecoveryActionType.CHANGE_TASK_ORDER: (
                RecoveryStrategy.CHANGE_TASK_ORDER
            ),
            RecoveryActionType.SKIP_TASK: (
                RecoveryStrategy.SKIP_NONESSENTIAL_TASK
            ),
            RecoveryActionType.ESCALATE_TO_HUMAN: (
                RecoveryStrategy.ESCALATE_TO_HUMAN
            ),
        }[action_type]

        decision = RecoveryDecision(
            strategy=strategy,
            reason=f"Fake recovery decision: {strategy.value}.",
            requires_human=(
                action_type
                == RecoveryActionType.ESCALATE_TO_HUMAN
            ),
        )

        return RecoveryResult(
            failure=failure,
            decision=decision,
            action=RecoveryAction(
                action_type=action_type,
            ),
        )


class FakeRecoveryService:
    def __init__(
        self,
        executions: list[AgentExecution],
    ) -> None:
        self.executions = list(executions)
        self.retry_calls = []
        self.model_change_calls = []
        self.index = 0

    def _next_execution(self) -> AgentExecution:
        if self.index >= len(self.executions):
            raise AssertionError(
                "Fake recovery service ran out of executions."
            )

        execution = self.executions[self.index]
        self.index += 1
        return execution

    def retry_task(self, task, model_config):
        self.retry_calls.append((task, model_config))
        return self._next_execution()

    def change_model_and_retry(
        self,
        task,
        current_model_config,
        alternative_model_configs,
    ):
        self.model_change_calls.append(
            (
                task,
                current_model_config,
                alternative_model_configs,
            )
        )
        return self._next_execution()


class FakeStateSynchronizer:
    def __init__(self) -> None:
        self.calls = []

    def synchronize(self, execution, plan_steps):
        self.calls.append((execution, plan_steps))

        if execution.status == AgentExecutionStatus.FAILED:
            plan_steps[0].status = PlanStepStatus.FAILED


def create_plan_step() -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="Execute task.",
        required_capability=AgentCapability.REASONING,
    )


def create_assigned_task(plan_step_id=None) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        plan_step_id=plan_step_id,
        description="Execute task.",
        required_capability=AgentCapability.REASONING,
    )

    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED

    return task


def create_failed_execution(
    task: AgentTask,
    message: str = "Model provider failed.",
) -> AgentExecution:
    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    execution.status = AgentExecutionStatus.FAILED
    execution.failure = Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message=message,
    )
    execution.error_message = execution.failure.message

    return execution


def create_completed_execution(
    task: AgentTask,
    output: str = "Recovered successfully.",
) -> AgentExecution:
    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    execution.status = AgentExecutionStatus.COMPLETED
    execution.output = output

    return execution


def test_execution_loop_can_receive_recovery_coordinator() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (execution,)
    assert len(recovery_coordinator.calls) == 1


def test_execution_loop_passes_initial_recovery_context() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    recovered_execution, context = recovery_coordinator.calls[0]

    assert recovered_execution is execution
    assert context.task_id == task.id
    assert context.current_execution_id == execution.id
    assert context.attempt_number == 1
    assert context.recovery_attempt_number == 0
    assert context.failure_history == (execution.failure,)
    assert context.recovery_history == ()


def test_execution_loop_does_not_invoke_recovery_for_successful_execution() -> None:
    task = create_assigned_task()
    execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (execution,)
    assert recovery_coordinator.calls == []


def test_execution_loop_synchronizes_failed_execution_before_recovery() -> None:
    plan_step = create_plan_step()
    task = create_assigned_task(plan_step.id)
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )
    state_synchronizer = FakeStateSynchronizer()

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        state_synchronizer=state_synchronizer,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    assert state_synchronizer.calls == [
        (execution, [plan_step]),
    ]

    assert task.status == AgentTaskStatus.ASSIGNED
    assert plan_step.status == PlanStepStatus.FAILED
    assert len(recovery_coordinator.calls) == 1


def test_execution_loop_retries_failed_task_and_stops_after_success() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(task)
    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator([first_failure])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )
    recovery_service = FakeRecoveryService(
        [successful_execution]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (
        first_failure,
        successful_execution,
    )

    assert len(recovery_coordinator.calls) == 1
    assert len(recovery_service.retry_calls) == 1


def test_execution_loop_supports_multiple_recovery_attempts() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(
        task,
        message="First failure.",
    )

    second_failure = create_failed_execution(
        task,
        message="Second failure.",
    )

    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator(
        [first_failure]
    )

    recovery_coordinator = FakeRecoveryCoordinator(
        [
            RecoveryActionType.RETRY_TASK,
            RecoveryActionType.RETRY_TASK,
        ]
    )

    recovery_service = FakeRecoveryService(
        [
            second_failure,
            successful_execution,
        ]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (
        first_failure,
        second_failure,
        successful_execution,
    )

    assert len(recovery_coordinator.calls) == 2
    assert len(recovery_service.retry_calls) == 2


def test_execution_loop_preserves_every_execution_attempt() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(task)
    second_failure = create_failed_execution(task)
    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator(
        [first_failure]
    )

    recovery_coordinator = FakeRecoveryCoordinator(
        [
            RecoveryActionType.RETRY_TASK,
            RecoveryActionType.RETRY_TASK,
        ]
    )

    recovery_service = FakeRecoveryService(
        [
            second_failure,
            successful_execution,
        ]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert len(result.executions) == 3
    assert result.executions[0] is first_failure
    assert result.executions[1] is second_failure
    assert result.executions[2] is successful_execution


def test_execution_loop_accumulates_failure_and_recovery_history() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(
        task,
        message="First failure.",
    )

    second_failure = create_failed_execution(
        task,
        message="Second failure.",
    )

    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator(
        [first_failure]
    )

    recovery_coordinator = FakeRecoveryCoordinator(
        [
            RecoveryActionType.RETRY_TASK,
            RecoveryActionType.RETRY_TASK,
        ]
    )

    recovery_service = FakeRecoveryService(
        [
            second_failure,
            successful_execution,
        ]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert len(recovery_coordinator.calls) == 2

    first_context = recovery_coordinator.calls[0][1]
    second_context = recovery_coordinator.calls[1][1]

    assert first_context.failure_history == (
        first_failure.failure,
    )

    assert first_context.recovery_history == ()

    assert second_context.failure_history == (
        first_failure.failure,
        second_failure.failure,
    )

    assert len(second_context.recovery_history) == 1
    assert (
        second_context.recovery_history[0].strategy
        == RecoveryStrategy.RETRY_CURRENT_TASK
    )
    assert (
        second_context.recovery_history[0].reason
        == "Fake recovery decision: retry_current_task."
    )


def test_execution_loop_progresses_recovery_attempt_context() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(task)
    second_failure = create_failed_execution(task)
    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator(
        [first_failure]
    )

    recovery_coordinator = FakeRecoveryCoordinator(
        [
            RecoveryActionType.RETRY_TASK,
            RecoveryActionType.RETRY_TASK,
        ]
    )

    recovery_service = FakeRecoveryService(
        [
            second_failure,
            successful_execution,
        ]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    first_context = recovery_coordinator.calls[0][1]
    second_context = recovery_coordinator.calls[1][1]

    assert first_context.attempt_number == 1
    assert first_context.recovery_attempt_number == 0

    assert second_context.attempt_number == 2
    assert second_context.recovery_attempt_number == 1
    assert second_context.current_execution_id == second_failure.id


def test_execution_loop_changes_model_and_continues_recovery() -> None:
    task = create_assigned_task()

    first_failure = create_failed_execution(task)
    successful_execution = create_completed_execution(task)

    coordinator = FakeExecutionCoordinator([first_failure])

    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.CHANGE_MODEL]
    )

    recovery_service = FakeRecoveryService(
        [successful_execution]
    )

    current_model = ModelConfig(provider_name="mock")
    alternative_model = ModelConfig(provider_name="alternative")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=current_model,
        alternative_model_configs=(alternative_model,),
    )

    assert result.executions == (
        first_failure,
        successful_execution,
    )

    assert recovery_service.model_change_calls == [
        (
            task,
            current_model,
            (alternative_model,),
        )
    ]


def test_execution_loop_stops_when_recovery_action_is_not_implemented() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])
    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.CHANGE_AGENT]
    )
    recovery_service = FakeRecoveryService([])

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (execution,)
    assert recovery_coordinator.calls
    assert recovery_service.retry_calls == []
    assert recovery_service.model_change_calls == []


def test_execution_loop_stops_when_recovery_coordinator_is_missing() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (execution,)


def test_execution_loop_stops_when_recovery_service_is_missing() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator([execution])

    recovery_coordinator = FakeRecoveryCoordinator(
        [RecoveryActionType.RETRY_TASK]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert result.executions == (execution,)
    assert len(recovery_coordinator.calls) == 1

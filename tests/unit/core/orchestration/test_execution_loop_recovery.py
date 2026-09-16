from uuid import uuid4

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


class FakeExecutionCoordinator:
    def __init__(self, execution: AgentExecution) -> None:
        self.execution = execution
        self.calls = []

    def execute_task(self, task, model_config):
        self.calls.append((task, model_config))
        return self.execution


class FakeRecoveryCoordinator:
    def __init__(
        self,
        action_type: RecoveryActionType = RecoveryActionType.RETRY_TASK,
    ) -> None:
        self.action_type = action_type
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

        return RecoveryResult(
            failure=failure,
            action=RecoveryAction(
                action_type=self.action_type,
            ),
        )


class FakeRecoveryService:
    def __init__(self, execution: AgentExecution) -> None:
        self.execution = execution
        self.calls = []
        self.model_change_calls = []

    def retry_task(self, task, model_config):
        self.calls.append((task, model_config))
        return self.execution

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
        return self.execution


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


def create_failed_execution(task: AgentTask) -> AgentExecution:
    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    execution.status = AgentExecutionStatus.FAILED
    execution.failure = Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message="Model provider failed.",
    )
    execution.error_message = execution.failure.message

    return execution


def test_execution_loop_can_receive_recovery_coordinator() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator(execution)
    recovery_coordinator = FakeRecoveryCoordinator()

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


def test_execution_loop_passes_recovery_context_for_failed_execution() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator(execution)
    recovery_coordinator = FakeRecoveryCoordinator()

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
    assert isinstance(context, RecoveryExecutionContext)
    assert context.task_id == task.id
    assert context.current_execution_id == execution.id
    assert context.failure_history == (execution.failure,)


def test_execution_loop_does_not_invoke_recovery_for_successful_execution() -> None:
    task = create_assigned_task()

    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )
    execution.status = AgentExecutionStatus.COMPLETED

    coordinator = FakeExecutionCoordinator(execution)
    recovery_coordinator = FakeRecoveryCoordinator()

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

    coordinator = FakeExecutionCoordinator(execution)
    recovery_coordinator = FakeRecoveryCoordinator()
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


def test_execution_loop_retries_when_recovery_requests_retry() -> None:
    plan_step = create_plan_step()
    task = create_assigned_task(plan_step.id)

    failed_execution = create_failed_execution(task)

    retry_execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )
    retry_execution.status = AgentExecutionStatus.COMPLETED
    retry_execution.output = "Recovered successfully."

    coordinator = FakeExecutionCoordinator(failed_execution)
    recovery_coordinator = FakeRecoveryCoordinator(
        action_type=RecoveryActionType.RETRY_TASK,
    )
    recovery_service = FakeRecoveryService(retry_execution)
    state_synchronizer = FakeStateSynchronizer()

    model_config = ModelConfig(provider_name="mock")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task],
        model_config=model_config,
        plan_steps=[plan_step],
    )

    assert recovery_service.calls == [
        (task, model_config),
    ]

    assert recovery_service.model_change_calls == []

    assert result.executions == (
        failed_execution,
        retry_execution,
    )


def test_execution_loop_changes_model_when_recovery_requests_change_model() -> None:
    plan_step = create_plan_step()
    task = create_assigned_task(plan_step.id)

    failed_execution = create_failed_execution(task)

    recovered_execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )
    recovered_execution.status = AgentExecutionStatus.COMPLETED
    recovered_execution.output = "Recovered using alternative model."

    coordinator = FakeExecutionCoordinator(failed_execution)

    recovery_coordinator = FakeRecoveryCoordinator(
        action_type=RecoveryActionType.CHANGE_MODEL,
    )

    recovery_service = FakeRecoveryService(recovered_execution)
    state_synchronizer = FakeStateSynchronizer()

    current_model = ModelConfig(
        provider_name="primary",
    )

    alternative_model = ModelConfig(
        provider_name="alternate",
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task],
        model_config=current_model,
        alternative_model_configs=(alternative_model,),
        plan_steps=[plan_step],
    )

    assert recovery_service.calls == []

    assert recovery_service.model_change_calls == [
        (
            task,
            current_model,
            (alternative_model,),
        ),
    ]

    assert result.executions == (
        failed_execution,
        recovered_execution,
    )


def test_execution_loop_ignores_recovery_actions_without_implementation() -> None:
    task = create_assigned_task()
    execution = create_failed_execution(task)

    coordinator = FakeExecutionCoordinator(execution)

    recovery_coordinator = FakeRecoveryCoordinator(
        action_type=RecoveryActionType.CHANGE_AGENT,
    )

    recovery_service = FakeRecoveryService(execution)

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
    assert recovery_service.calls == []
    assert recovery_service.model_change_calls == []

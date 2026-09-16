from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_action import RecoveryAction, RecoveryActionType
from orion.core.recovery.recovery_coordinator import RecoveryResult
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.orchestration.execution_loop import ExecutionLoop


class FakeExecutionCoordinator:
    def __init__(self, execution: AgentExecution) -> None:
        self.execution = execution
        self.calls = []

    def execute_task(self, task, model_config):
        self.calls.append((task, model_config))
        return self.execution


class FakeRecoveryCoordinator:
    def __init__(self) -> None:
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
                action_type=RecoveryActionType.RETRY_TASK,
            ),
        )


def create_assigned_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Execute task.",
        required_capability=__import__(
            "orion.core.agents.capabilities",
            fromlist=["AgentCapability"],
        ).AgentCapability.REASONING,
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

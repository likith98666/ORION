from uuid import UUID, uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.memory_task_repository import InMemoryAgentTaskRepository
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService
from orion.core.observability.context import TelemetryContext
from orion.core.orchestration.execution_loop import ExecutionLoop
from orion.core.orchestration.parallel_executor import ParallelExecutor
from orion.core.orchestration.state_synchronizer import StateSynchronizer
from orion.core.planning.steps import PlanStep, PlanStepStatus
from orion.core.recovery.failures import FailureType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService


class VerificationExecutionCoordinator:
    def __init__(self, output: str = "The system uses PostgreSQL for persistent storage.") -> None:
        self.output = output
        self.calls: list[AgentTask] = []

    def execute_task(self, task: AgentTask, model_config: ModelConfig, memory_context=None) -> AgentExecution:
        self.calls.append(task)
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        execution.output = self.output
        return execution


class SequenceExecutionCoordinator:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[AgentTask] = []
        self.index = 0

    def execute_task(self, task: AgentTask, model_config: ModelConfig, memory_context=None) -> AgentExecution:
        self.calls.append(task)
        output = self.outputs[self.index] if self.index < len(self.outputs) else "Exhausted"
        self.index += 1
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        execution.output = output
        return execution


class FakeRecoveryService:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.retry_calls: list[tuple[AgentTask, ModelConfig]] = []
        self.model_change_calls: list[tuple[AgentTask, ModelConfig]] = []
        self.index = 0

    def retry_task(
        self,
        task: AgentTask,
        model_config: ModelConfig,
        memory_context=None,
    ) -> AgentExecution:
        self.retry_calls.append((task, model_config))
        output = self.outputs[self.index] if self.index < len(self.outputs) else "Fallback"
        self.index += 1
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        execution.output = output
        return execution

    def change_model_and_retry(
        self,
        task: AgentTask,
        current_model_config: ModelConfig,
        alternative_model_configs: tuple[ModelConfig, ...],
        memory_context=None,
    ) -> AgentExecution:
        self.model_change_calls.append((task, current_model_config))
        output = self.outputs[self.index] if self.index < len(self.outputs) else "Fallback"
        self.index += 1
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        execution.output = output
        return execution


class StatusTrackingTaskService:
    """Task service that tracks all status transitions in sequence for invariant testing."""

    def __init__(self, initial_task: AgentTask) -> None:
        self.task = initial_task
        self.status_history: list[AgentTaskStatus] = [initial_task.status]

    def get_task(self, task_id: UUID) -> AgentTask | None:
        if task_id == self.task.id:
            return self.task
        return None

    def update_status(self, task_id: UUID, status: AgentTaskStatus) -> AgentTask:
        self.status_history.append(status)
        self.task.status = status
        return self.task


def create_task(requirements: tuple[str, ...] = ("PostgreSQL",)) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate PostgreSQL documentation.",
        required_capability=AgentCapability.REASONING,
        expected_requirements=requirements,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def create_plan_step() -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="Generate documentation.",
        required_capability=AgentCapability.REASONING,
    )


# ---------------------------------------------------------------------------
# Verification Success Tests
# ---------------------------------------------------------------------------


def test_execution_loop_verifies_execution_output() -> None:
    task = create_task()

    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    engine = VerificationEngine(service)

    loop = ExecutionLoop(
        execution_coordinator=VerificationExecutionCoordinator(),
        verification_engine=engine,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]

    verification_results = repository.list_for_execution(execution.id)

    assert len(verification_results) == 1
    assert verification_results[0].status == VerificationStatus.PASSED
    assert verification_results[0].execution_id == execution.id
    assert execution.status == AgentExecutionStatus.COMPLETED


def test_execution_loop_does_not_verify_when_requirements_are_empty() -> None:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate documentation.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED

    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    engine = VerificationEngine(service)

    loop = ExecutionLoop(
        execution_coordinator=VerificationExecutionCoordinator(),
        verification_engine=engine,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]

    assert repository.list_for_execution(execution.id) == []
    assert execution.status == AgentExecutionStatus.COMPLETED


def test_execution_output_passes_verification_completes_task_and_plan_step() -> None:
    plan_step = create_plan_step()
    task = create_task()
    task.plan_step_id = plan_step.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    verif_service = VerificationService(verif_repo)
    engine = VerificationEngine(verif_service)

    coordinator = VerificationExecutionCoordinator("Output mentions PostgreSQL correctly.")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    execution = result.executions[0]
    assert execution.status == AgentExecutionStatus.COMPLETED
    assert task.status == AgentTaskStatus.COMPLETED
    assert plan_step.status == PlanStepStatus.COMPLETED


def test_successful_output_is_remembered_in_memory() -> None:
    task = create_task()

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    memory_repo = InMemoryMemoryRepository()
    memory_service = MemoryService(memory_repo)

    coordinator = VerificationExecutionCoordinator("Output contains PostgreSQL.")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        memory_service=memory_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]
    assert execution.status == AgentExecutionStatus.COMPLETED

    memories = memory_service.list_for_task(task.task_id)
    assert len(memories) == 1
    assert memories[0].task_id == task.task_id


# ---------------------------------------------------------------------------
# Verification Failure Tests & Invariant Verification
# ---------------------------------------------------------------------------


def test_failed_verification_marks_execution_and_task_and_step_failed() -> None:
    plan_step = create_plan_step()
    task = create_task(requirements=("PostgreSQL", "Replication"))
    task.plan_step_id = plan_step.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    # Output missing "Replication"
    coordinator = VerificationExecutionCoordinator("Output mentions PostgreSQL only.")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    execution = result.executions[0]
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.failure is not None
    assert execution.failure.failure_type == FailureType.VERIFICATION_FAILURE
    assert "Output is missing required content" in execution.failure.message
    assert task.status == AgentTaskStatus.FAILED
    assert plan_step.status == PlanStepStatus.FAILED


def test_task_is_not_marked_completed_before_verification() -> None:
    plan_step = create_plan_step()
    task = create_task(requirements=("PostgreSQL",))
    task.plan_step_id = plan_step.id

    tracking_service = StatusTrackingTaskService(task)
    state_synchronizer = StateSynchronizer(task_service=tracking_service)

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    # Produce failing output
    coordinator = VerificationExecutionCoordinator("Output mentions MySQL only.")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        state_synchronizer=state_synchronizer,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    # Invariant: COMPLETED was NEVER entered in the status history
    assert AgentTaskStatus.COMPLETED not in tracking_service.status_history
    assert tracking_service.status_history == [
        AgentTaskStatus.ASSIGNED,
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.FAILED,
    ]


def test_failed_verification_does_not_remember_successful_memory() -> None:
    task = create_task(requirements=("PostgreSQL",))

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    memory_repo = InMemoryMemoryRepository()
    memory_service = MemoryService(memory_repo)

    coordinator = VerificationExecutionCoordinator("Output mentions MongoDB.")

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        memory_service=memory_service,
    )

    loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    memories = memory_service.list_for_task(task.task_id)
    assert len(memories) == 0


# ---------------------------------------------------------------------------
# Recovery Integration & Decision Tests
# ---------------------------------------------------------------------------


def test_verification_failure_reaches_recovery_coordinator_and_engine() -> None:
    task = create_task(requirements=("PostgreSQL",))

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    coordinator = VerificationExecutionCoordinator("Output mentions Redis.")

    recovery_engine = RecoveryEngine()
    recovery_coordinator = RecoveryCoordinator(recovery_engine=recovery_engine)

    fake_recovery_service = FakeRecoveryService(
        ["Second attempt now includes PostgreSQL."]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=fake_recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    # Two executions: initial failure, followed by successful recovery
    assert len(result.executions) == 2
    assert result.executions[0].status == AgentExecutionStatus.FAILED
    assert result.executions[0].failure.failure_type == FailureType.VERIFICATION_FAILURE
    assert result.executions[1].status == AgentExecutionStatus.COMPLETED
    assert "PostgreSQL" in result.executions[1].output
    assert len(fake_recovery_service.retry_calls) == 1


def test_verification_failure_triggers_re_execution_and_re_verification() -> None:
    plan_step = create_plan_step()
    task = create_task(requirements=("PostgreSQL",))
    task.plan_step_id = plan_step.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    verif_service = VerificationService(verif_repo)
    engine = VerificationEngine(verif_service)

    coordinator = VerificationExecutionCoordinator("Invalid output.")

    recovery_engine = RecoveryEngine()
    recovery_coordinator = RecoveryCoordinator(recovery_engine=recovery_engine)

    fake_recovery_service = FakeRecoveryService(
        ["Correct PostgreSQL documentation."]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=fake_recovery_service,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    assert len(result.executions) == 2
    # Verify that BOTH executions were verified in the verification repository
    first_verif = verif_service.list_for_execution(result.executions[0].id)
    second_verif = verif_service.list_for_execution(result.executions[1].id)

    assert len(first_verif) == 1
    assert first_verif[0].status == VerificationStatus.FAILED
    assert len(second_verif) == 1
    assert second_verif[0].status == VerificationStatus.PASSED


# ---------------------------------------------------------------------------
# Successful Recovery Tests
# ---------------------------------------------------------------------------


def test_first_attempt_fails_verification_second_attempt_passes_and_completes() -> None:
    plan_step = create_plan_step()
    task = create_task(requirements=("PostgreSQL",))
    task.plan_step_id = plan_step.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    memory_repo = InMemoryMemoryRepository()
    memory_service = MemoryService(memory_repo)

    coordinator = VerificationExecutionCoordinator("Failing first attempt.")
    recovery_coordinator = RecoveryCoordinator(RecoveryEngine())
    recovery_service = FakeRecoveryService(
        ["Successful PostgreSQL documentation."]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
        state_synchronizer=state_synchronizer,
        memory_service=memory_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    assert len(result.executions) == 2
    assert result.executions[0].status == AgentExecutionStatus.FAILED
    assert result.executions[1].status == AgentExecutionStatus.COMPLETED
    assert task.status == AgentTaskStatus.COMPLETED
    assert plan_step.status == PlanStepStatus.COMPLETED

    # Memory only recorded for the successful completion
    memories = memory_service.list_for_task(task.task_id)
    assert len(memories) == 1
    assert memories[0].source_execution_id == result.executions[1].id


# ---------------------------------------------------------------------------
# Exhaustion & Bounded Loop Tests
# ---------------------------------------------------------------------------


def test_repeated_verification_failures_stop_at_configured_limit_without_infinite_loop() -> None:
    plan_step = create_plan_step()
    task = create_task(requirements=("PostgreSQL",))
    task.plan_step_id = plan_step.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    coordinator = VerificationExecutionCoordinator("Attempt 1: No requirement.")
    recovery_coordinator = RecoveryCoordinator(RecoveryEngine())

    # Continuous failing outputs
    recovery_service = FakeRecoveryService(
        [
            "Attempt 2: Still missing.",
            "Attempt 3: Still missing.",
            "Attempt 4: Still missing.",
        ]
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
        state_synchronizer=state_synchronizer,
        max_recovery_attempts=2,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step],
    )

    # 1 initial attempt + 2 recovery attempts = 3 executions total
    assert len(result.executions) == 3
    for execution in result.executions:
        assert execution.status == AgentExecutionStatus.FAILED
        assert execution.failure.failure_type == FailureType.VERIFICATION_FAILURE

    assert len(recovery_service.retry_calls) == 2
    assert task.status == AgentTaskStatus.FAILED
    assert plan_step.status == PlanStepStatus.FAILED


# ---------------------------------------------------------------------------
# Parallel Path Tests
# ---------------------------------------------------------------------------


class ParallelVerificationCoordinator:
    def __init__(self) -> None:
        pass

    def execute_task(self, task: AgentTask, model_config: ModelConfig, memory_context=None) -> AgentExecution:
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        if "Task 1" in task.description:
            execution.output = "PostgreSQL cluster configuration."
        else:
            execution.output = "Invalid output without requirement."
        return execution


def test_parallel_execution_verification_failure_isolates_to_affected_task() -> None:
    plan_step_1 = PlanStep.create(
        plan_id=uuid4(),
        order=1,
        description="Task 1",
        required_capability=AgentCapability.REASONING,
    )
    plan_step_2 = PlanStep.create(
        plan_id=uuid4(),
        order=2,
        description="Task 2",
        required_capability=AgentCapability.REASONING,
    )

    task_1 = AgentTask.create(
        task_id=uuid4(),
        description="Task 1 description",
        required_capability=AgentCapability.REASONING,
        expected_requirements=("PostgreSQL",),
    )
    task_1.assigned_agent_id = uuid4()
    task_1.status = AgentTaskStatus.ASSIGNED
    task_1.plan_step_id = plan_step_1.id

    task_2 = AgentTask.create(
        task_id=uuid4(),
        description="Task 2 description",
        required_capability=AgentCapability.REASONING,
        expected_requirements=("PostgreSQL",),
    )
    task_2.assigned_agent_id = uuid4()
    task_2.status = AgentTaskStatus.ASSIGNED
    task_2.plan_step_id = plan_step_2.id

    task_repo = InMemoryAgentTaskRepository()
    task_repo.save(task_1)
    task_repo.save(task_2)
    task_service = AgentTaskService(task_repo)
    state_synchronizer = StateSynchronizer(task_service=task_service)

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    coordinator = ParallelVerificationCoordinator()
    parallel_executor = ParallelExecutor(execution_coordinator=coordinator, max_workers=2)

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        parallel_executor=parallel_executor,
        verification_engine=engine,
        state_synchronizer=state_synchronizer,
    )

    result = loop.execute(
        tasks=[task_1, task_2],
        model_config=ModelConfig(provider_name="mock"),
        plan_steps=[plan_step_1, plan_step_2],
    )

    assert len(result.executions) == 2
    # Task 1 passed verification
    assert result.executions[0].status == AgentExecutionStatus.COMPLETED
    assert task_1.status == AgentTaskStatus.COMPLETED
    assert plan_step_1.status == PlanStepStatus.COMPLETED

    # Task 2 failed verification
    assert result.executions[1].status == AgentExecutionStatus.FAILED
    assert result.executions[1].failure.failure_type == FailureType.VERIFICATION_FAILURE
    assert task_2.status == AgentTaskStatus.FAILED
    assert plan_step_2.status == PlanStepStatus.FAILED


# ---------------------------------------------------------------------------
# Telemetry Preservation Tests
# ---------------------------------------------------------------------------


def test_telemetry_context_survives_verification_failure_and_recovery() -> None:
    task = create_task(requirements=("PostgreSQL",))

    request_id = uuid4()
    trace_id = uuid4()
    span_id = uuid4()

    parent_telemetry = TelemetryContext(
        request_id=request_id,
        trace_id=trace_id,
        span_id=span_id,
    )

    class TelemetryCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            execution = AgentExecution.create(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
                telemetry_context=parent_telemetry,
            )
            execution.status = AgentExecutionStatus.COMPLETED
            execution.output = "Failing output."
            return execution

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    coordinator = TelemetryCoordinator()
    recovery_coordinator = RecoveryCoordinator(RecoveryEngine())
    recovery_service = FakeRecoveryService(["PostgreSQL recovered output."])

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert len(result.executions) == 2

    # Initial failed execution preserved its telemetry context
    first_telemetry = result.executions[0].telemetry_context
    assert first_telemetry is not None
    assert first_telemetry.request_id == request_id
    assert first_telemetry.trace_id == trace_id
    assert first_telemetry.span_id == span_id
    assert first_telemetry.task_id == task.id
    assert first_telemetry.execution_id == result.executions[0].id

    # Second successful execution has valid telemetry
    second_telemetry = result.executions[1].telemetry_context
    assert second_telemetry is not None
    assert second_telemetry.task_id == task.id
    assert second_telemetry.execution_id == result.executions[1].id


# ---------------------------------------------------------------------------
# Execution Persistence & Attempt Distinction Tests
# ---------------------------------------------------------------------------


def test_verification_failure_updates_persisted_execution_state_correctly() -> None:
    from orion.core.agents.execution_repository_memory import (
        InMemoryAgentExecutionRepository,
    )
    from orion.core.agents.execution_service import AgentExecutionService

    task = create_task(requirements=("PostgreSQL",))

    exec_repo = InMemoryAgentExecutionRepository()
    exec_service = AgentExecutionService(exec_repo)

    class ServiceExecutionCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            execution = exec_service.create_execution(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
            )
            return exec_service.complete_execution(
                execution_id=execution.id,
                output="Invalid output without required keyword",
                model_name="mock-model",
                provider_name="mock-provider",
            )

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    loop = ExecutionLoop(
        execution_coordinator=ServiceExecutionCoordinator(),
        verification_engine=engine,
        execution_service=exec_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.runtime_status == AgentExecutionStatus.COMPLETED
    assert execution.verification_status == VerificationStatus.FAILED

    persisted = exec_repo.get(execution.id)
    assert persisted is not None
    assert persisted.status == AgentExecutionStatus.FAILED
    assert persisted.runtime_status == AgentExecutionStatus.COMPLETED
    assert persisted.verification_status == VerificationStatus.FAILED
    assert persisted.failure is not None
    assert persisted.failure.failure_type == FailureType.VERIFICATION_FAILURE
    assert persisted.output == "Invalid output without required keyword"


def test_retry_creates_and_preserves_independent_attempt_history_correctly() -> None:
    from orion.core.agents.execution_repository_memory import (
        InMemoryAgentExecutionRepository,
    )
    from orion.core.agents.execution_service import AgentExecutionService

    task = create_task(requirements=("PostgreSQL",))

    exec_repo = InMemoryAgentExecutionRepository()
    exec_service = AgentExecutionService(exec_repo)

    class InitialExecutionCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            execution = exec_service.create_execution(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
            )
            return exec_service.complete_execution(
                execution_id=execution.id,
                output="Failing first attempt",
                model_name="mock-model",
                provider_name="mock-provider",
            )

    class ServiceRecoveryService:
        def __init__(self):
            self.retry_calls = []

        def retry_task(self, task, model_config, memory_context=None):
            self.retry_calls.append((task, model_config))
            execution = exec_service.create_execution(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
            )
            return exec_service.complete_execution(
                execution_id=execution.id,
                output="Successful second attempt mentioning PostgreSQL",
                model_name="mock-model",
                provider_name="mock-provider",
            )

    verif_repo = InMemoryVerificationRepository()
    engine = VerificationEngine(VerificationService(verif_repo))

    coordinator = InitialExecutionCoordinator()
    recovery_coordinator = RecoveryCoordinator(RecoveryEngine())
    recovery_service = ServiceRecoveryService()

    memory_repo = InMemoryMemoryRepository()
    memory_service = MemoryService(memory_repo)

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        verification_engine=engine,
        recovery_coordinator=recovery_coordinator,
        recovery_service=recovery_service,
        execution_service=exec_service,
        memory_service=memory_service,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert len(result.executions) == 2
    exec1, exec2 = result.executions

    assert exec1.id != exec2.id
    assert exec1.agent_task_id == task.id
    assert exec2.agent_task_id == task.id

    assert exec1.status == AgentExecutionStatus.FAILED
    assert exec1.runtime_status == AgentExecutionStatus.COMPLETED
    assert exec1.verification_status == VerificationStatus.FAILED

    assert exec2.status == AgentExecutionStatus.COMPLETED
    assert exec2.runtime_status == AgentExecutionStatus.COMPLETED
    assert exec2.verification_status == VerificationStatus.PASSED

    history = exec_service.list_for_agent_task(task.id)
    assert len(history) == 2
    persisted_1 = next(e for e in history if e.id == exec1.id)
    persisted_2 = next(e for e in history if e.id == exec2.id)

    assert persisted_1.status == AgentExecutionStatus.FAILED
    assert persisted_1.runtime_status == AgentExecutionStatus.COMPLETED
    assert persisted_1.verification_status == VerificationStatus.FAILED
    assert persisted_1.failure.failure_type == FailureType.VERIFICATION_FAILURE

    assert persisted_2.status == AgentExecutionStatus.COMPLETED
    assert persisted_2.runtime_status == AgentExecutionStatus.COMPLETED
    assert persisted_2.verification_status == VerificationStatus.PASSED

    memories = memory_service.list_for_task(task.task_id)
    assert len(memories) == 1
    assert memories[0].source_execution_id == exec2.id

from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.memory.context_provider import MemoryContextProvider
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService
from orion.core.orchestration.execution_loop import ExecutionLoop


class CapturingExecutionCoordinator:
    def __init__(self) -> None:
        self.calls = []

    def execute_task(
        self,
        task,
        model_config,
        memory_context=None,
    ):
        self.calls.append(
            (task, model_config, memory_context)
        )

        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )

        return execution


def create_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Find previous deployment knowledge.",
        required_capability=AgentCapability.REASONING,
    )

    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED

    return task


def test_execution_loop_propagates_memory_context() -> None:
    task = create_task()

    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository)

    memory_service.remember(
        content="Previous deployment succeeded.",
        memory_type=__import__(
            "orion.core.memory.models",
            fromlist=["MemoryType"],
        ).MemoryType.EPISODIC,
        task_id=task.task_id,
        agent_id=task.assigned_agent_id,
    )

    provider = MemoryContextProvider(memory_service)

    coordinator = CapturingExecutionCoordinator()

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        memory_context_provider=provider,
    )

    model_config = ModelConfig(provider_name="mock")

    loop.execute(
        tasks=[task],
        model_config=model_config,
    )

    assert len(coordinator.calls) == 1

    captured_task, captured_config, context = coordinator.calls[0]

    assert captured_task is task
    assert captured_config is model_config
    assert isinstance(context, ExecutionMemoryContext)
    assert context.task_id == task.task_id
    assert context.agent_id == task.assigned_agent_id
    assert context.memory_count == 1


def test_execution_loop_propagates_memory_contexts_in_parallel() -> None:
    first_task = create_task()
    second_task = create_task()

    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository)

    first_memory = memory_service.remember(
        content="First task deployment knowledge.",
        memory_type=__import__(
            "orion.core.memory.models",
            fromlist=["MemoryType"],
        ).MemoryType.EPISODIC,
        task_id=first_task.task_id,
        agent_id=first_task.assigned_agent_id,
    )

    second_memory = memory_service.remember(
        content="Second task deployment knowledge.",
        memory_type=__import__(
            "orion.core.memory.models",
            fromlist=["MemoryType"],
        ).MemoryType.EPISODIC,
        task_id=second_task.task_id,
        agent_id=second_task.assigned_agent_id,
    )

    provider = MemoryContextProvider(memory_service)
    coordinator = CapturingExecutionCoordinator()

    from orion.core.orchestration.parallel_executor import ParallelExecutor

    parallel_executor = ParallelExecutor(
        execution_coordinator=coordinator,
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        parallel_executor=parallel_executor,
        memory_context_provider=provider,
    )

    model_config = ModelConfig(provider_name="mock")

    result = loop.execute(
        tasks=[first_task, second_task],
        model_config=model_config,
    )

    assert len(result.executions) == 2
    assert len(coordinator.calls) == 2

    captured = {
        task.task_id: context
        for task, _, context in coordinator.calls
    }

    first_context = captured[first_task.task_id]
    second_context = captured[second_task.task_id]

    assert isinstance(first_context, ExecutionMemoryContext)
    assert isinstance(second_context, ExecutionMemoryContext)

    assert first_context.task_id == first_task.task_id
    assert second_context.task_id == second_task.task_id

    assert first_context.memory_count >= 1
    assert second_context.memory_count >= 1

    assert first_context.memories[0].memory.id == first_memory.id
    assert second_context.memories[0].memory.id == second_memory.id


def test_execution_loop_preserves_none_when_memory_provider_is_missing() -> None:
    task = create_task()
    coordinator = CapturingExecutionCoordinator()

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
    )

    model_config = ModelConfig(provider_name="mock")

    loop.execute(
        tasks=[task],
        model_config=model_config,
    )

    assert coordinator.calls == [
        (task, model_config, None),
    ]

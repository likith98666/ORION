from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.memory.context_provider import MemoryContextProvider
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.memory.models import MemoryType
from orion.core.memory.repository_memory import InMemoryMemoryRepository
from orion.core.memory.service import MemoryService
from orion.core.orchestration.execution_loop import ExecutionLoop


class RealMemoryExecutionCoordinator:
    def __init__(self) -> None:
        self.memory_contexts: list[ExecutionMemoryContext | None] = []

    def execute_task(
        self,
        task,
        model_config,
        memory_context: ExecutionMemoryContext | None = None,
    ):
        self.memory_contexts.append(memory_context)
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.status = AgentExecutionStatus.COMPLETED
        execution.output = "Execution produced a reusable result."
        return execution


def create_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate reusable knowledge.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def test_execution_loop_persists_real_episodic_memory() -> None:
    task = create_task()
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository)

    coordinator = RealMemoryExecutionCoordinator()
    memory_context_provider = MemoryContextProvider(memory_service)

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        memory_service=memory_service,
        memory_context_provider=memory_context_provider,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    assert len(result.executions) == 1
    assert len(coordinator.memory_contexts) == 1

    memory_context = coordinator.memory_contexts[0]
    assert memory_context is not None
    assert memory_context.task_id == task.task_id
    assert memory_context.agent_id == task.assigned_agent_id
    assert memory_context.is_empty

    memories = repository.list_for_task(task.task_id)

    assert len(memories) == 1

    memory = memories[0]

    assert memory.memory_type == MemoryType.EPISODIC
    assert memory.task_id == task.task_id
    assert memory.agent_id == task.assigned_agent_id
    assert memory.source_execution_id == result.executions[0].id
    assert "Execution produced a reusable result." in memory.content

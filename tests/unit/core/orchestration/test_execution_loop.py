from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.execution_loop import (
    ExecutionLoop,
    ExecutionLoopResult,
)
from orion.core.orchestration.parallel_executor import (
    ParallelExecutionResult,
)


class FakeExecutionCoordinator:
    def __init__(self) -> None:
        self.calls = []
        self.executions = {}

    def execute_task(
        self,
        task,
        model_config,
        memory_context=None,
    ):
        self.calls.append((task, model_config))

        execution = self.executions.get(task.id)

        if execution is None:
            execution = AgentExecution.create(
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
            )
            self.executions[task.id] = execution

        return execution


class FakeParallelExecutor:
    def __init__(self) -> None:
        self.calls = []
        self.result = ParallelExecutionResult(executions=())

    def execute(
        self,
        tasks,
        model_config,
        memory_contexts=None,
    ):
        self.calls.append((tasks, model_config, memory_contexts))
        return self.result


def create_assigned_task(description: str) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description=description,
        required_capability=AgentCapability.REASONING,
    )

    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED

    return task


def test_execution_loop_executes_all_tasks() -> None:
    first_task = create_assigned_task("First task.")
    second_task = create_assigned_task("Second task.")

    model_config = ModelConfig(provider_name="mock")

    coordinator = FakeExecutionCoordinator()
    loop = ExecutionLoop(coordinator)

    result = loop.execute(
        tasks=[first_task, second_task],
        model_config=model_config,
    )

    assert isinstance(result, ExecutionLoopResult)
    assert len(result.executions) == 2
    assert result.executions[0].agent_task_id == first_task.id
    assert result.executions[1].agent_task_id == second_task.id


def test_execution_loop_preserves_task_order() -> None:
    first_task = create_assigned_task("First task.")
    second_task = create_assigned_task("Second task.")
    third_task = create_assigned_task("Third task.")

    model_config = ModelConfig(provider_name="mock")

    coordinator = FakeExecutionCoordinator()
    loop = ExecutionLoop(coordinator)

    result = loop.execute(
        tasks=[third_task, first_task, second_task],
        model_config=model_config,
    )

    assert [execution.agent_task_id for execution in result.executions] == [
        third_task.id,
        first_task.id,
        second_task.id,
    ]


def test_execution_loop_passes_model_config_to_coordinator() -> None:
    first_task = create_assigned_task("First task.")
    second_task = create_assigned_task("Second task.")

    model_config = ModelConfig(
        provider_name="mock",
        temperature=0.7,
        max_tokens=512,
    )

    coordinator = FakeExecutionCoordinator()
    loop = ExecutionLoop(coordinator)

    loop.execute(
        tasks=[first_task, second_task],
        model_config=model_config,
    )

    assert coordinator.calls == [
        (first_task, model_config),
        (second_task, model_config),
    ]


def test_execution_loop_returns_empty_result_for_no_tasks() -> None:
    model_config = ModelConfig(provider_name="mock")

    coordinator = FakeExecutionCoordinator()
    loop = ExecutionLoop(coordinator)

    result = loop.execute(
        tasks=[],
        model_config=model_config,
    )

    assert result.executions == ()
    assert coordinator.calls == []


def test_execution_loop_propagates_coordinator_execution_result() -> None:
    task = create_assigned_task("Execute task.")

    model_config = ModelConfig(provider_name="mock")

    coordinator = FakeExecutionCoordinator()

    expected_execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )

    coordinator.executions[task.id] = expected_execution

    loop = ExecutionLoop(coordinator)

    result = loop.execute(
        tasks=[task],
        model_config=model_config,
    )

    assert result.executions == (expected_execution,)


def test_execution_loop_delegates_to_parallel_executor() -> None:
    first_task = create_assigned_task("First task.")
    second_task = create_assigned_task("Second task.")

    model_config = ModelConfig(provider_name="mock")

    coordinator = FakeExecutionCoordinator()
    parallel_executor = FakeParallelExecutor()

    expected_execution = AgentExecution.create(
        agent_task_id=first_task.id,
        agent_id=first_task.assigned_agent_id,
    )

    parallel_executor.result = ParallelExecutionResult(
        executions=(expected_execution,),
    )

    loop = ExecutionLoop(
        execution_coordinator=coordinator,
        parallel_executor=parallel_executor,
    )

    result = loop.execute(
        tasks=[first_task, second_task],
        model_config=model_config,
    )

    assert parallel_executor.calls == [
        ([first_task, second_task], model_config, [None, None]),
    ]

    assert result.executions == (expected_execution,)

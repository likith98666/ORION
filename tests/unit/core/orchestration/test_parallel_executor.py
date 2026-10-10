from threading import Event, Lock
from time import sleep
from uuid import uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.parallel_executor import ParallelExecutor


class FakeExecutionCoordinator:
    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.started = []
        self.completed = []
        self._lock = Lock()

    def execute_task(self, task, model_config, memory_context=None):
        with self._lock:
            self.started.append(task.id)

        sleep(self.delay)

        with self._lock:
            self.completed.append(task.id)

        return AgentExecution(
            id=uuid4(),
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
            status=AgentExecutionStatus.COMPLETED,
        )


def create_task(description: str) -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        plan_step_id=uuid4(),
        description=description,
        required_capability=AgentCapability.RESEARCH,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def create_model_config() -> ModelConfig:
    return ModelConfig(provider_name="test")


def test_parallel_executor_executes_all_tasks():
    coordinator = FakeExecutionCoordinator()

    executor = ParallelExecutor(
        execution_coordinator=coordinator,
        max_workers=2,
    )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
        create_task("Task C"),
    ]

    result = executor.execute(
        tasks=tasks,
        model_config=create_model_config(),
    )

    assert len(result.executions) == 3
    assert {execution.agent_task_id for execution in result.executions} == {
        task.id for task in tasks
    }


def test_parallel_executor_runs_tasks_concurrently():
    started = Event()
    release = Event()

    class BlockingCoordinator:
        def __init__(self):
            self.started_count = 0
            self._lock = Lock()

        def execute_task(self, task, model_config, memory_context=None):
            with self._lock:
                self.started_count += 1
                if self.started_count >= 2:
                    started.set()

            release.wait(timeout=1)

            return AgentExecution(
                id=uuid4(),
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
                status=AgentExecutionStatus.COMPLETED,
            )

    coordinator = BlockingCoordinator()

    executor = ParallelExecutor(
        execution_coordinator=coordinator,
        max_workers=2,
    )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
    ]

    results = []

    import threading

    worker = threading.Thread(
        target=lambda: results.append(
            executor.execute(
                tasks=tasks,
                model_config=create_model_config(),
            )
        )
    )

    worker.start()

    assert started.wait(timeout=1)

    release.set()
    worker.join(timeout=1)

    assert worker.is_alive() is False
    assert len(results) == 1
    assert len(results[0].executions) == 2


def test_parallel_executor_respects_max_workers():
    active = 0
    maximum_active = 0
    lock = Lock()

    class ConcurrencyCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            nonlocal active, maximum_active

            with lock:
                active += 1
                maximum_active = max(maximum_active, active)

            sleep(0.05)

            with lock:
                active -= 1

            return AgentExecution(
                id=uuid4(),
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
                status=AgentExecutionStatus.COMPLETED,
            )

    executor = ParallelExecutor(
        execution_coordinator=ConcurrencyCoordinator(),
        max_workers=2,
    )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
        create_task("Task C"),
        create_task("Task D"),
    ]

    executor.execute(
        tasks=tasks,
        model_config=create_model_config(),
    )

    assert maximum_active == 2


def test_parallel_executor_preserves_input_order():
    class OutOfOrderCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            if task.description == "Task A":
                sleep(0.10)
            elif task.description == "Task B":
                sleep(0.01)

            return AgentExecution(
                id=uuid4(),
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
                status=AgentExecutionStatus.COMPLETED,
            )

    executor = ParallelExecutor(
        execution_coordinator=OutOfOrderCoordinator(),
        max_workers=3,
    )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
        create_task("Task C"),
    ]

    result = executor.execute(
        tasks=tasks,
        model_config=create_model_config(),
    )

    assert [execution.agent_task_id for execution in result.executions] == [
        task.id for task in tasks
    ]


def test_parallel_executor_handles_empty_tasks():
    executor = ParallelExecutor(
        execution_coordinator=FakeExecutionCoordinator(),
        max_workers=2,
    )

    result = executor.execute(
        tasks=[],
        model_config=create_model_config(),
    )

    assert result.executions == ()


def test_parallel_executor_rejects_invalid_max_workers():
    with pytest.raises(ValueError, match="max_workers"):
        ParallelExecutor(
            execution_coordinator=FakeExecutionCoordinator(),
            max_workers=0,
        )


def test_parallel_executor_propagates_memory_context_per_task():
    received = {}
    lock = Lock()

    class MemoryAwareCoordinator:
        def execute_task(self, task, model_config, memory_context=None):
            with lock:
                received[task.id] = memory_context

            return AgentExecution(
                id=uuid4(),
                agent_task_id=task.id,
                agent_id=task.assigned_agent_id,
                status=AgentExecutionStatus.COMPLETED,
            )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
        create_task("Task C"),
    ]

    from orion.core.memory.execution_context import ExecutionMemoryContext

    contexts = [
        ExecutionMemoryContext(
            task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        for task in tasks
    ]

    executor = ParallelExecutor(
        execution_coordinator=MemoryAwareCoordinator(),
        max_workers=3,
    )

    result = executor.execute(
        tasks=tasks,
        model_config=create_model_config(),
        memory_contexts=contexts,
    )

    assert len(result.executions) == len(tasks)

    for task, context in zip(tasks, contexts, strict=True):
        assert received[task.id] is context

    assert [execution.agent_task_id for execution in result.executions] == [
        task.id for task in tasks
    ]


def test_parallel_executor_rejects_mismatched_memory_contexts():
    executor = ParallelExecutor(
        execution_coordinator=FakeExecutionCoordinator(),
        max_workers=2,
    )

    tasks = [
        create_task("Task A"),
        create_task("Task B"),
    ]

    from orion.core.memory.execution_context import ExecutionMemoryContext

    context = ExecutionMemoryContext(
        task_id=tasks[0].id,
        agent_id=tasks[0].assigned_agent_id,
    )

    with pytest.raises(
        ValueError,
        match="exactly one context per task",
    ):
        executor.execute(
            tasks=tasks,
            model_config=create_model_config(),
            memory_contexts=[context],
        )

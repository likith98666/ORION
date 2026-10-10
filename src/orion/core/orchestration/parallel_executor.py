from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask
from orion.core.memory.execution_context import ExecutionMemoryContext
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator


@dataclass(frozen=True)
class ParallelExecutionResult:
    """Result of executing agent tasks in parallel."""

    executions: tuple[AgentExecution, ...]


class ParallelExecutor:
    """Executes independent assigned agent tasks with bounded concurrency."""

    DEFAULT_MAX_WORKERS = 4

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero.")

        self._execution_coordinator = execution_coordinator
        self._max_workers = max_workers

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
        memory_contexts: list[ExecutionMemoryContext | None] | None = None,
    ) -> ParallelExecutionResult:
        """Execute tasks concurrently while preserving input result order."""

        if not tasks:
            return ParallelExecutionResult(executions=())

        if memory_contexts is not None and len(memory_contexts) != len(tasks):
            raise ValueError("memory_contexts must contain exactly one context per task.")

        contexts: Sequence[ExecutionMemoryContext | None]
        if memory_contexts is None:
            contexts = [None] * len(tasks)
        else:
            contexts = memory_contexts

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [
                executor.submit(
                    self._execution_coordinator.execute_task,
                    task,
                    model_config,
                    memory_context,
                )
                for task, memory_context in zip(tasks, contexts, strict=True)
            ]

            executions = tuple(future.result() for future in futures)

        return ParallelExecutionResult(executions=executions)

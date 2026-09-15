from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask
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
        """Return the maximum number of concurrent workers."""
        return self._max_workers

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
    ) -> ParallelExecutionResult:
        """Execute tasks concurrently while preserving input result order."""

        if not tasks:
            return ParallelExecutionResult(executions=())

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [
                executor.submit(
                    self._execution_coordinator.execute_task,
                    task,
                    model_config,
                )
                for task in tasks
            ]

            executions = tuple(
                future.result()
                for future in futures
            )

        return ParallelExecutionResult(
            executions=executions,
        )

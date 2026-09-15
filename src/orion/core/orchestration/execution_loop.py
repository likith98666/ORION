from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator
from orion.core.orchestration.parallel_executor import ParallelExecutor


@dataclass(frozen=True)
class ExecutionLoopResult:
    """Result of executing a collection of assigned agent tasks."""

    executions: tuple[AgentExecution, ...]


class ExecutionLoop:
    """Coordinates execution of assigned agent tasks."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        parallel_executor: ParallelExecutor | None = None,
    ) -> None:
        self._execution_coordinator = execution_coordinator
        self._parallel_executor = parallel_executor

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
    ) -> ExecutionLoopResult:
        """Execute assigned agent tasks."""

        if self._parallel_executor is not None:
            result = self._parallel_executor.execute(
                tasks=tasks,
                model_config=model_config,
            )

            return ExecutionLoopResult(
                executions=result.executions,
            )

        executions: list[AgentExecution] = []

        for task in tasks:
            execution = self._execution_coordinator.execute_task(
                task=task,
                model_config=model_config,
            )
            executions.append(execution)

        return ExecutionLoopResult(
            executions=tuple(executions),
        )

from dataclasses import dataclass

from orion.config.model_config import ModelConfig
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask
from orion.core.orchestration.execution_coordinator import ExecutionCoordinator


@dataclass(frozen=True)
class ExecutionLoopResult:
    """Result of executing a collection of assigned agent tasks."""

    executions: tuple[AgentExecution, ...]


class ExecutionLoop:
    """Coordinates execution of assigned agent tasks."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
    ) -> None:
        self._execution_coordinator = execution_coordinator

    def execute(
        self,
        tasks: list[AgentTask],
        model_config: ModelConfig,
    ) -> ExecutionLoopResult:
        """Execute assigned agent tasks sequentially."""

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

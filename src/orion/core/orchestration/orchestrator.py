from dataclasses import dataclass
from uuid import UUID

from orion.config.model_config import ModelConfig
from orion.core.agents.assignment_service import AgentAssignmentService
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTask
from orion.core.orchestration.execution_loop import (
    ExecutionLoop,
    ExecutionLoopResult,
)
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep


@dataclass(frozen=True)
class OrchestrationResult:
    """Result of scheduling and assigning ready plan steps."""

    ready_steps: tuple[PlanStep, ...]
    agent_tasks: tuple[AgentTask, ...]


@dataclass(frozen=True)
class OrchestrationExecutionResult:
    """Result of orchestration followed by agent task execution."""

    orchestration: OrchestrationResult
    execution: ExecutionLoopResult


class Orchestrator:
    """Coordinates plan steps, agent tasks, and execution."""

    def __init__(
        self,
        scheduler: PlanScheduler,
        agent_task_service: AgentTaskService,
        assignment_service: AgentAssignmentService,
        execution_loop: ExecutionLoop | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._agent_task_service = agent_task_service
        self._assignment_service = assignment_service
        self._execution_loop = execution_loop

    def orchestrate(
        self,
        task_id: UUID,
        plan_steps: list[PlanStep],
    ) -> OrchestrationResult:
        """Propagate blocked steps and assign currently ready plan steps."""

        self._scheduler.mark_blocked_steps(plan_steps)

        ready_steps = self._scheduler.get_ready_steps(plan_steps)

        agent_tasks: list[AgentTask] = []

        for step in ready_steps:
            agent_task = self._agent_task_service.create_task(
                task_id=task_id,
                plan_step_id=step.id,
                description=step.description,
                required_capability=step.required_capability,
            )

            assigned_task = self._assignment_service.assign_task(
                agent_task
            )

            agent_tasks.append(assigned_task)

        return OrchestrationResult(
            ready_steps=tuple(ready_steps),
            agent_tasks=tuple(agent_tasks),
        )

    def orchestrate_and_execute(
        self,
        task_id: UUID,
        plan_steps: list[PlanStep],
        model_config: ModelConfig,
    ) -> OrchestrationExecutionResult:
        """Orchestrate ready tasks and execute them."""

        if self._execution_loop is None:
            raise ValueError(
                "Execution loop is required for orchestrate_and_execute."
            )

        orchestration = self.orchestrate(
            task_id=task_id,
            plan_steps=plan_steps,
        )

        execution = self._execution_loop.execute(
            tasks=list(orchestration.agent_tasks),
            model_config=model_config,
            plan_steps=plan_steps,
        )

        return OrchestrationExecutionResult(
            orchestration=orchestration,
            execution=execution,
        )

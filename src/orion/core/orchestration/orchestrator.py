from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.assignment_service import AgentAssignmentService
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTask
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep


@dataclass(frozen=True)
class OrchestrationResult:
    """Result of scheduling and assigning ready plan steps."""

    ready_steps: tuple[PlanStep, ...]
    agent_tasks: tuple[AgentTask, ...]


class Orchestrator:
    """Coordinates ready plan steps with agent task creation and assignment."""

    def __init__(
        self,
        scheduler: PlanScheduler,
        agent_task_service: AgentTaskService,
        assignment_service: AgentAssignmentService,
    ) -> None:
        self._scheduler = scheduler
        self._agent_task_service = agent_task_service
        self._assignment_service = assignment_service

    def orchestrate(
        self,
        task_id: UUID,
        plan_steps: list[PlanStep],
    ) -> OrchestrationResult:
        """Create and assign agent tasks for currently ready plan steps."""

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

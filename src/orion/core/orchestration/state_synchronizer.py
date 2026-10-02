from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.task_service import AgentTaskService
from orion.core.agents.tasks import AgentTaskStatus
from orion.core.planning.steps import PlanStep, PlanStepStatus


class StateSynchronizer:
    """Synchronizes agent execution state with its task and plan step."""

    def __init__(
        self,
        task_service: AgentTaskService,
    ) -> None:
        self._task_service = task_service

    def synchronize(
        self,
        execution: AgentExecution,
        plan_steps: list[PlanStep],
    ) -> None:
        """Synchronize an execution result with its agent task and plan step."""

        task = self._task_service.get_task(execution.agent_task_id)

        if task is None:
            raise ValueError(
                f"Agent task not found: {execution.agent_task_id}"
            )

        plan_step = next(
            (
                step
                for step in plan_steps
                if step.id == task.plan_step_id
            ),
            None,
        )

        if plan_step is None:
            raise ValueError(
                f"Plan step not found: {task.plan_step_id}"
            )

        if execution.status == AgentExecutionStatus.RUNNING:
            if task.status != AgentTaskStatus.RUNNING:
                self._task_service.update_status(
                    task.id,
                    AgentTaskStatus.RUNNING,
                )
            plan_step.status = PlanStepStatus.RUNNING

        elif execution.status == AgentExecutionStatus.COMPLETED:
            if task.status != AgentTaskStatus.COMPLETED:
                if task.status in (AgentTaskStatus.ASSIGNED, AgentTaskStatus.FAILED):
                    self._task_service.update_status(
                        task.id,
                        AgentTaskStatus.RUNNING,
                    )
                self._task_service.update_status(
                    task.id,
                    AgentTaskStatus.COMPLETED,
                )
            plan_step.status = PlanStepStatus.COMPLETED

        elif execution.status == AgentExecutionStatus.FAILED:
            if task.status != AgentTaskStatus.FAILED:
                if task.status == AgentTaskStatus.ASSIGNED:
                    self._task_service.update_status(
                        task.id,
                        AgentTaskStatus.RUNNING,
                    )
                self._task_service.update_status(
                    task.id,
                    AgentTaskStatus.FAILED,
                )
            plan_step.status = PlanStepStatus.FAILED

        elif execution.status == AgentExecutionStatus.CANCELLED:
            if task.status != AgentTaskStatus.CANCELLED:
                self._task_service.update_status(
                    task.id,
                    AgentTaskStatus.CANCELLED,
                )
            plan_step.status = PlanStepStatus.SKIPPED

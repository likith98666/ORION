from orion.core.agents.tasks import AgentTask, AgentTaskStatus

ALLOWED_TRANSITIONS: dict[
    AgentTaskStatus,
    set[AgentTaskStatus],
] = {
    AgentTaskStatus.PENDING: {
        AgentTaskStatus.ASSIGNED,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.ASSIGNED: {
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.RUNNING: {
        AgentTaskStatus.COMPLETED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.COMPLETED: set(),
    AgentTaskStatus.FAILED: {
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.CANCELLED: set(),
}


class AgentTaskManager:
    """Manages the lifecycle of ORION agent tasks."""

    def update_status(
        self,
        task: AgentTask,
        status: AgentTaskStatus,
    ) -> AgentTask:
        """Update an agent task status using lifecycle rules."""

        allowed_statuses = ALLOWED_TRANSITIONS[task.status]

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid agent task transition: {task.status.value} -> {status.value}"
            )

        task.status = status

        return task

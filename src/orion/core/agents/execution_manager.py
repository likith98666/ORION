from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)


ALLOWED_TRANSITIONS: dict[
    AgentExecutionStatus,
    set[AgentExecutionStatus],
] = {
    AgentExecutionStatus.RUNNING: {
        AgentExecutionStatus.COMPLETED,
        AgentExecutionStatus.FAILED,
        AgentExecutionStatus.CANCELLED,
    },
    AgentExecutionStatus.COMPLETED: set(),
    AgentExecutionStatus.FAILED: set(),
    AgentExecutionStatus.CANCELLED: set(),
}


class AgentExecutionManager:
    """Manages the lifecycle of ORION agent executions."""

    def update_status(
        self,
        execution: AgentExecution,
        status: AgentExecutionStatus,
    ) -> AgentExecution:
        """Update an execution status using lifecycle rules."""

        allowed_statuses = ALLOWED_TRANSITIONS[execution.status]

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid agent execution transition: "
                f"{execution.status.value} -> {status.value}"
            )

        execution.status = status

        return execution

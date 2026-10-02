from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from orion.core.observability.context import TelemetryContext
from orion.core.recovery.failures import Failure
from orion.core.verification.models import VerificationStatus


class AgentExecutionStatus(str, Enum):
    """Lifecycle status of an ORION agent execution attempt."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentExecution:
    """Represents one execution attempt of an ORION agent task."""

    id: UUID
    agent_task_id: UUID
    agent_id: UUID
    status: AgentExecutionStatus = AgentExecutionStatus.RUNNING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    output: str | None = None
    error_message: str | None = None
    failure: Failure | None = None
    model_name: str | None = None
    provider_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    telemetry_context: TelemetryContext | None = None
    runtime_status: AgentExecutionStatus | None = None
    verification_status: VerificationStatus | None = None

    @classmethod
    def create(
        cls,
        agent_task_id: UUID,
        agent_id: UUID,
        telemetry_context: TelemetryContext | None = None,
    ) -> "AgentExecution":
        """Create a new agent execution attempt."""

        execution_id = uuid4()

        context = TelemetryContext(
            request_id=(telemetry_context.request_id if telemetry_context is not None else None),
            trace_id=(telemetry_context.trace_id if telemetry_context is not None else None),
            span_id=(telemetry_context.span_id if telemetry_context is not None else None),
            parent_span_id=(
                telemetry_context.parent_span_id if telemetry_context is not None else None
            ),
            task_id=agent_task_id,
            execution_id=execution_id,
            agent_id=agent_id,
            tool_id=(telemetry_context.tool_id if telemetry_context is not None else None),
        )

        return cls(
            id=execution_id,
            agent_task_id=agent_task_id,
            agent_id=agent_id,
            status=AgentExecutionStatus.RUNNING,
            telemetry_context=context,
            runtime_status=AgentExecutionStatus.RUNNING,
        )

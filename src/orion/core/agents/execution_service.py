from dataclasses import replace
from datetime import datetime
from uuid import UUID

from orion.core.agents.execution_manager import AgentExecutionManager
from orion.core.agents.execution_repository import AgentExecutionRepository
from orion.core.agents.executions import (
    AgentExecution,
    AgentExecutionStatus,
)
from orion.core.observability.context import TelemetryContext
from orion.core.recovery.failures import Failure, FailureType
from orion.core.verification.models import VerificationResult, VerificationStatus


class AgentExecutionService:
    """Coordinates creation and lifecycle updates of agent executions."""

    def __init__(
        self,
        repository: AgentExecutionRepository,
    ) -> None:
        self._repository = repository
        self._manager = AgentExecutionManager()

    def create_execution(
        self,
        agent_task_id: UUID,
        agent_id: UUID,
        telemetry_context: TelemetryContext | None = None,
    ) -> AgentExecution:
        """Create and persist a new running execution."""

        execution = AgentExecution.create(
            agent_task_id=agent_task_id,
            agent_id=agent_id,
            telemetry_context=telemetry_context,
        )

        self._repository.save(execution)

        return execution

    def get_execution(
        self,
        execution_id: UUID,
    ) -> AgentExecution | None:
        """Get an execution by ID."""

        return self._repository.get(execution_id)

    def update_status(
        self,
        execution_id: UUID,
        status: AgentExecutionStatus,
    ) -> AgentExecution:
        """Update and persist an execution status."""

        execution = self._repository.get(execution_id)

        if execution is None:
            raise ValueError(f"Agent execution '{execution_id}' not found.")

        updated_execution = self._manager.update_status(
            execution,
            status,
        )

        self._repository.save(updated_execution)

        return updated_execution

    def complete_execution(
        self,
        execution_id: UUID,
        output: str,
        model_name: str,
        provider_name: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: float | None = None,
    ) -> AgentExecution:
        """Complete an execution and persist its result metadata."""

        execution = self._repository.get(execution_id)

        if execution is None:
            raise ValueError(f"Agent execution '{execution_id}' not found.")

        updated_execution = self._manager.update_status(
            execution,
            AgentExecutionStatus.COMPLETED,
        )

        updated_execution = replace(
            updated_execution,
            completed_at=datetime.now(),
            output=output,
            model_name=model_name,
            provider_name=provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            runtime_status=AgentExecutionStatus.COMPLETED,
        )

        self._repository.save(updated_execution)

        return updated_execution

    def fail_execution(
        self,
        execution_id: UUID,
        error_message: str | None = None,
        failure: Failure | None = None,
    ) -> AgentExecution:
        """Fail an execution and persist its error and structured failure."""

        if failure is not None and not isinstance(failure, Failure):
            raise TypeError("failure must be a Failure instance.")

        if failure is None:
            if error_message is None or not error_message.strip():
                raise ValueError("Either error_message or failure must be provided.")

            failure = Failure(
                failure_type=FailureType.UNKNOWN,
                message=error_message,
            )

        execution = self._repository.get(execution_id)

        if execution is None:
            raise ValueError(f"Agent execution '{execution_id}' not found.")

        updated_execution = self._manager.update_status(
            execution,
            AgentExecutionStatus.FAILED,
        )

        updated_execution = replace(
            updated_execution,
            completed_at=datetime.now(),
            error_message=failure.message,
            failure=failure,
            runtime_status=AgentExecutionStatus.FAILED,
        )

        self._repository.save(updated_execution)

        return updated_execution

    def fail_verification(
        self,
        execution_id: UUID,
        failure: Failure,
        verification_result: VerificationResult | None = None,
    ) -> AgentExecution:
        """Record verification failure on an execution attempt while preserving runtime outcome."""

        if not isinstance(failure, Failure):
            raise TypeError("failure must be a Failure instance.")

        execution = self._repository.get(execution_id)

        if execution is None:
            raise ValueError(f"Agent execution '{execution_id}' not found.")

        updated_execution = replace(
            execution,
            status=AgentExecutionStatus.FAILED,
            runtime_status=(execution.runtime_status or AgentExecutionStatus.COMPLETED),
            verification_status=(
                verification_result.status
                if verification_result is not None
                else VerificationStatus.FAILED
            ),
            failure=failure,
            error_message=failure.message,
        )

        self._repository.save(updated_execution)

        return updated_execution

    def complete_verification(
        self,
        execution_id: UUID,
        verification_result: VerificationResult | None = None,
    ) -> AgentExecution:
        """Record verification success on an execution attempt."""

        execution = self._repository.get(execution_id)

        if execution is None:
            raise ValueError(f"Agent execution '{execution_id}' not found.")

        updated_execution = replace(
            execution,
            status=AgentExecutionStatus.COMPLETED,
            runtime_status=(execution.runtime_status or AgentExecutionStatus.COMPLETED),
            verification_status=(
                verification_result.status
                if verification_result is not None
                else VerificationStatus.PASSED
            ),
        )

        self._repository.save(updated_execution)

        return updated_execution

    def list_for_agent_task(
        self,
        agent_task_id: UUID,
    ) -> list[AgentExecution]:
        """List all execution attempts for an agent task."""

        return self._repository.list_for_agent_task(agent_task_id)

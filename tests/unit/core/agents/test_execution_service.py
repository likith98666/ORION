import uuid

import pytest

from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.executions import AgentExecutionStatus
from orion.core.observability.context import TelemetryContext


def create_service() -> tuple[
    AgentExecutionService,
    InMemoryAgentExecutionRepository,
]:
    repository = InMemoryAgentExecutionRepository()
    service = AgentExecutionService(repository)

    return service, repository


def test_create_execution_persists_running_execution() -> None:
    service, repository = create_service()

    agent_task_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    execution = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=agent_id,
    )

    assert execution.status == AgentExecutionStatus.RUNNING
    assert execution.agent_task_id == agent_task_id
    assert execution.agent_id == agent_id
    assert repository.get(execution.id) is execution


def test_get_execution_returns_existing_execution() -> None:
    service, _ = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    result = service.get_execution(execution.id)

    assert result is execution


def test_get_execution_returns_none_for_unknown_execution() -> None:
    service, _ = create_service()

    result = service.get_execution(uuid.uuid4())

    assert result is None


def test_update_status_persists_valid_transition() -> None:
    service, repository = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    updated = service.update_status(
        execution.id,
        AgentExecutionStatus.CANCELLED,
    )

    assert updated.status == AgentExecutionStatus.CANCELLED
    assert repository.get(execution.id) is updated


def test_update_status_rejects_unknown_execution() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError, match="not found"):
        service.update_status(
            uuid.uuid4(),
            AgentExecutionStatus.COMPLETED,
        )


def test_complete_execution_stores_result_metadata() -> None:
    service, repository = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    completed = service.complete_execution(
        execution_id=execution.id,
        output="Research completed.",
        model_name="mock-model",
        provider_name="mock",
        input_tokens=100,
        output_tokens=50,
        latency_ms=125.5,
    )

    assert completed.status == AgentExecutionStatus.COMPLETED
    assert completed.output == "Research completed."
    assert completed.model_name == "mock-model"
    assert completed.provider_name == "mock"
    assert completed.input_tokens == 100
    assert completed.output_tokens == 50
    assert completed.latency_ms == 125.5
    assert completed.completed_at is not None
    assert repository.get(execution.id) is completed


def test_fail_execution_stores_error() -> None:
    service, repository = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    failed = service.fail_execution(
        execution_id=execution.id,
        error_message="Model provider failed.",
    )

    assert failed.status == AgentExecutionStatus.FAILED
    assert failed.error_message == "Model provider failed."
    assert failed.completed_at is not None
    assert repository.get(execution.id) is failed


def test_complete_execution_rejects_unknown_execution() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError, match="not found"):
        service.complete_execution(
            execution_id=uuid.uuid4(),
            output="Result",
            model_name="mock-model",
            provider_name="mock",
        )


def test_fail_execution_rejects_unknown_execution() -> None:
    service, _ = create_service()

    with pytest.raises(ValueError, match="not found"):
        service.fail_execution(
            execution_id=uuid.uuid4(),
            error_message="Failure",
        )


def test_complete_execution_rejects_terminal_execution() -> None:
    service, _ = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    service.complete_execution(
        execution_id=execution.id,
        output="First result",
        model_name="mock-model",
        provider_name="mock",
    )

    with pytest.raises(ValueError, match="Invalid agent execution transition"):
        service.complete_execution(
            execution_id=execution.id,
            output="Second result",
            model_name="mock-model",
            provider_name="mock",
        )


def test_fail_execution_rejects_terminal_execution() -> None:
    service, _ = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    service.fail_execution(
        execution_id=execution.id,
        error_message="First failure",
    )

    with pytest.raises(ValueError, match="Invalid agent execution transition"):
        service.fail_execution(
            execution_id=execution.id,
            error_message="Second failure",
        )


def test_list_for_agent_task_returns_all_executions() -> None:
    service, _ = create_service()

    agent_task_id = uuid.uuid4()

    first = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=uuid.uuid4(),
    )
    second = service.create_execution(
        agent_task_id=agent_task_id,
        agent_id=uuid.uuid4(),
    )

    result = service.list_for_agent_task(agent_task_id)

    assert result == [first, second]


def test_create_execution_propagates_parent_telemetry_context() -> None:
    service, repository = create_service()

    request_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    span_id = uuid.uuid4()
    parent_span_id = uuid.uuid4()
    tool_id = uuid.uuid4()

    parent_context = TelemetryContext(
        request_id=request_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        tool_id=tool_id,
    )

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        telemetry_context=parent_context,
    )

    assert execution.telemetry_context is not None
    assert execution.telemetry_context.request_id == request_id
    assert execution.telemetry_context.trace_id == trace_id
    assert execution.telemetry_context.span_id == span_id
    assert execution.telemetry_context.parent_span_id == parent_span_id
    assert execution.telemetry_context.tool_id == tool_id
    assert execution.telemetry_context.task_id == execution.agent_task_id
    assert execution.telemetry_context.execution_id == execution.id
    assert execution.telemetry_context.agent_id == execution.agent_id
    assert repository.get(execution.id) is execution


def test_create_execution_without_parent_context_preserves_base_context() -> None:
    service, _ = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    assert execution.telemetry_context is not None
    assert execution.telemetry_context.request_id is None
    assert execution.telemetry_context.trace_id is None
    assert execution.telemetry_context.span_id is None
    assert execution.telemetry_context.parent_span_id is None
    assert execution.telemetry_context.task_id == execution.agent_task_id
    assert execution.telemetry_context.execution_id == execution.id
    assert execution.telemetry_context.agent_id == execution.agent_id
    assert execution.telemetry_context.tool_id is None


def test_fail_verification_updates_execution_status_and_preserves_runtime_status() -> None:
    from orion.core.recovery.failures import Failure, FailureType
    from orion.core.verification.models import (
        VerificationResult,
        VerificationStatus,
        VerificationType,
    )

    service, repository = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    completed = service.complete_execution(
        execution_id=execution.id,
        output="Generated output",
        model_name="test-model",
        provider_name="test-provider",
    )

    assert completed.status == AgentExecutionStatus.COMPLETED
    assert completed.runtime_status == AgentExecutionStatus.COMPLETED
    assert completed.verification_status is None

    verification_result = VerificationResult.create(
        execution_id=execution.id,
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.FAILED,
        reason="Missing expected keywords.",
    )
    failure = Failure(
        failure_type=FailureType.VERIFICATION_FAILURE,
        message=verification_result.reason,
    )

    failed = service.fail_verification(
        execution_id=execution.id,
        failure=failure,
        verification_result=verification_result,
    )

    assert failed.status == AgentExecutionStatus.FAILED
    assert failed.runtime_status == AgentExecutionStatus.COMPLETED
    assert failed.verification_status == VerificationStatus.FAILED
    assert failed.failure == failure
    assert failed.output == "Generated output"

    persisted = repository.get(execution.id)
    assert persisted is not None
    assert persisted.status == AgentExecutionStatus.FAILED
    assert persisted.runtime_status == AgentExecutionStatus.COMPLETED
    assert persisted.verification_status == VerificationStatus.FAILED


def test_complete_verification_updates_verification_status() -> None:
    from orion.core.verification.models import (
        VerificationResult,
        VerificationStatus,
        VerificationType,
    )

    service, repository = create_service()

    execution = service.create_execution(
        agent_task_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )

    service.complete_execution(
        execution_id=execution.id,
        output="Valid output",
        model_name="test-model",
        provider_name="test-provider",
    )

    verification_result = VerificationResult.create(
        execution_id=execution.id,
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="All requirements met.",
    )

    verified = service.complete_verification(
        execution_id=execution.id,
        verification_result=verification_result,
    )

    assert verified.status == AgentExecutionStatus.COMPLETED
    assert verified.runtime_status == AgentExecutionStatus.COMPLETED
    assert verified.verification_status == VerificationStatus.PASSED

    persisted = repository.get(execution.id)
    assert persisted is not None
    assert persisted.verification_status == VerificationStatus.PASSED

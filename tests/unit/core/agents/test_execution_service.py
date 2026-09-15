import uuid

import pytest

from orion.core.agents.execution_repository_memory import (
    InMemoryAgentExecutionRepository,
)
from orion.core.agents.execution_service import AgentExecutionService
from orion.core.agents.executions import AgentExecutionStatus


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

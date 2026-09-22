from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.execution_manager import AgentExecutionStatus
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import (
    InMemoryVerificationRepository,
)
from orion.core.verification.service import VerificationService


def create_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate PostgreSQL documentation.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def create_execution(task: AgentTask) -> AgentExecution:
    execution = AgentExecution.create(
        agent_task_id=task.id,
        agent_id=task.assigned_agent_id,
    )
    execution.status = AgentExecutionStatus.COMPLETED
    execution.output = "The system uses PostgreSQL for persistent storage."
    return execution


def test_verification_engine_integrates_with_execution_result() -> None:
    task = create_task()
    execution = create_execution(task)

    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    engine = VerificationEngine(service)

    result = engine.verify_output(
        execution_id=execution.id,
        output=execution.output,
        expected_requirements=["PostgreSQL"],
    )

    assert result.status == VerificationStatus.PASSED
    assert result.execution_id == execution.id

    stored_results = repository.list_for_execution(execution.id)

    assert stored_results == [result]

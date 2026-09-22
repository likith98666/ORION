from uuid import uuid4

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.executions import AgentExecution
from orion.core.agents.tasks import AgentTask, AgentTaskStatus
from orion.core.orchestration.execution_loop import ExecutionLoop
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationStatus
from orion.core.verification.repository_memory import (
    InMemoryVerificationRepository,
)
from orion.core.verification.service import VerificationService


class VerificationExecutionCoordinator:
    def execute_task(self, task, model_config, memory_context=None):
        execution = AgentExecution.create(
            agent_task_id=task.id,
            agent_id=task.assigned_agent_id,
        )
        execution.output = "The system uses PostgreSQL for persistent storage."
        return execution


def create_task() -> AgentTask:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate PostgreSQL documentation.",
        required_capability=AgentCapability.REASONING,
        expected_requirements=("PostgreSQL",),
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED
    return task


def test_execution_loop_verifies_execution_output() -> None:
    task = create_task()

    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    engine = VerificationEngine(service)

    loop = ExecutionLoop(
        execution_coordinator=VerificationExecutionCoordinator(),
        verification_engine=engine,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]

    verification_results = repository.list_for_execution(
        execution.id
    )

    assert len(verification_results) == 1
    assert verification_results[0].status == VerificationStatus.PASSED
    assert verification_results[0].execution_id == execution.id


def test_execution_loop_does_not_verify_when_requirements_are_empty() -> None:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Generate documentation.",
        required_capability=AgentCapability.REASONING,
    )
    task.assigned_agent_id = uuid4()
    task.status = AgentTaskStatus.ASSIGNED

    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    engine = VerificationEngine(service)

    loop = ExecutionLoop(
        execution_coordinator=VerificationExecutionCoordinator(),
        verification_engine=engine,
    )

    result = loop.execute(
        tasks=[task],
        model_config=ModelConfig(provider_name="mock"),
    )

    execution = result.executions[0]

    assert repository.list_for_execution(execution.id) == []

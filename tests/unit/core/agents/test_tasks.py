from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


def test_agent_task_can_be_created() -> None:
    task_id = uuid4()

    task = AgentTask.create(
        task_id=task_id,
        description="Research competitors in the AI education market.",
        required_capability=AgentCapability.RESEARCH,
    )

    assert task.id is not None
    assert task.task_id == task_id
    assert task.plan_step_id is None
    assert task.description == (
        "Research competitors in the AI education market."
    )
    assert task.required_capability == AgentCapability.RESEARCH
    assert task.status == AgentTaskStatus.PENDING
    assert task.assigned_agent_id is None


def test_agent_task_can_reference_plan_step() -> None:
    task_id = uuid4()
    plan_step_id = uuid4()

    task = AgentTask.create(
        task_id=task_id,
        plan_step_id=plan_step_id,
        description="Research competitors.",
        required_capability=AgentCapability.RESEARCH,
    )

    assert task.task_id == task_id
    assert task.plan_step_id == plan_step_id


def test_agent_task_description_is_trimmed() -> None:
    task = AgentTask.create(
        task_id=uuid4(),
        description="   Analyze the dataset.   ",
        required_capability=AgentCapability.DATA_ANALYSIS,
    )

    assert task.description == "Analyze the dataset."


def test_agent_task_rejects_empty_description() -> None:
    with pytest.raises(
        ValueError,
        match="Agent task description cannot be empty",
    ):
        AgentTask.create(
            task_id=uuid4(),
            description="",
            required_capability=AgentCapability.RESEARCH,
        )


def test_agent_task_rejects_whitespace_description() -> None:
    with pytest.raises(
        ValueError,
        match="Agent task description cannot be empty",
    ):
        AgentTask.create(
            task_id=uuid4(),
            description="   ",
            required_capability=AgentCapability.RESEARCH,
        )


def test_agent_task_rejects_description_over_5000_characters() -> None:
    with pytest.raises(
        ValueError,
        match="Agent task description cannot exceed 5,000 characters",
    ):
        AgentTask.create(
            task_id=uuid4(),
            description="x" * 5_001,
            required_capability=AgentCapability.RESEARCH,
        )


def test_agent_task_starts_with_pending_status() -> None:
    task = AgentTask.create(
        task_id=uuid4(),
        description="Find relevant research papers.",
        required_capability=AgentCapability.RESEARCH,
    )

    assert task.status == AgentTaskStatus.PENDING


def test_agent_task_has_all_expected_statuses() -> None:
    assert AgentTaskStatus.PENDING.value == "pending"
    assert AgentTaskStatus.ASSIGNED.value == "assigned"
    assert AgentTaskStatus.RUNNING.value == "running"
    assert AgentTaskStatus.COMPLETED.value == "completed"
    assert AgentTaskStatus.FAILED.value == "failed"
    assert AgentTaskStatus.CANCELLED.value == "cancelled"

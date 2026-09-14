import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.task_manager import AgentTaskManager
from orion.core.agents.tasks import AgentTask, AgentTaskStatus


def create_test_task() -> AgentTask:
    return AgentTask.create(
        task_id=__import__("uuid").uuid4(),
        description="Research the AI education market.",
        required_capability=AgentCapability.RESEARCH,
    )


def test_pending_task_can_be_assigned() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    result = manager.update_status(
        task,
        AgentTaskStatus.ASSIGNED,
    )

    assert result.status == AgentTaskStatus.ASSIGNED


def test_assigned_task_can_be_started() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.ASSIGNED)

    result = manager.update_status(
        task,
        AgentTaskStatus.RUNNING,
    )

    assert result.status == AgentTaskStatus.RUNNING


def test_running_task_can_be_completed() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.ASSIGNED)
    manager.update_status(task, AgentTaskStatus.RUNNING)

    result = manager.update_status(
        task,
        AgentTaskStatus.COMPLETED,
    )

    assert result.status == AgentTaskStatus.COMPLETED


def test_running_task_can_fail() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.ASSIGNED)
    manager.update_status(task, AgentTaskStatus.RUNNING)

    result = manager.update_status(
        task,
        AgentTaskStatus.FAILED,
    )

    assert result.status == AgentTaskStatus.FAILED


def test_failed_task_can_be_retried() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.ASSIGNED)
    manager.update_status(task, AgentTaskStatus.RUNNING)
    manager.update_status(task, AgentTaskStatus.FAILED)

    result = manager.update_status(
        task,
        AgentTaskStatus.RUNNING,
    )

    assert result.status == AgentTaskStatus.RUNNING


def test_completed_task_cannot_be_restarted() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.ASSIGNED)
    manager.update_status(task, AgentTaskStatus.RUNNING)
    manager.update_status(task, AgentTaskStatus.COMPLETED)

    with pytest.raises(
        ValueError,
        match="Invalid agent task transition: completed -> running",
    ):
        manager.update_status(
            task,
            AgentTaskStatus.RUNNING,
        )


def test_pending_task_cannot_start_directly() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    with pytest.raises(
        ValueError,
        match="Invalid agent task transition: pending -> running",
    ):
        manager.update_status(
            task,
            AgentTaskStatus.RUNNING,
        )


def test_cancelled_task_cannot_be_restarted() -> None:
    manager = AgentTaskManager()
    task = create_test_task()

    manager.update_status(task, AgentTaskStatus.CANCELLED)

    with pytest.raises(
        ValueError,
        match="Invalid agent task transition: cancelled -> running",
    ):
        manager.update_status(
            task,
            AgentTaskStatus.RUNNING,
        )
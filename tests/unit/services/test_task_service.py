from orion.core.tasks.events import TaskEventType
from orion.core.tasks.memory_event_repository import (
    InMemoryTaskEventRepository,
)
from orion.core.tasks.memory_repository import InMemoryTaskRepository
from orion.core.tasks.models import TaskStatus
from orion.services.task_service import TaskService


def create_service() -> TaskService:
    return TaskService(
        InMemoryTaskRepository(),
        InMemoryTaskEventRepository(),
    )


def test_service_can_create_task() -> None:
    service = create_service()

    task = service.create_task("Research autonomous AI workforce systems")

    assert task.objective == "Research autonomous AI workforce systems"
    assert task.status == TaskStatus.CREATED


def test_service_can_get_task() -> None:
    service = create_service()

    task = service.create_task("Analyze AI infrastructure")

    retrieved_task = service.get_task(task.id)

    assert retrieved_task is task


def test_service_can_update_task_status() -> None:
    service = create_service()

    task = service.create_task("Prepare an AI market report")

    service.update_task_status(
        task.id,
        TaskStatus.PLANNING,
    )

    assert task.status == TaskStatus.PLANNING


def test_service_can_get_task_events() -> None:
    service = create_service()

    task = service.create_task("Research AI companies")

    service.update_task_status(
        task.id,
        TaskStatus.PLANNING,
    )

    events = service.get_task_events(task.id)

    assert len(events) == 2
    assert events[0].event_type == TaskEventType.TASK_CREATED
    assert events[1].event_type == TaskEventType.STATUS_CHANGED


def test_service_preserves_task_failure_information() -> None:
    service = create_service()

    task = service.create_task("Execute a research task")

    service.update_task_status(
        task.id,
        TaskStatus.PLANNING,
    )

    service.update_task_status(
        task.id,
        TaskStatus.RUNNING,
    )

    service.update_task_status(
        task.id,
        TaskStatus.FAILED,
        error="Research tool failed.",
    )

    assert task.status == TaskStatus.FAILED
    assert task.last_error == "Research tool failed."

    events = service.get_task_events(task.id)

    assert events[-1].event_type == TaskEventType.TASK_FAILED

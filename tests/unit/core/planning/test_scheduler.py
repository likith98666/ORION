from uuid import uuid4

import pytest

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.scheduler import PlanScheduler
from orion.core.planning.steps import PlanStep, PlanStepStatus


def create_step(
    order: int,
    dependencies: frozenset | None = None,
    priority: int = 3,
) -> PlanStep:
    return PlanStep.create(
        plan_id=uuid4(),
        order=order,
        description=f"Step {order}",
        required_capability=AgentCapability.REASONING,
        dependencies=dependencies,
        priority=priority,
    )


def test_get_ready_steps_returns_steps_without_dependencies() -> None:
    step = create_step(1)

    result = PlanScheduler().get_ready_steps([step])

    assert result == [step]
    assert step.status == PlanStepStatus.PENDING


def test_get_ready_steps_returns_step_after_dependency_completes() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    dependency.status = PlanStepStatus.COMPLETED

    result = PlanScheduler().get_ready_steps([dependent, dependency])

    assert result == [dependent]
    assert dependent.status == PlanStepStatus.PENDING


def test_get_ready_steps_does_not_return_step_with_unfinished_dependency() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    result = PlanScheduler().get_ready_steps([dependent, dependency])

    assert result == [dependency]


def test_mark_ready_steps_transitions_pending_steps_to_ready() -> None:
    step = create_step(1)

    result = PlanScheduler().mark_ready_steps([step])

    assert result == [step]
    assert step.status == PlanStepStatus.READY


def test_mark_ready_steps_does_not_modify_non_pending_steps() -> None:
    step = create_step(1)
    step.status = PlanStepStatus.RUNNING

    result = PlanScheduler().mark_ready_steps([step])

    assert result == []
    assert step.status == PlanStepStatus.RUNNING


def test_ready_steps_are_sorted_by_priority_then_order() -> None:
    low = create_step(1, priority=1)
    high_late = create_step(3, priority=5)
    medium = create_step(2, priority=3)
    high_early = create_step(4, priority=5)

    result = PlanScheduler().get_ready_steps(
        [low, high_late, medium, high_early]
    )

    assert result == [
        high_late,
        high_early,
        medium,
        low,
    ]


def test_get_blocked_steps_detects_failed_dependency() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    dependency.status = PlanStepStatus.FAILED

    result = PlanScheduler().get_blocked_steps([dependent, dependency])

    assert result == [dependent]
    assert dependent.status == PlanStepStatus.PENDING


def test_get_blocked_steps_detects_skipped_dependency() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    dependency.status = PlanStepStatus.SKIPPED

    result = PlanScheduler().get_blocked_steps([dependent, dependency])

    assert result == [dependent]


def test_get_blocked_steps_ignores_completed_dependency() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    dependency.status = PlanStepStatus.COMPLETED

    result = PlanScheduler().get_blocked_steps([dependent, dependency])

    assert result == []


def test_mark_blocked_steps_transitions_to_skipped() -> None:
    dependency = create_step(1)
    dependent = create_step(2, frozenset({dependency.id}))

    dependency.status = PlanStepStatus.FAILED

    result = PlanScheduler().mark_blocked_steps([dependent, dependency])

    assert result == [dependent]
    assert dependent.status == PlanStepStatus.SKIPPED


def test_plan_step_priority_defaults_to_three() -> None:
    step = create_step(1)

    assert step.priority == 3


@pytest.mark.parametrize("priority", [0, 6, -1, 10])
def test_plan_step_rejects_invalid_priority(priority: int) -> None:
    with pytest.raises(
        ValueError,
        match="Plan step priority must be between 1 and 5",
    ):
        create_step(1, priority=priority)

"""Execution engine for orchestrating task graphs and enforcing budgets in V2."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from orion.core.missions.graph import MissionTaskGraph
from orion.core.missions.memory import MemoryEntryType, MissionMemory
from orion.core.missions.models import MissionPlan, ResourceBudget, TaskNode, TaskState


class MissionBudgetExceededError(RuntimeError):
    """Raised when execution exceeds the allocated resource budget."""


class MissionCancelledError(RuntimeError):
    """Raised when an operation is attempted on a cancelled mission."""


@dataclass
class MissionExecutionSummary:
    """Summary of a mission execution cycle."""

    mission_id: UUID
    status: TaskState
    total_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    blocked_tasks: int
    duration_seconds: float
    started_at: datetime
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert execution summary to dictionary."""
        return {
            "mission_id": str(self.mission_id),
            "status": self.status.value,
            "total_tasks": self.total_tasks,
            "succeeded_tasks": self.succeeded_tasks,
            "failed_tasks": self.failed_tasks,
            "cancelled_tasks": self.cancelled_tasks,
            "blocked_tasks": self.blocked_tasks,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": list(self.errors),
        }


class MissionExecutionEngine:
    """Orchestrates sequential and dependency-driven task execution with budget guards."""

    def __init__(
        self,
        plan: MissionPlan,
        graph: MissionTaskGraph,
        memory: MissionMemory | None = None,
        mission_budget: ResourceBudget | None = None,
    ) -> None:
        self.plan = plan
        self.graph = graph
        self.memory = memory or MissionMemory(mission_id=plan.mission_id)
        self.mission_budget = mission_budget or ResourceBudget(max_duration_seconds=1800.0)
        self._is_cancelled = False
        self._is_paused = False
        self._started_at: datetime | None = None

    @property
    def is_paused(self) -> bool:
        """Return whether execution is paused by operator intervention."""
        return self._is_paused

    def pause(self, reason: str = "Mission paused by operator.") -> None:
        """Pause the mission execution engine."""
        self._is_paused = True
        self.memory.record(
            entry_type=MemoryEntryType.OBSERVATION,
            title="Mission Paused",
            content=reason,
        )

    def resume(self) -> None:
        """Resume execution of a paused mission engine."""
        self._is_paused = False
        self.memory.record(
            entry_type=MemoryEntryType.OBSERVATION,
            title="Mission Resumed",
            content="Mission resumed by operator.",
        )

    def cancel(self, reason: str = "Mission cancelled by user or operator.") -> None:
        """Cancel the entire mission and all pending/running tasks."""
        self._is_cancelled = True
        self.plan.status = TaskState.CANCELLED
        self.graph.cancel_all(reason=reason)
        self.memory.record(
            entry_type=MemoryEntryType.OBSERVATION,
            title="Mission Cancelled",
            content=reason,
        )

    def execute_next_ready_task(
        self,
        executor_func: Callable[[TaskNode], bool] | None = None,
    ) -> TaskNode | None:
        """Execute the next available ready task.

        If executor_func is not provided, marks the task as SUCCEEDED (or VERIFIED if final).
        """
        if self._is_cancelled:
            raise MissionCancelledError("Cannot execute tasks on a cancelled mission.")
        if self._is_paused:
            return None

        ready_tasks = self.graph.get_ready_tasks()
        if not ready_tasks:
            return None

        target = ready_tasks[0]
        target.mark_state(TaskState.RUNNING)
        start_time = time.time()

        self.memory.record(
            entry_type=MemoryEntryType.ATTEMPT,
            title=f"Started task: {target.title}",
            content=target.description,
            task_id=target.task_id,
        )

        success = True
        err_msg: str | None = None

        try:
            if executor_func is not None:
                success = executor_func(target)
            else:
                success = True
        except Exception as exc:
            success = False
            err_msg = str(exc)

        elapsed = time.time() - start_time
        if elapsed > target.budget.max_duration_seconds:
            success = False
            err_msg = (
                f"Task exceeded duration budget ({elapsed:.2f}s > "
                f"{target.budget.max_duration_seconds}s)."
            )

        if success:
            next_state = (
                TaskState.VERIFIED if "verify" in target.title.lower() else TaskState.SUCCEEDED
            )
            self.graph.mark_task_state(target.task_id, next_state)
            self.memory.record(
                entry_type=MemoryEntryType.DECISION,
                title=f"Completed task: {target.title}",
                content=f"Task transitioned to {next_state.value}.",
                task_id=target.task_id,
            )
        else:
            self.graph.mark_task_state(
                target.task_id, TaskState.FAILED, error_message=err_msg or "Execution failed."
            )
            self.memory.record_failure(
                title=f"Failed task: {target.title}",
                details=err_msg or "Unknown error",
                task_id=target.task_id,
            )

        return target

    def run_all(
        self,
        task_runner: Callable[[TaskNode], bool] | None = None,
        max_cycles: int = 100,
    ) -> MissionExecutionSummary:
        """Run all tasks in topological dependency order until completion or budget exhaustion."""
        self._started_at = datetime.now(UTC)
        start_mono = time.time()
        self.plan.status = TaskState.RUNNING

        cycles = 0
        while not self.graph.is_completed() and cycles < max_cycles:
            cycles += 1
            if self._is_cancelled:
                break

            total_elapsed = time.time() - start_mono
            if total_elapsed > self.mission_budget.max_duration_seconds:
                self.cancel(reason="Overall mission duration budget exceeded.")
                raise MissionBudgetExceededError(
                    f"Mission exceeded budget of {self.mission_budget.max_duration_seconds}s."
                )

            executed = self.execute_next_ready_task(executor_func=task_runner)
            if executed is None:
                # No tasks are ready; if graph is not completed, remaining tasks are blocked
                break

        total_elapsed = time.time() - start_mono
        tasks = list(self.graph.tasks.values())
        succeeded = sum(1 for t in tasks if t.state in (TaskState.SUCCEEDED, TaskState.VERIFIED))
        failed = sum(1 for t in tasks if t.state == TaskState.FAILED)
        cancelled = sum(1 for t in tasks if t.state == TaskState.CANCELLED)
        blocked = sum(1 for t in tasks if t.state == TaskState.BLOCKED)

        if self._is_cancelled:
            overall_status = TaskState.CANCELLED
        elif self._is_paused:
            overall_status = TaskState.BLOCKED
        elif failed > 0 or blocked > 0:
            overall_status = TaskState.FAILED
        else:
            overall_status = TaskState.VERIFIED

        self.plan.status = overall_status
        errors = [t.error_message for t in tasks if t.error_message]

        return MissionExecutionSummary(
            mission_id=self.plan.mission_id,
            status=overall_status,
            total_tasks=len(tasks),
            succeeded_tasks=succeeded,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            blocked_tasks=blocked,
            duration_seconds=total_elapsed,
            started_at=self._started_at,
            completed_at=datetime.now(UTC),
            errors=errors,
        )

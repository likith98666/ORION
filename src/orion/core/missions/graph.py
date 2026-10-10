"""Directed Acyclic Graph (DAG) for managing mission task dependencies and transitions."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from uuid import UUID

from orion.core.missions.models import TaskNode, TaskState


class MissionGraphCycleError(ValueError):
    """Raised when a dependency cycle is detected in the task graph."""


class TaskNotFoundError(KeyError):
    """Raised when an operation targets a nonexistent task in the graph."""


class MissionTaskGraph:
    """Manages the dependency graph and topological scheduling of tasks in a mission."""

    def __init__(self, mission_id: UUID) -> None:
        self.mission_id = mission_id
        self._tasks: dict[UUID, TaskNode] = {}
        self._dependents: dict[UUID, set[UUID]] = {}  # task -> tasks that depend on it

    @property
    def tasks(self) -> dict[UUID, TaskNode]:
        """Return shallow copy of tasks dictionary."""
        return dict(self._tasks)

    def add_task(self, task: TaskNode) -> None:
        """Add a task node to the graph."""
        if not isinstance(task, TaskNode):
            raise TypeError("task must be a TaskNode instance.")
        if task.task_id in self._tasks:
            raise ValueError(f"Task with ID {task.task_id} already exists in graph.")

        self._tasks[task.task_id] = task
        if task.task_id not in self._dependents:
            self._dependents[task.task_id] = set()

        # Register existing dependencies
        for dep_id in task.dependencies:
            if dep_id in self._tasks:
                self._dependents.setdefault(dep_id, set()).add(task.task_id)

        # Validate no cycles introduced
        if self.has_cycles():
            # Rollback
            del self._tasks[task.task_id]
            for dep_id in task.dependencies:
                if dep_id in self._dependents:
                    self._dependents[dep_id].discard(task.task_id)
            raise MissionGraphCycleError(
                f"Adding task '{task.title}' ({task.task_id}) introduces a cycle."
            )

    def add_dependency(self, task_id: UUID, depends_on_id: UUID) -> None:
        """Declare that task_id depends on depends_on_id completing first."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task {task_id} not found in graph.")
        if depends_on_id not in self._tasks:
            raise TaskNotFoundError(f"Dependency target {depends_on_id} not found in graph.")
        if task_id == depends_on_id:
            raise MissionGraphCycleError("A task cannot depend on itself.")

        self._tasks[task_id].dependencies.add(depends_on_id)
        self._dependents.setdefault(depends_on_id, set()).add(task_id)

        if self.has_cycles():
            self._tasks[task_id].dependencies.remove(depends_on_id)
            self._dependents[depends_on_id].remove(task_id)
            raise MissionGraphCycleError(
                f"Dependency from {task_id} to {depends_on_id} creates a cycle."
            )

    def get_task(self, task_id: UUID) -> TaskNode:
        """Retrieve task by ID."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task {task_id} not found.")
        return self._tasks[task_id]

    def has_cycles(self) -> bool:
        """Detect whether the graph contains any cycles via Kahn's algorithm."""
        in_degree: dict[UUID, int] = {tid: len(t.dependencies) for tid, t in self._tasks.items()}
        queue: deque[UUID] = deque([tid for tid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for child in self._dependents.get(node, set()):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return visited_count != len(self._tasks)

    def topological_sort(self) -> list[TaskNode]:
        """Return tasks ordered topologically by dependency order."""
        if self.has_cycles():
            raise MissionGraphCycleError("Cannot sort graph containing cycles.")

        in_degree: dict[UUID, int] = {tid: len(t.dependencies) for tid, t in self._tasks.items()}
        queue: deque[UUID] = deque([tid for tid, deg in in_degree.items() if deg == 0])
        ordered: list[TaskNode] = []

        while queue:
            node = queue.popleft()
            ordered.append(self._tasks[node])
            for child in self._dependents.get(node, set()):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return ordered

    def get_ready_tasks(self) -> list[TaskNode]:
        """Return all tasks whose dependencies have succeeded and are ready to run."""
        ready: list[TaskNode] = []
        for task in self._tasks.values():
            if task.state != TaskState.PENDING:
                continue

            deps_satisfied = True
            for dep_id in task.dependencies:
                dep_task = self._tasks.get(dep_id)
                if dep_task is None or dep_task.state not in (
                    TaskState.SUCCEEDED,
                    TaskState.VERIFIED,
                ):
                    deps_satisfied = False
                    break

            if deps_satisfied:
                ready.append(task)

        # Sort ready tasks by priority (CRITICAL -> HIGH -> MEDIUM -> LOW)
        priority_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
        }
        ready.sort(key=lambda t: priority_order.get(t.priority.value, 2))
        return ready

    def mark_task_state(
        self, task_id: UUID, new_state: TaskState, error_message: str | None = None
    ) -> None:
        """Update a task's state and cascade blocked status if failed."""
        task = self.get_task(task_id)
        task.mark_state(new_state, error_message=error_message)

        # If a task fails or is cancelled, cascade BLOCKED to pending downstream dependents
        if new_state in (TaskState.FAILED, TaskState.CANCELLED):
            self._cascade_blocked(task_id)

    def _cascade_blocked(self, failed_task_id: UUID) -> None:
        """Mark all transitive downstream dependents as BLOCKED."""
        visited: set[UUID] = set()
        queue: deque[UUID] = deque(self._dependents.get(failed_task_id, set()))

        while queue:
            curr_id = queue.popleft()
            if curr_id in visited:
                continue
            visited.add(curr_id)

            curr_task = self._tasks.get(curr_id)
            if curr_task and curr_task.state in (TaskState.PENDING, TaskState.READY):
                curr_task.mark_state(
                    TaskState.BLOCKED,
                    error_message=f"Prerequisite task {failed_task_id} failed or was cancelled.",
                )

            for next_dep in self._dependents.get(curr_id, set()):
                queue.append(next_dep)

    def cancel_all(self, reason: str = "Mission cancelled.") -> Sequence[UUID]:
        """Cancel all pending, ready, or running tasks."""
        cancelled_ids: list[UUID] = []
        for task in self._tasks.values():
            if task.state in (TaskState.PENDING, TaskState.READY, TaskState.RUNNING):
                task.mark_state(TaskState.CANCELLED, error_message=reason)
                cancelled_ids.append(task.task_id)
        return tuple(cancelled_ids)

    def is_completed(self) -> bool:
        """Check if all tasks in the graph have reached a terminal state."""
        terminal_states = (
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.VERIFIED,
            TaskState.BLOCKED,
        )
        return all(task.state in terminal_states for task in self._tasks.values())

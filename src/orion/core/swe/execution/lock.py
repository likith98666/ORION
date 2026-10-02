"""Deterministic workspace locking to prevent unsafe concurrent modifications."""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from orion.core.swe.execution.errors import WorkspaceLockedError


@dataclass(frozen=True)
class LockRecord:
    """Audit descriptor of an active workspace lock."""

    workspace_id: UUID
    execution_id: UUID
    acquired_at: datetime


class WorkspaceLockManager:
    """Thread-safe, deterministic workspace lock manager preventing concurrent patch application."""

    def __init__(self) -> None:
        self._mutex = threading.RLock()
        self._locks: dict[UUID, LockRecord] = {}
        self._depths: dict[UUID, int] = {}

    def is_locked(self, workspace_id: UUID) -> bool:
        """Check whether a workspace is currently locked."""
        with self._mutex:
            return workspace_id in self._locks

    def get_lock_holder(self, workspace_id: UUID) -> UUID | None:
        """Return execution_id holding the lock, or None."""
        with self._mutex:
            record = self._locks.get(workspace_id)
            return record.execution_id if record else None

    def acquire(self, workspace_id: UUID, execution_id: UUID) -> None:
        """Acquire lock on workspace_id for execution_id.

        Raises:
            WorkspaceLockedError: If workspace is locked by a different execution.
        """
        with self._mutex:
            current_record = self._locks.get(workspace_id)
            if current_record is not None:
                if current_record.execution_id != execution_id:
                    raise WorkspaceLockedError(
                        f"Workspace '{workspace_id}' is locked by execution "
                        f"'{current_record.execution_id}' since "
                        f"{current_record.acquired_at.isoformat()}."
                    )
                # Reentrant acquisition for same execution
                self._depths[workspace_id] = self._depths.get(workspace_id, 1) + 1
                return

            self._locks[workspace_id] = LockRecord(
                workspace_id=workspace_id,
                execution_id=execution_id,
                acquired_at=datetime.now(UTC),
            )
            self._depths[workspace_id] = 1

    def release(self, workspace_id: UUID, execution_id: UUID) -> None:
        """Release lock on workspace_id for execution_id."""
        with self._mutex:
            current_record = self._locks.get(workspace_id)
            if current_record is None:
                return

            if current_record.execution_id != execution_id:
                raise WorkspaceLockedError(
                    f"Execution '{execution_id}' cannot release lock held by "
                    f"'{current_record.execution_id}' on workspace '{workspace_id}'."
                )

            current_depth = self._depths.get(workspace_id, 1)
            if current_depth > 1:
                self._depths[workspace_id] = current_depth - 1
            else:
                self._locks.pop(workspace_id, None)
                self._depths.pop(workspace_id, None)

    @contextmanager
    def lock(self, workspace_id: UUID, execution_id: UUID) -> Generator[None, None, None]:
        """Context manager for failure-safe lock acquisition and release."""
        self.acquire(workspace_id, execution_id)
        try:
            yield
        finally:
            self.release(workspace_id, execution_id)

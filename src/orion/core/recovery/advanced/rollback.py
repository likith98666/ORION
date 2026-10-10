"""Intelligent workspace snapshotting, partial rollback, and integrity verification in V5."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache"}


@dataclass(frozen=True)
class FileSnapshot:
    """Record of a single file's state at snapshot time."""

    rel_path: str
    sha256_hash: str
    size_bytes: int
    content: bytes


@dataclass
class WorkspaceSnapshot:
    """Immutable image of workspace files before executing potentially destructive actions."""

    snapshot_id: UUID
    root_dir: str
    files: dict[str, FileSnapshot] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "snapshot_id": str(self.snapshot_id),
            "root_dir": self.root_dir,
            "total_files": len(self.files),
            "created_at": self.created_at.isoformat(),
        }


class IntelligentRollbackManager:
    """Captures filesystem snapshots and performs atomic full or partial rollbacks."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.root_dir = Path(workspace_root).resolve()
        if not self.root_dir.exists():
            raise ValueError(f"Workspace root does not exist: {workspace_root}")

    def capture_snapshot(self) -> WorkspaceSnapshot:
        """Capture SHA-256 hashes and content of all non-excluded files in the workspace."""
        snapshot = WorkspaceSnapshot(snapshot_id=uuid4(), root_dir=str(self.root_dir))

        for file_path in self.root_dir.rglob("*"):
            if file_path.is_file():
                parts = set(file_path.relative_to(self.root_dir).parts)
                if parts.intersection(EXCLUDE_DIRS):
                    continue

                rel_str = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
                content = file_path.read_bytes()
                sha = hashlib.sha256(content).hexdigest()

                snapshot.files[rel_str] = FileSnapshot(
                    rel_path=rel_str,
                    sha256_hash=sha,
                    size_bytes=len(content),
                    content=content,
                )

        return snapshot

    def rollback(
        self,
        snapshot: WorkspaceSnapshot,
        target_files: Sequence[str] | None = None,
    ) -> tuple[int, list[str]]:
        """Restore workspace to snapshot state.

        If target_files is provided, restores only those files.
        """
        restored_count = 0
        restored_files: list[str] = []

        files_to_restore = (
            [f.replace("\\", "/") for f in target_files]
            if target_files is not None
            else list(snapshot.files.keys())
        )

        for rel_path in files_to_restore:
            if rel_path in snapshot.files:
                file_snap = snapshot.files[rel_path]
                full_dest = (self.root_dir / rel_path).resolve()
                try:
                    full_dest.relative_to(self.root_dir)
                except ValueError:
                    raise ValueError(f"Path traversal detected in rollback: '{rel_path}'") from None
                full_dest.parent.mkdir(parents=True, exist_ok=True)
                full_dest.write_bytes(file_snap.content)
                restored_count += 1
                restored_files.append(rel_path)

        # Remove untracked files created since snapshot if doing full rollback
        if target_files is None:
            for file_path in self.root_dir.rglob("*"):
                if file_path.is_file():
                    parts = set(file_path.relative_to(self.root_dir).parts)
                    if parts.intersection(EXCLUDE_DIRS):
                        continue
                    rel_str = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
                    if rel_str not in snapshot.files:
                        file_path.unlink()

        return restored_count, restored_files

    def verify_integrity(self, snapshot: WorkspaceSnapshot) -> tuple[bool, list[str]]:
        """Compare current workspace state against snapshot checksums."""
        drift: list[str] = []
        for rel_path, file_snap in snapshot.files.items():
            full_path = self.root_dir / rel_path
            if not full_path.exists():
                drift.append(f"Missing file: '{rel_path}'")
                continue
            curr_content = full_path.read_bytes()
            curr_sha = hashlib.sha256(curr_content).hexdigest()
            if curr_sha != file_snap.sha256_hash:
                drift.append(f"Content modified: '{rel_path}'")

        return len(drift) == 0, drift

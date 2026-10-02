"""Pre-apply snapshot creation and deterministic recovery for workspace mutations."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from orion.core.swe.cognitive.patch_contracts import PatchProposal
from orion.core.swe.execution.contracts import FileSnapshot, PatchRecoveryPoint
from orion.core.swe.execution.errors import PatchRecoveryError
from orion.core.workspace.models import Workspace


class PatchRecoveryManager:
    """Manages creation and deterministic restoration of pre-apply recovery points."""

    def create_recovery_point(
        self,
        workspace: Workspace,
        patch_proposal: PatchProposal,
        execution_id: UUID,
    ) -> PatchRecoveryPoint:
        """Capture pre-apply snapshots of all files affected by the proposal.

        Records contents, hashes, and existence status before any disk mutation occurs.
        """
        snapshots: dict[str, FileSnapshot] = {}

        for op in patch_proposal.operations:
            target_path = workspace.validate_path(op.path)
            existed = target_path.exists() and target_path.is_file()

            if existed:
                try:
                    content = target_path.read_text(encoding="utf-8")
                    sha256_hash = hashlib.sha256(content.encode("utf-8")).hexdigest().lower()
                except Exception as exc:
                    raise PatchRecoveryError(
                        f"Failed reading pre-apply state for '{op.path}': {exc}"
                    ) from exc
                snapshots[op.path] = FileSnapshot(
                    path=op.path,
                    existed=True,
                    content=content,
                    sha256_hash=sha256_hash,
                )
            else:
                snapshots[op.path] = FileSnapshot(
                    path=op.path,
                    existed=False,
                    content=None,
                    sha256_hash=None,
                )

        return PatchRecoveryPoint(
            recovery_id=uuid4(),
            patch_id=patch_proposal.task_id,
            task_id=patch_proposal.task_id,
            execution_id=execution_id,
            workspace_id=workspace.workspace_id,
            created_at=datetime.now(UTC),
            snapshots=snapshots,
        )

    def restore_recovery_point(
        self,
        workspace: Workspace,
        recovery_point: PatchRecoveryPoint,
    ) -> tuple[bool, str]:
        """Restore workspace to the exact pre-apply snapshot state.

        Returns (success, description).
        """
        restored_files: list[str] = []
        errors: list[str] = []

        for rel_path, snapshot in recovery_point.snapshots.items():
            try:
                target_path = workspace.validate_path(rel_path)

                if snapshot.existed:
                    # Restore pre-existing file content
                    if snapshot.content is None:
                        errors.append(
                            f"Missing snapshot content for pre-existing file '{rel_path}'"
                        )
                        continue

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(snapshot.content, encoding="utf-8", newline="\n")

                    # Verify restored hash
                    restored_hash = hashlib.sha256(
                        target_path.read_text(encoding="utf-8").encode("utf-8")
                    ).hexdigest().lower()

                    if restored_hash != snapshot.sha256_hash:
                        errors.append(
                            f"Restored hash mismatch for '{rel_path}': "
                            f"expected {snapshot.sha256_hash}, got {restored_hash}"
                        )
                    else:
                        restored_files.append(rel_path)
                else:
                    # File did not exist before application; remove if created
                    if target_path.exists():
                        target_path.unlink()
                    restored_files.append(rel_path)

            except Exception as exc:
                errors.append(f"Failed restoring '{rel_path}': {exc}")

        if errors:
            return False, f"Recovery encountered errors: {'; '.join(errors)}"

        return True, f"Successfully restored {len(restored_files)} files to pre-apply state."

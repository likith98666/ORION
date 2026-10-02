"""Authoritative, secure application service for approved patch proposals."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from orion.core.observability.context import TelemetryContext
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_service import ApprovalService
from orion.core.swe.cognitive.patch_approval import PatchApprovalPackage
from orion.core.swe.cognitive.patch_contracts import (
    PatchOperationType,
    PatchProposal,
)
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.contracts import (
    AppliedOperationRecord,
    PatchApplicationResult,
    PostApplyIntegrityResult,
)
from orion.core.swe.execution.errors import (
    ApprovalIntegrityError,
    PatchApplicationError,
    RevokedApprovalError,
    StaleApprovalError,
    UnapprovedPatchError,
)
from orion.core.swe.execution.lock import WorkspaceLockManager
from orion.core.swe.execution.recovery import PatchRecoveryManager
from orion.core.swe.execution.states import PatchExecutionLifecycle, PatchExecutionState
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.repository.security import is_protected_path
from orion.core.workspace.errors import PathOutsideWorkspaceError, PathSecurityError
from orion.core.workspace.models import Workspace


class PatchApplicationAuthority:
    """Sole authoritative service permitted to apply approved patches to the workspace."""

    def __init__(
        self,
        workspace: Workspace,
        approval_service: ApprovalService,
        lock_manager: WorkspaceLockManager | None = None,
        recovery_manager: PatchRecoveryManager | None = None,
        ledger: EvidenceLedger | None = None,
        telemetry_context: TelemetryContext | None = None,
    ) -> None:
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be a Workspace instance.")
        if not isinstance(approval_service, ApprovalService):
            raise TypeError("approval_service must be an ApprovalService instance.")

        self._workspace = workspace
        self._approval_service = approval_service
        self._lock_manager = lock_manager or WorkspaceLockManager()
        self._recovery_manager = recovery_manager or PatchRecoveryManager()
        self._ledger = ledger
        self._telemetry_context = telemetry_context or TelemetryContext()

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    @property
    def approval_service(self) -> ApprovalService:
        return self._approval_service

    @property
    def lock_manager(self) -> WorkspaceLockManager:
        return self._lock_manager

    @property
    def recovery_manager(self) -> PatchRecoveryManager:
        return self._recovery_manager

    def compute_patch_fingerprint(self, proposal: PatchProposal) -> str:
        """Compute deterministic SHA-256 fingerprint of patch proposal contents."""
        hasher = hashlib.sha256()
        for op in proposal.operations:
            chunk = (
                f"{op.operation_type.value}:{op.path}:"
                f"{op.expected_hash or ''}:{op.new_content or ''}"
            )
            hasher.update(chunk.encode("utf-8"))
        return hasher.hexdigest()

    def verify_approval_integrity(
        self,
        package: PatchApprovalPackage,
        execution_id: UUID,
    ) -> None:
        """Verify the approval package against ApprovalService and execution context."""
        if not isinstance(package, PatchApprovalPackage):
            raise TypeError("package must be a PatchApprovalPackage instance.")

        if not package.is_approved:
            if package.status == ApprovalStatus.DENIED:
                raise RevokedApprovalError(
                    f"Patch approval request '{package.request_id}' has been DENIED."
                )
            raise UnapprovedPatchError(
                f"Patch approval request '{package.request_id}' is not in APPROVED state "
                f"(current status: '{package.status.value}')."
            )

        # Query authoritative repository in ApprovalService
        try:
            stored_request = self._approval_service._repository.get(package.request_id)
        except Exception as exc:
            raise UnapprovedPatchError(
                f"Approval request '{package.request_id}' not found in ApprovalService: {exc}"
            ) from exc

        if stored_request is None:
            raise UnapprovedPatchError(
                f"Approval request '{package.request_id}' does not exist."
            )

        if stored_request.status != ApprovalStatus.APPROVED:
            if stored_request.status == ApprovalStatus.DENIED:
                raise RevokedApprovalError(
                    f"Approval request '{package.request_id}' has been denied or revoked."
                )
            raise UnapprovedPatchError(
                f"Approval request '{package.request_id}' has status "
                f"'{stored_request.status.value}'."
            )

        # Check expiration
        if stored_request.expires_at is not None:
            now = datetime.now(stored_request.expires_at.tzinfo or UTC)
            if now > stored_request.expires_at:
                raise StaleApprovalError(
                    f"Approval request '{package.request_id}' expired at "
                    f"{stored_request.expires_at.isoformat()}."
                )

        # Verify agent identity
        if stored_request.agent_id != package.agent_id:
            raise ApprovalIntegrityError(
                f"Approval agent '{stored_request.agent_id}' does not match "
                f"package agent '{package.agent_id}'."
            )

        # Verify execution binding if present
        if stored_request.execution_id is not None and stored_request.execution_id != execution_id:
            raise ApprovalIntegrityError(
                f"Approval execution '{stored_request.execution_id}' does not match "
                f"execution '{execution_id}'."
            )

    def _sanitize_path_at_boundary(self, raw_path: str) -> str:
        """Repeat strict path sanitization at the application authority boundary."""
        path_str = raw_path.strip().replace("\\", "/")

        if "\0" in path_str:
            raise PatchApplicationError(f"Path '{path_str}' contains forbidden null bytes.")

        if len(path_str) >= 2 and path_str[1] == ":":
            raise PatchApplicationError(f"Absolute drive path '{path_str}' is forbidden.")

        if raw_path.strip().startswith(("\\\\", "//")):
            raise PatchApplicationError(f"UNC path '{raw_path}' is forbidden.")

        if path_str.startswith("/"):
            raise PatchApplicationError(f"Absolute root path '{path_str}' is forbidden.")

        if ".." in path_str.split("/"):
            raise PatchApplicationError(f"Path traversal sequence '..' in '{path_str}' rejected.")

        if is_protected_path(path_str):
            raise PatchApplicationError(f"Target '{path_str}' is a protected credential file.")

        try:
            self._workspace.validate_path(path_str)
        except (PathOutsideWorkspaceError, PathSecurityError) as exc:
            raise PatchApplicationError(
                f"Target '{path_str}' escapes workspace boundary: {exc}"
            ) from exc

        return path_str

    def verify_post_apply_integrity(
        self,
        proposal: PatchProposal,
    ) -> PostApplyIntegrityResult:
        """Verify that applied changes on disk strictly match the patch proposal."""
        verified_files: list[str] = []
        missing_files: list[str] = []
        hash_mismatches: list[str] = []
        boundary_violations: list[str] = []

        for op in proposal.operations:
            try:
                target_path = self._workspace.validate_path(op.path)
            except Exception as exc:
                boundary_violations.append(f"{op.path}: {exc}")
                continue

            if op.operation_type in (
                PatchOperationType.CREATE_FILE,
                PatchOperationType.MODIFY_FILE,
            ):
                if not target_path.exists() or not target_path.is_file():
                    missing_files.append(op.path)
                    continue

                content = target_path.read_text(encoding="utf-8")
                actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest().lower()
                expected_new_hash = hashlib.sha256(
                    (op.new_content or "").encode("utf-8")
                ).hexdigest().lower()

                if actual_hash != expected_new_hash:
                    hash_mismatches.append(
                        f"{op.path} (expected {expected_new_hash[:8]}, got {actual_hash[:8]})"
                    )
                else:
                    verified_files.append(op.path)

            elif op.operation_type == PatchOperationType.DELETE_FILE:
                if target_path.exists():
                    missing_files.append(f"{op.path} (file still exists)")
                else:
                    verified_files.append(op.path)

        valid = not (missing_files or hash_mismatches or boundary_violations)
        details = (
            "Post-apply filesystem integrity check passed."
            if valid
            else (
                f"Integrity check failed: missing={missing_files}, "
                f"hash_mismatches={hash_mismatches}, boundary={boundary_violations}"
            )
        )

        return PostApplyIntegrityResult(
            valid=valid,
            verified_files=tuple(verified_files),
            missing_files=tuple(missing_files),
            hash_mismatches=tuple(hash_mismatches),
            boundary_violations=tuple(boundary_violations),
            details=details,
        )

    def apply_patch(
        self,
        approval_package: PatchApprovalPackage,
        execution_id: UUID | None = None,
    ) -> PatchApplicationResult:
        """Apply an approved PatchProposal within strict workspace boundaries and locks."""
        if not isinstance(approval_package, PatchApprovalPackage):
            raise TypeError("approval_package must be a PatchApprovalPackage instance.")

        effective_execution_id = execution_id or uuid4()
        proposal = approval_package.patch_proposal

        # 1. State machine initialization
        lifecycle = PatchExecutionLifecycle(initial_state=PatchExecutionState.AUTHORIZED)

        # 2. Verify approval integrity
        self.verify_approval_integrity(approval_package, effective_execution_id)

        # 3. Verify path containment and security at boundary before any filesystem mutation
        for op in proposal.operations:
            self._sanitize_path_at_boundary(op.path)

        # 4. Acquire workspace lock to prevent concurrent modifications
        with self._lock_manager.lock(self._workspace.workspace_id, effective_execution_id):
            lifecycle.transition_to(
                PatchExecutionState.APPLYING,
                reason="Acquired workspace lock, beginning controlled application",
            )

            # 5. Create pre-apply recovery point
            recovery_point = self._recovery_manager.create_recovery_point(
                workspace=self._workspace,
                patch_proposal=proposal,
                execution_id=effective_execution_id,
            )

            completed_records: list[AppliedOperationRecord] = []

            # 5. Pre-validate operations on disk against optimistic hashes
            for op in proposal.operations:
                sanitized_path = self._sanitize_path_at_boundary(op.path)
                target_file = self._workspace.validate_path(sanitized_path)

                if op.operation_type == PatchOperationType.CREATE_FILE:
                    if target_file.exists():
                        lifecycle.transition_to(
                            PatchExecutionState.FAILED,
                            reason="Pre-check failed",
                        )
                        return PatchApplicationResult(
                            patch_id=proposal.task_id,
                            task_id=proposal.task_id,
                            execution_id=effective_execution_id,
                            status=PatchExecutionState.FAILED,
                            completed_operations=(),
                            failed_operation=op,
                            remaining_operations=proposal.operations,
                            error=f"Cannot CREATE_FILE: path '{sanitized_path}' already exists.",
                            affected_files=proposal.affected_files,
                        )

                elif op.operation_type in (
                    PatchOperationType.MODIFY_FILE,
                    PatchOperationType.DELETE_FILE,
                ):
                    if not target_file.exists():
                        lifecycle.transition_to(
                            PatchExecutionState.FAILED,
                            reason="Pre-check failed",
                        )
                        return PatchApplicationResult(
                            patch_id=proposal.task_id,
                            task_id=proposal.task_id,
                            execution_id=effective_execution_id,
                            status=PatchExecutionState.FAILED,
                            completed_operations=(),
                            failed_operation=op,
                            remaining_operations=proposal.operations,
                            error=f"Target file '{sanitized_path}' not found on disk.",
                            affected_files=proposal.affected_files,
                        )

                    # Hash check
                    current_content = target_file.read_text(encoding="utf-8")
                    current_hash = hashlib.sha256(
                        current_content.encode("utf-8")
                    ).hexdigest().lower()

                    if op.expected_hash is not None and op.expected_hash:
                        if op.expected_hash.lower() != current_hash:
                            lifecycle.transition_to(
                                PatchExecutionState.FAILED,
                                reason="Stale hash detected",
                            )
                            return PatchApplicationResult(
                                patch_id=proposal.task_id,
                                task_id=proposal.task_id,
                                execution_id=effective_execution_id,
                                status=PatchExecutionState.FAILED,
                                completed_operations=(),
                                failed_operation=op,
                                remaining_operations=proposal.operations,
                                error=(
                                    f"Stale hash on '{sanitized_path}': "
                                    f"expected {op.expected_hash}, got {current_hash}."
                                ),
                                affected_files=proposal.affected_files,
                            )

            # 6. Apply operations sequentially
            for idx, op in enumerate(proposal.operations):
                sanitized_path = self._sanitize_path_at_boundary(op.path)
                target_file = self._workspace.validate_path(sanitized_path)

                try:
                    if op.operation_type == PatchOperationType.CREATE_FILE:
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        content = op.new_content or ""
                        target_file.write_text(content, encoding="utf-8", newline="\n")
                        new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest().lower()
                        record = AppliedOperationRecord(
                            operation_type=op.operation_type,
                            path=sanitized_path,
                            previous_hash=None,
                            new_hash=new_hash,
                            bytes_written=len(content.encode("utf-8")),
                            lines_added=len(content.splitlines()),
                            lines_removed=0,
                        )
                        completed_records.append(record)

                    elif op.operation_type == PatchOperationType.MODIFY_FILE:
                        prev_content = target_file.read_text(encoding="utf-8")
                        prev_hash = hashlib.sha256(
                            prev_content.encode("utf-8")
                        ).hexdigest().lower()
                        content = op.new_content or ""
                        target_file.write_text(content, encoding="utf-8", newline="\n")
                        new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest().lower()
                        record = AppliedOperationRecord(
                            operation_type=op.operation_type,
                            path=sanitized_path,
                            previous_hash=prev_hash,
                            new_hash=new_hash,
                            bytes_written=len(content.encode("utf-8")),
                            lines_added=op.lines_added,
                            lines_removed=op.lines_removed,
                        )
                        completed_records.append(record)

                    elif op.operation_type == PatchOperationType.DELETE_FILE:
                        prev_content = target_file.read_text(encoding="utf-8")
                        prev_hash = hashlib.sha256(
                            prev_content.encode("utf-8")
                        ).hexdigest().lower()
                        target_file.unlink()
                        record = AppliedOperationRecord(
                            operation_type=op.operation_type,
                            path=sanitized_path,
                            previous_hash=prev_hash,
                            new_hash=None,
                            bytes_written=0,
                            lines_added=0,
                            lines_removed=op.lines_removed,
                        )
                        completed_records.append(record)

                except Exception as exc:
                    # Operation failed: initiate deterministic recovery
                    remaining = tuple(proposal.operations[idx + 1:])
                    lifecycle.transition_to(
                        PatchExecutionState.PARTIALLY_APPLIED,
                        reason=f"Operation failed on '{sanitized_path}': {exc}",
                    )
                    lifecycle.transition_to(
                        PatchExecutionState.RECOVERING,
                        reason="Restoring pre-apply snapshot",
                    )

                    restored, recovery_msg = self._recovery_manager.restore_recovery_point(
                        workspace=self._workspace,
                        recovery_point=recovery_point,
                    )

                    final_status = (
                        PatchExecutionState.RECOVERED
                        if restored
                        else PatchExecutionState.RECOVERY_FAILED
                    )
                    lifecycle.transition_to(final_status, reason=recovery_msg)

                    self._record_evidence(
                        stage=SWETaskStage.IMPLEMENT_CHANGE,
                        category=EvidenceCategory.RECOVERY_EVENT,
                        summary=f"Patch application failure on '{sanitized_path}': {recovery_msg}",
                        content=str(exc),
                        task_id=proposal.task_id,
                        execution_id=effective_execution_id,
                        metadata={
                            "failed_path": sanitized_path,
                            "recovery_status": final_status.value,
                            "completed_count": len(completed_records),
                        },
                    )

                    return PatchApplicationResult(
                        patch_id=proposal.task_id,
                        task_id=proposal.task_id,
                        execution_id=effective_execution_id,
                        status=final_status,
                        completed_operations=tuple(completed_records),
                        failed_operation=op,
                        remaining_operations=remaining,
                        error=f"Application failed on '{sanitized_path}': {exc}",
                        recovery_status=recovery_msg,
                        affected_files=proposal.affected_files,
                    )

            # 7. Post-apply integrity check
            integrity_result = self.verify_post_apply_integrity(proposal)
            if not integrity_result.valid:
                lifecycle.transition_to(
                    PatchExecutionState.PARTIALLY_APPLIED,
                    reason="Post-apply integrity mismatch",
                )
                lifecycle.transition_to(
                    PatchExecutionState.RECOVERING,
                    reason="Reverting mutations due to integrity discrepancy",
                )
                restored, recovery_msg = self._recovery_manager.restore_recovery_point(
                    workspace=self._workspace,
                    recovery_point=recovery_point,
                )
                final_status = (
                    PatchExecutionState.RECOVERED
                    if restored
                    else PatchExecutionState.RECOVERY_FAILED
                )
                lifecycle.transition_to(final_status, reason=recovery_msg)

                return PatchApplicationResult(
                    patch_id=proposal.task_id,
                    task_id=proposal.task_id,
                    execution_id=effective_execution_id,
                    status=final_status,
                    completed_operations=tuple(completed_records),
                    error=f"Post-apply integrity verification failed: {integrity_result.details}",
                    recovery_status=recovery_msg,
                    affected_files=proposal.affected_files,
                )

            # 8. Success: transition to APPLIED
            lifecycle.transition_to(
                PatchExecutionState.APPLIED,
                reason="All operations applied and post-apply integrity verified",
            )

            # Record OBSERVED evidence in EvidenceLedger for each applied file change
            for rec in completed_records:
                self._record_evidence(
                    stage=SWETaskStage.IMPLEMENT_CHANGE,
                    category=EvidenceCategory.FILE_CHANGE,
                    summary=f"Applied {rec.operation_type.value} to '{rec.path}'",
                    content=proposal.unified_diff[:4000],
                    task_id=proposal.task_id,
                    execution_id=effective_execution_id,
                    metadata={
                        "path": rec.path,
                        "operation_type": rec.operation_type.value,
                        "new_hash": rec.new_hash,
                        "status": PatchExecutionState.APPLIED.value,
                        "integrity_valid": True,
                    },
                )

            return PatchApplicationResult(
                patch_id=proposal.task_id,
                task_id=proposal.task_id,
                execution_id=effective_execution_id,
                status=PatchExecutionState.APPLIED,
                completed_operations=tuple(completed_records),
                error=None,
                recovery_status=None,
                affected_files=proposal.affected_files,
            )

    def _record_evidence(
        self,
        stage: SWETaskStage,
        category: EvidenceCategory,
        summary: str,
        content: str,
        task_id: UUID | None,
        execution_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record OBSERVED evidence in the evidence ledger if configured."""
        if self._ledger is not None:
            self._ledger.record_observed(
                stage=stage,
                source="PatchApplicationAuthority",
                content=content,
                category=category,
                summary=summary,
                task_id=task_id,
                execution_id=execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata=metadata,
            )

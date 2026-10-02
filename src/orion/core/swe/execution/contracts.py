"""Contracts and data transfer objects for Phase 5 controlled execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from orion.core.swe.cognitive.patch_contracts import PatchOperation, PatchOperationType
from orion.core.swe.execution.states import PatchExecutionState
from orion.core.verification.models import VerificationResult


@dataclass(frozen=True)
class FileSnapshot:
    """Pre-apply snapshot of an individual file within the workspace boundary."""

    path: str
    existed: bool
    content: str | None = None
    sha256_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "existed": self.existed,
            "sha256_hash": self.sha256_hash,
            "content_length": len(self.content) if self.content is not None else 0,
        }


@dataclass(frozen=True)
class PatchRecoveryPoint:
    """Complete pre-apply recovery snapshot binding affected files before modification."""

    recovery_id: UUID
    patch_id: UUID | None
    task_id: UUID | None
    execution_id: UUID
    workspace_id: UUID
    created_at: datetime
    snapshots: dict[str, FileSnapshot]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_id": str(self.recovery_id),
            "patch_id": str(self.patch_id) if self.patch_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id),
            "workspace_id": str(self.workspace_id),
            "created_at": self.created_at.isoformat(),
            "snapshots": {p: s.to_dict() for p, s in self.snapshots.items()},
        }


@dataclass(frozen=True)
class AppliedOperationRecord:
    """Deterministic record of an applied filesystem modification."""

    operation_type: PatchOperationType
    path: str
    previous_hash: str | None
    new_hash: str | None
    bytes_written: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    applied_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_type": self.operation_type.value,
            "path": self.path,
            "previous_hash": self.previous_hash,
            "new_hash": self.new_hash,
            "bytes_written": self.bytes_written,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "applied_at": self.applied_at.isoformat(),
        }


@dataclass(frozen=True)
class PatchApplicationResult:
    """Comprehensive result of controlled patch application."""

    patch_id: UUID | None
    task_id: UUID | None
    execution_id: UUID
    status: PatchExecutionState
    completed_operations: tuple[AppliedOperationRecord, ...]
    failed_operation: PatchOperation | None = None
    remaining_operations: tuple[PatchOperation, ...] = ()
    error: str | None = None
    recovery_status: str | None = None
    affected_files: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_applied(self) -> bool:
        return self.status == PatchExecutionState.APPLIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": str(self.patch_id) if self.patch_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id),
            "status": self.status.value,
            "completed_operations": [op.to_dict() for op in self.completed_operations],
            "failed_operation": self.failed_operation.to_dict() if self.failed_operation else None,
            "remaining_operations_count": len(self.remaining_operations),
            "error": self.error,
            "recovery_status": self.recovery_status,
            "affected_files": list(self.affected_files),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class PostApplyIntegrityResult:
    """Result of post-apply filesystem verification."""

    valid: bool
    verified_files: tuple[str, ...]
    missing_files: tuple[str, ...] = ()
    unexpected_files: tuple[str, ...] = ()
    hash_mismatches: tuple[str, ...] = ()
    boundary_violations: tuple[str, ...] = ()
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "verified_files": list(self.verified_files),
            "missing_files": list(self.missing_files),
            "unexpected_files": list(self.unexpected_files),
            "hash_mismatches": list(self.hash_mismatches),
            "boundary_violations": list(self.boundary_violations),
            "details": self.details,
        }


@dataclass(frozen=True)
class ControlledTestResult:
    """Result of executing allowlisted tests under controlled policy."""

    execution_id: UUID
    target: str
    exit_code: int
    status: str
    stdout: str
    stderr: str
    duration_seconds: float
    started_at: datetime
    completed_at: datetime
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and self.status == "passed" and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": str(self.execution_id),
            "target": self.target,
            "exit_code": self.exit_code,
            "status": self.status,
            "stdout_length": len(self.stdout),
            "stderr_length": len(self.stderr),
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "timed_out": self.timed_out,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class Phase5ExecutionOutcome:
    """Authoritative outcome of Phase 5 execution and verification."""

    patch_id: UUID | None
    task_id: UUID | None
    execution_id: UUID
    lifecycle_state: PatchExecutionState
    application_result: PatchApplicationResult
    integrity_result: PostApplyIntegrityResult | None
    test_result: ControlledTestResult | None
    verification_result: VerificationResult | None
    is_verified: bool
    summary: str
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": str(self.patch_id) if self.patch_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id),
            "lifecycle_state": self.lifecycle_state.value,
            "application_result": self.application_result.to_dict(),
            "integrity_result": (
                self.integrity_result.to_dict() if self.integrity_result else None
            ),
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "verification_status": (
                self.verification_result.status.value if self.verification_result else None
            ),
            "is_verified": self.is_verified,
            "summary": self.summary,
            "completed_at": self.completed_at.isoformat(),
        }

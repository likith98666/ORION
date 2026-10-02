"""Patch proposal contracts for bounded cognitive code modification and patch synthesis.

IMPORTANT ARCHITECTURAL INVARIANT:
These contracts represent UNTRUSTED MODEL PROPOSALS.
They possess NO authoritative execution permissions.
At most they constitute EvidenceLevel.CLAIMED until independently verified by ORION.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class PatchOperationType(str, Enum):
    """Explicit, conservative patch operations."""

    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"


@dataclass(frozen=True)
class SyntaxValidationResult:
    """Outcome of deterministic syntax validation for an affected patch target."""

    path: str
    language: str
    valid: bool
    supported: bool
    error_message: str | None = None
    line_number: int | None = None
    column_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize syntax validation result to dictionary."""
        return {
            "path": self.path,
            "language": self.language,
            "valid": self.valid,
            "supported": self.supported,
            "error_message": self.error_message,
            "line_number": self.line_number,
            "column_number": self.column_number,
        }


@dataclass(frozen=True)
class PatchOperation:
    """Explicit, bounded file modification instruction within a patch proposal."""

    operation_type: PatchOperationType
    path: str
    new_content: str | None = None
    expected_hash: str | None = None
    expected_content: str | None = None
    diff: str = ""
    lines_added: int = 0
    lines_removed: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize patch operation to dictionary."""
        return {
            "operation_type": self.operation_type.value,
            "path": self.path,
            "new_content": self.new_content,
            "expected_hash": self.expected_hash,
            "expected_content": self.expected_content,
            "diff": self.diff,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatchOperation:
        """Construct PatchOperation from dictionary representation."""
        op_val = data["operation_type"]
        op_type = (
            op_val
            if isinstance(op_val, PatchOperationType)
            else PatchOperationType(str(op_val).lower())
        )
        return cls(
            operation_type=op_type,
            path=str(data["path"]),
            new_content=data.get("new_content"),
            expected_hash=data.get("expected_hash"),
            expected_content=data.get("expected_content"),
            diff=str(data.get("diff", "")),
            lines_added=int(data.get("lines_added", 0)),
            lines_removed=int(data.get("lines_removed", 0)),
        )


@dataclass(frozen=True)
class PatchProposal:
    """Structured code patch proposed by a cognitive model for deterministic review."""

    affected_files: tuple[str, ...]
    operations: tuple[PatchOperation, ...]
    rationale: str
    validation_steps: tuple[str, ...] = ()
    confidence: float = 0.0
    task_id: UUID | None = None
    execution_id: UUID | None = None
    syntax_results: tuple[SyntaxValidationResult, ...] = ()
    total_lines_added: int = 0
    total_lines_removed: int = 0
    unified_diff: str = ""
    provider_name: str | None = None
    model_name: str | None = None
    raw_response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return True if patch operations exist and all syntax validations pass."""
        return len(self.operations) > 0 and all(r.valid for r in self.syntax_results)

    def summary(self) -> str:
        """Return a human-readable one-line summary of the patch proposal."""
        return (
            f"PatchProposal(files={len(self.affected_files)}, "
            f"ops={len(self.operations)}, +{self.total_lines_added}/-{self.total_lines_removed}, "
            f"confidence={self.confidence})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize proposal to dictionary for telemetry and evidence ledger recording."""
        return {
            "affected_files": list(self.affected_files),
            "operations": [op.to_dict() for op in self.operations],
            "rationale": self.rationale,
            "validation_steps": list(self.validation_steps),
            "confidence": self.confidence,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "syntax_results": [res.to_dict() for res in self.syntax_results],
            "total_lines_added": self.total_lines_added,
            "total_lines_removed": self.total_lines_removed,
            "unified_diff": self.unified_diff,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "metadata": dict(self.metadata),
        }

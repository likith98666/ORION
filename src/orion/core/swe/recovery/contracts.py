"""Strongly typed contracts, data transfer objects, and audit records for Phase 6."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from orion.core.security.risk import ToolRiskLevel
from orion.core.swe.evidence import EvidenceCategory
from orion.core.swe.recovery.budget import BudgetSnapshot
from orion.core.swe.recovery.classification import FailureCategory
from orion.core.swe.recovery.strategies import RecoveryStrategy
from orion.core.verification.models import VerificationResult


class RecoveryAttemptState(str, Enum):
    """Lifecycle states of an individual recovery attempt."""

    PLANNED = "PLANNED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    RETESTING = "RETESTING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    TERMINATED = "TERMINATED"


@dataclass(frozen=True)
class RecoveryStateTransition:
    """Immutable transition audit record within a recovery attempt."""

    from_state: RecoveryAttemptState
    to_state: RecoveryAttemptState
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RecoveryPlan:
    """Deterministic recovery specification constructed prior to execution."""

    plan_id: UUID
    failure_id: UUID
    failure_category: FailureCategory
    selected_strategy: RecoveryStrategy
    rationale: str
    required_evidence: tuple[EvidenceCategory, ...] = (EvidenceCategory.TEST_RESULT,)
    risk: ToolRiskLevel = ToolRiskLevel.LOW
    approval_required: bool = False
    attempt_number: int = 1
    parent_attempt_id: UUID | None = None
    expected_action: str = ""
    budget_remaining: BudgetSnapshot | None = None
    target_model: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "failure_id": str(self.failure_id),
            "failure_category": self.failure_category.value,
            "selected_strategy": self.selected_strategy.value,
            "rationale": self.rationale,
            "required_evidence": [e.value for e in self.required_evidence],
            "risk": self.risk.value,
            "approval_required": self.approval_required,
            "attempt_number": self.attempt_number,
            "parent_attempt_id": str(self.parent_attempt_id) if self.parent_attempt_id else None,
            "expected_action": self.expected_action,
            "budget_remaining": self.budget_remaining.to_dict() if self.budget_remaining else None,
            "target_model": self.target_model,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class RollbackRecord:
    """Audit record capturing filesystem snapshot rollback execution and outcomes."""

    rollback_id: UUID
    attempt_id: UUID
    restored_files: tuple[str, ...]
    pre_state_hashes: dict[str, str | None]
    post_rollback_hashes: dict[str, str | None]
    success: bool
    details: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_id": str(self.rollback_id),
            "attempt_id": str(self.attempt_id),
            "restored_files": list(self.restored_files),
            "pre_state_hashes": self.pre_state_hashes,
            "post_rollback_hashes": self.post_rollback_hashes,
            "success": self.success,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class RecoveryAttempt:
    """Execution record of an individual recovery cycle."""

    attempt_id: UUID
    execution_id: UUID
    failure_id: UUID
    strategy: RecoveryStrategy
    start_time: datetime
    parent_attempt_id: UUID | None = None
    plan: RecoveryPlan | None = None
    end_time: datetime | None = None
    state: RecoveryAttemptState = RecoveryAttemptState.PLANNED
    budget_before: BudgetSnapshot | None = None
    budget_after: BudgetSnapshot | None = None
    patch_id: UUID | None = None
    test_execution_id: UUID | None = None
    verification_result: VerificationResult | None = None
    rollback_record: RollbackRecord | None = None
    error: str | None = None
    outcome: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": str(self.attempt_id),
            "execution_id": str(self.execution_id),
            "failure_id": str(self.failure_id),
            "parent_attempt_id": str(self.parent_attempt_id) if self.parent_attempt_id else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "strategy": self.strategy.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "state": self.state.value,
            "budget_before": self.budget_before.to_dict() if self.budget_before else None,
            "budget_after": self.budget_after.to_dict() if self.budget_after else None,
            "patch_id": str(self.patch_id) if self.patch_id else None,
            "test_execution_id": str(self.test_execution_id) if self.test_execution_id else None,
            "verification_status": (
                self.verification_result.status.value if self.verification_result else None
            ),
            "rollback": self.rollback_record.to_dict() if self.rollback_record else None,
            "error": self.error,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class RecoveryAuditReport:
    """Comprehensive recovery summary exposing structured status for API/UI."""

    mission_id: UUID
    task_id: UUID
    execution_id: UUID
    initial_failure_category: FailureCategory
    final_state: RecoveryAttemptState
    total_attempts_executed: int
    attempts: tuple[RecoveryAttempt, ...]
    final_budget: BudgetSnapshot
    verified_success: bool
    summary: str
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": str(self.mission_id),
            "task_id": str(self.task_id),
            "execution_id": str(self.execution_id),
            "initial_failure_category": self.initial_failure_category.value,
            "final_state": self.final_state.value,
            "total_attempts_executed": self.total_attempts_executed,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_budget": self.final_budget.to_dict(),
            "verified_success": self.verified_success,
            "summary": self.summary,
            "completed_at": self.completed_at.isoformat(),
        }

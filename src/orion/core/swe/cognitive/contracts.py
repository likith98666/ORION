"""Cognitive proposal contracts for model-assisted failure analysis and fix formulation.

IMPORTANT ARCHITECTURAL INVARIANT:
These contracts represent UNTRUSTED MODEL PROPOSALS.
They possess NO authoritative execution permissions.
At most they constitute EvidenceLevel.CLAIMED until independently verified by ORION.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from orion.core.swe.cognitive.patch_contracts import (
    PatchOperation,
    PatchOperationType,
    PatchProposal,
    SyntaxValidationResult,
)
from orion.core.swe.formulation import ProposedFixPlan


@dataclass(frozen=True)
class FailureAnalysisProposal:
    """Structured hypothesis and diagnostic analysis proposed by a cognitive model."""

    failure_classification: str
    root_cause_hypothesis: str
    supporting_observations: tuple[str, ...] = ()
    relevant_files: tuple[str, ...] = ()
    confidence: float = 0.0
    proposed_next_action: str = ""
    reasoning_summary: str = ""
    task_id: UUID | None = None
    execution_id: UUID | None = None
    provider_name: str | None = None
    model_name: str | None = None
    raw_response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize proposal to dictionary for telemetry and evidence ledger recording."""
        return {
            "failure_classification": self.failure_classification,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "supporting_observations": list(self.supporting_observations),
            "relevant_files": list(self.relevant_files),
            "confidence": self.confidence,
            "proposed_next_action": self.proposed_next_action,
            "reasoning_summary": self.reasoning_summary,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FixProposal:
    """Structured fix formulation proposed by a cognitive model."""

    change_intent: str
    affected_files: tuple[str, ...]
    proposed_modifications: tuple[str, ...] = ()
    rationale: str = ""
    expected_effect: str = ""
    validation_plan: tuple[str, ...] = ()
    confidence: float = 0.0
    diagnosis_reference: str = ""
    task_id: UUID | None = None
    execution_id: UUID | None = None
    provider_name: str | None = None
    model_name: str | None = None
    raw_response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_proposed_fix_plan(self) -> ProposedFixPlan:
        """Convert validated FixProposal into the coordinator's internal ProposedFixPlan."""
        strategy = (
            "; ".join(self.validation_plan) if self.validation_plan else "run_tests validation"
        )
        return ProposedFixPlan(
            target_files=self.affected_files,
            intended_modification=self.change_intent,
            expected_behavior=self.expected_effect or "Fix verified through test pass",
            validation_strategy=strategy,
            constraints=self.proposed_modifications,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize proposal to dictionary for telemetry and evidence ledger recording."""
        return {
            "change_intent": self.change_intent,
            "affected_files": list(self.affected_files),
            "proposed_modifications": list(self.proposed_modifications),
            "rationale": self.rationale,
            "expected_effect": self.expected_effect,
            "validation_plan": list(self.validation_plan),
            "confidence": self.confidence,
            "diagnosis_reference": self.diagnosis_reference,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "FailureAnalysisProposal",
    "FixProposal",
    "PatchOperation",
    "PatchOperationType",
    "PatchProposal",
    "SyntaxValidationResult",
]

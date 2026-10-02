"""Evidence-driven conflict resolution between competing agent proposals in V4."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from orion.core.agents.workforce.models import AgentProposal, ConflictResolution


class AgentConflictResolver:
    """Evaluates and arbitrates between divergent or competing agent proposals."""

    def resolve(
        self,
        proposals: Sequence[AgentProposal],
        confidence_threshold: float = 0.15,
    ) -> ConflictResolution:
        """Resolve competing proposals using evidence count, confidence, and blast radius."""
        if not proposals:
            raise ValueError("Cannot resolve conflicts without candidate proposals.")

        if len(proposals) == 1:
            p = proposals[0]
            return ConflictResolution(
                resolution_id=uuid4(),
                competing_proposals=(p.proposal_id,),
                selected_proposal_id=p.proposal_id,
                rationale="Uncontested single proposal selected.",
                requires_human_approval=False,
                evaluation_matrix={str(p.proposal_id): {"score": p.confidence_score}},
            )

        # Build comparative score matrix
        matrix: dict[str, dict[str, float]] = {}
        scores: dict[UUID, float] = {}

        for p in proposals:
            evidence_weight = len(p.evidence_items) * 0.1
            file_scope_penalty = len(p.target_files) * 0.05
            composite_score = p.confidence_score + evidence_weight - file_scope_penalty

            matrix[str(p.proposal_id)] = {
                "confidence": p.confidence_score,
                "evidence_count": float(len(p.evidence_items)),
                "file_count": float(len(p.target_files)),
                "composite_score": round(composite_score, 3),
            }
            scores[p.proposal_id] = composite_score

        # Sort proposals descending by score
        sorted_proposals = sorted(proposals, key=lambda p: scores[p.proposal_id], reverse=True)
        top = sorted_proposals[0]
        runner_up = sorted_proposals[1]

        score_diff = scores[top.proposal_id] - scores[runner_up.proposal_id]

        # If top two proposals are within close margin, require human intervention
        requires_human = score_diff < confidence_threshold
        rationale = (
            f"Close competition between proposal {top.proposal_id} "
            f"({scores[top.proposal_id]:.2f}) and {runner_up.proposal_id} "
            f"({scores[runner_up.proposal_id]:.2f}). Routed for human review."
            if requires_human
            else f"Proposal {top.proposal_id} decisively outscored competitors "
            f"(margin: {score_diff:.2f})."
        )

        selected_id = None if requires_human else top.proposal_id

        return ConflictResolution(
            resolution_id=uuid4(),
            competing_proposals=tuple(p.proposal_id for p in proposals),
            selected_proposal_id=selected_id,
            rationale=rationale,
            requires_human_approval=requires_human,
            evaluation_matrix=matrix,
        )

"""Deterministic recovery planner constructing auditable RecoveryPlans."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from orion.core.swe.cognitive.patch_contracts import PatchProposal
from orion.core.swe.recovery.budget import RecoveryBudget
from orion.core.swe.recovery.classification import FailureClassification
from orion.core.swe.recovery.contracts import RecoveryAttempt, RecoveryPlan
from orion.core.swe.recovery.errors import RecoveryPolicyViolationError, UnregisteredStrategyError
from orion.core.swe.recovery.policy import RecoveryPolicy
from orion.core.swe.recovery.strategies import (
    RecoveryStrategy,
    RecoveryStrategyRegistry,
)


class RecoveryPlanner:
    """Plans deterministic, bounded recovery actions for SWE failures."""

    def __init__(
        self,
        policy: RecoveryPolicy | None = None,
        strategy_registry: RecoveryStrategyRegistry | None = None,
    ) -> None:
        self._policy = policy or RecoveryPolicy()
        self._registry = strategy_registry or RecoveryStrategyRegistry()

    def plan_recovery(
        self,
        classification: FailureClassification,
        budget: RecoveryBudget,
        history: Sequence[RecoveryAttempt] = (),
        current_patch: PatchProposal | None = None,
        parent_attempt_id: UUID | None = None,
        candidate_strategy: RecoveryStrategy | str | None = None,
        candidate_model: str | None = None,
        available_models: Sequence[str] = (),
    ) -> RecoveryPlan:
        """Create a validated RecoveryPlan under strict budget and policy constraints."""
        plan_id = uuid4()
        attempt_number = len(history) + 1
        can_change_model = bool(available_models) and budget.can_attempt(
            RecoveryStrategy.CHANGE_MODEL
        )

        # 1. Determine strategy: either validate candidate or select from policy
        if candidate_strategy is not None:
            # Model or caller recommended a strategy; validate it deterministically
            try:
                strat_enum = (
                    RecoveryStrategy(candidate_strategy)
                    if isinstance(candidate_strategy, str)
                    else candidate_strategy
                )
            except ValueError as exc:
                raise UnregisteredStrategyError(
                    f"Candidate strategy '{candidate_strategy}' is not registered."
                ) from exc

            # Policy check: cannot bypass policy with untrusted candidate
            if not self._policy.validate_strategy_allowed(strat_enum, classification.category):
                raise RecoveryPolicyViolationError(
                    f"Candidate strategy '{strat_enum.value}' is forbidden by recovery policy "
                    f"for failure category '{classification.category.value}'."
                )
            selected_strategy = strat_enum
            rationale = (
                f"Candidate strategy '{strat_enum.value}' verified and permitted."
            )
        else:
            # Authoritative policy selection
            selected_strategy, rationale = self._policy.select_strategy(
                classification=classification,
                history=history,
                can_change_model=can_change_model,
            )

        # 2. Verify strategy exists in registry
        strat_defn = self._registry.get(selected_strategy)

        # 3. Budget enforcement check
        if selected_strategy != RecoveryStrategy.TERMINATE and not budget.can_attempt(
            selected_strategy
        ):
            selected_strategy = RecoveryStrategy.TERMINATE
            strat_defn = self._registry.get(selected_strategy)
            rationale = (
                f"Recovery budget exhausted for strategy '{strat_defn.strategy.value}'. "
                f"Enforcing TERMINATE."
            )

        # 4. Formulate expected action
        if selected_strategy == RecoveryStrategy.RETRY_TEST:
            action = (
                "Re-execute isolated pytest subprocess in workspace without filesystem changes."
            )
        elif selected_strategy == RecoveryStrategy.REFRESH_WORKSPACE_STATE:
            action = (
                "Release transient workspace locks and recompute "
                "SHA-256 hashes of repository files."
            )
        elif selected_strategy == RecoveryStrategy.REGENERATE_PATCH:
            action = (
                "Synthesize new PatchProposal from updated failure "
                "context and request authorization."
            )
        elif selected_strategy == RecoveryStrategy.MODIFY_PATCH:
            action = (
                "Refine existing PatchProposal against failed "
                "verification criteria and request authorization."
            )
        elif selected_strategy == RecoveryStrategy.ROLLBACK:
            action = (
                "Revert workspace mutations cleanly using pre-apply "
                "FileSnapshot recovery point."
            )
        elif selected_strategy == RecoveryStrategy.CHANGE_MODEL:
            target_model = candidate_model or (available_models[0] if available_models else None)
            action = (
                f"Switch cognitive provider to alternate model '{target_model}' "
                "and regenerate patch."
            )
        else:
            action = "Terminate recovery loop and record final mission failure audit."
            target_model = None

        if selected_strategy != RecoveryStrategy.CHANGE_MODEL:
            target_model = None

        budget_snapshot = budget.create_snapshot()

        return RecoveryPlan(
            plan_id=plan_id,
            failure_id=classification.failure_id,
            failure_category=classification.category,
            selected_strategy=selected_strategy,
            rationale=rationale,
            required_evidence=strat_defn.required_evidence,
            risk=strat_defn.risk_level,
            approval_required=strat_defn.approval_required,
            attempt_number=attempt_number,
            parent_attempt_id=parent_attempt_id,
            expected_action=action,
            budget_remaining=budget_snapshot,
            target_model=target_model,
        )

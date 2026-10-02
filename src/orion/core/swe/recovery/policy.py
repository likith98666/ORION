"""Deterministic recovery policy rules mapping failure classifications to strategies."""

from __future__ import annotations

from collections.abc import Sequence

from orion.core.swe.recovery.classification import FailureCategory, FailureClassification
from orion.core.swe.recovery.contracts import RecoveryAttempt
from orion.core.swe.recovery.strategies import RecoveryStrategy


class RecoveryPolicy:
    """Authoritative deterministic policy engine for selecting recovery strategies."""

    def select_strategy(
        self,
        classification: FailureClassification,
        history: Sequence[RecoveryAttempt] = (),
        can_change_model: bool = False,
    ) -> tuple[RecoveryStrategy, str]:
        """Select permitted recovery strategy based on deterministic rules and history.

        Returns (selected_strategy, rationale).
        """
        category = classification.category

        # Count prior attempts with this same failure category
        same_cat_attempts = [
            a for a in history if a.plan is not None and a.plan.failure_category == category
        ]
        same_cat_count = len(same_cat_attempts)

        # 1. Non-recoverable failures terminate immediately
        if category in (
            FailureCategory.APPROVAL_FAILURE,
            FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
            FailureCategory.DEPENDENCY_FAILURE,
            FailureCategory.UNKNOWN_FAILURE,
        ):
            return (
                RecoveryStrategy.TERMINATE,
                f"Failure category '{category.value}' is non-recoverable under policy.",
            )

        # 2. Environment failure: try refreshing once, else terminate
        if category == FailureCategory.ENVIRONMENT_FAILURE:
            if same_cat_count == 0:
                return (
                    RecoveryStrategy.REFRESH_WORKSPACE_STATE,
                    "Refresh workspace locks and verify environment state.",
                )
            return (
                RecoveryStrategy.TERMINATE,
                "Repeated environment failure cannot be resolved autonomously.",
            )

        # 3. Stale workspace state: refresh state to resync hashes and release locks
        if category == FailureCategory.STALE_STATE:
            if same_cat_count == 0:
                return (
                    RecoveryStrategy.REFRESH_WORKSPACE_STATE,
                    "Resynchronize workspace hashes and release transient workspace locks.",
                )
            # If still stale after refresh, rollback and regenerate
            return (
                RecoveryStrategy.ROLLBACK,
                "Repeated stale state collision: rolling back workspace to pre-apply snapshot.",
            )

        # 4. Patch application failure: rollback mutated state first, then regenerate
        if category == FailureCategory.PATCH_APPLICATION_FAILURE:
            # Check if last attempt was rollback
            if history and history[-1].strategy == RecoveryStrategy.ROLLBACK:
                return (
                    RecoveryStrategy.REGENERATE_PATCH,
                    "Workspace rolled back cleanly; regenerating patch proposal with clean syntax.",
                )
            return (
                RecoveryStrategy.ROLLBACK,
                "Patch application failed mid-mutation; rolling back to clean pre-apply snapshot.",
            )

        # 5. Timeout: retry once with fresh test run, then modify patch
        if category == FailureCategory.TIMEOUT:
            if same_cat_count == 0:
                return (
                    RecoveryStrategy.RETRY_TEST,
                    "Test execution timed out; retrying execution once for transient load.",
                )
            return (
                RecoveryStrategy.MODIFY_PATCH,
                "Test timed out repeatedly; modifying patch to address potential deadlock.",
            )

        # 6. Verification failure: modify or regenerate patch, or change model if repeated
        if category == FailureCategory.VERIFICATION_FAILURE:
            if same_cat_count >= 2 and can_change_model:
                return (
                    RecoveryStrategy.CHANGE_MODEL,
                    "Repeated verification failure under model; switching to alternate provider.",
                )
            if same_cat_count == 0:
                return (
                    RecoveryStrategy.MODIFY_PATCH,
                    "VerificationEngine requirements unsatisfied; modifying patch for assertions.",
                )
            return (
                RecoveryStrategy.REGENERATE_PATCH,
                "Verification requirements unsatisfied; regenerating patch from first principles.",
            )

        # 7. Test failure: retry once if 0 prior attempts, else regenerate patch
        if category == FailureCategory.TEST_FAILURE:
            if same_cat_count == 0:
                return (
                    RecoveryStrategy.RETRY_TEST,
                    "Initial test failure; retrying controlled execution to verify repeatability.",
                )
            if same_cat_count == 1:
                return (
                    RecoveryStrategy.REGENERATE_PATCH,
                    "Test failure confirmed; synthesizing updated patch with failure context.",
                )
            if same_cat_count >= 2:
                if can_change_model:
                    return (
                        RecoveryStrategy.CHANGE_MODEL,
                        "Repeated test failure with model; switching to alternate provider.",
                    )
                return (
                    RecoveryStrategy.MODIFY_PATCH,
                    "Applying targeted patch modification for lingering assertion failure.",
                )

        # Default fallback
        return (
            RecoveryStrategy.TERMINATE,
            f"No recovery rule configured for category '{category.value}'.",
        )

    def validate_strategy_allowed(
        self,
        strategy: RecoveryStrategy,
        category: FailureCategory,
    ) -> bool:
        """Verify whether a candidate strategy is allowed for the failure category."""
        forbidden_for_strategy = {
            RecoveryStrategy.RETRY_TEST: {
                FailureCategory.APPROVAL_FAILURE,
                FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
                FailureCategory.DEPENDENCY_FAILURE,
                FailureCategory.PATCH_APPLICATION_FAILURE,
            },
            RecoveryStrategy.REGENERATE_PATCH: {
                FailureCategory.APPROVAL_FAILURE,
                FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
                FailureCategory.DEPENDENCY_FAILURE,
            },
            RecoveryStrategy.MODIFY_PATCH: {
                FailureCategory.APPROVAL_FAILURE,
                FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
                FailureCategory.DEPENDENCY_FAILURE,
            },
        }

        blocked = forbidden_for_strategy.get(strategy, set())
        return category not in blocked

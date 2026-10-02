"""Recovery strategy definitions and authoritative strategy registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from orion.core.security.risk import ToolRiskLevel
from orion.core.swe.evidence import EvidenceCategory
from orion.core.swe.recovery.classification import FailureCategory
from orion.core.swe.recovery.errors import UnregisteredStrategyError


class RecoveryStrategy(str, Enum):
    """Explicit closed set of permitted self-healing recovery strategies."""

    RETRY_TEST = "RETRY_TEST"
    REFRESH_WORKSPACE_STATE = "REFRESH_WORKSPACE_STATE"
    REGENERATE_PATCH = "REGENERATE_PATCH"
    MODIFY_PATCH = "MODIFY_PATCH"
    ROLLBACK = "ROLLBACK"
    CHANGE_MODEL = "CHANGE_MODEL"
    TERMINATE = "TERMINATE"


@dataclass(frozen=True)
class RecoveryStrategyDefinition:
    """Authoritative metadata and policy specification for a recovery strategy."""

    strategy: RecoveryStrategy
    supported_failure_categories: frozenset[FailureCategory]
    prerequisites: tuple[str, ...]
    risk_level: ToolRiskLevel
    max_attempts: int
    required_evidence: tuple[EvidenceCategory, ...]
    approval_required: bool
    description: str


# Canonical strategy registry specifications
DEFAULT_STRATEGY_DEFINITIONS: dict[RecoveryStrategy, RecoveryStrategyDefinition] = {
    RecoveryStrategy.RETRY_TEST: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.RETRY_TEST,
        supported_failure_categories=frozenset(
            {
                FailureCategory.TEST_FAILURE,
                FailureCategory.TIMEOUT,
            }
        ),
        prerequisites=("Tests previously ran but failed or timed out",),
        risk_level=ToolRiskLevel.LOW,
        max_attempts=2,
        required_evidence=(EvidenceCategory.TEST_RESULT,),
        approval_required=False,
        description="Re-run controlled pytest suite without changing files to resolve flakiness.",
    ),
    RecoveryStrategy.REFRESH_WORKSPACE_STATE: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.REFRESH_WORKSPACE_STATE,
        supported_failure_categories=frozenset(
            {
                FailureCategory.STALE_STATE,
                FailureCategory.ENVIRONMENT_FAILURE,
            }
        ),
        prerequisites=("Workspace lock cleared and repository inspectable",),
        risk_level=ToolRiskLevel.LOW,
        max_attempts=2,
        required_evidence=(EvidenceCategory.REPOSITORY_STATE,),
        approval_required=False,
        description="Refresh file hashes and release locks to resolve concurrent collisions.",
    ),
    RecoveryStrategy.REGENERATE_PATCH: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.REGENERATE_PATCH,
        supported_failure_categories=frozenset(
            {
                FailureCategory.TEST_FAILURE,
                FailureCategory.VERIFICATION_FAILURE,
                FailureCategory.PATCH_APPLICATION_FAILURE,
            }
        ),
        prerequisites=("Failure diagnosed and diagnostic context updated",),
        risk_level=ToolRiskLevel.HIGH,
        max_attempts=2,
        required_evidence=(
            EvidenceCategory.DIAGNOSTIC_RESULT,
            EvidenceCategory.PROPOSED_CHANGE,
            EvidenceCategory.FILE_CHANGE,
        ),
        approval_required=True,
        description="Synthesize a completely new patch proposal with updated failure context.",
    ),
    RecoveryStrategy.MODIFY_PATCH: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.MODIFY_PATCH,
        supported_failure_categories=frozenset(
            {
                FailureCategory.VERIFICATION_FAILURE,
                FailureCategory.TEST_FAILURE,
            }
        ),
        prerequisites=("Previous patch available with test feedback",),
        risk_level=ToolRiskLevel.HIGH,
        max_attempts=2,
        required_evidence=(
            EvidenceCategory.PROPOSED_CHANGE,
            EvidenceCategory.FILE_CHANGE,
        ),
        approval_required=True,
        description=(
            "Refine the existing patch proposal to satisfy missing verification requirements."
        ),
    ),
    RecoveryStrategy.ROLLBACK: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.ROLLBACK,
        supported_failure_categories=frozenset(
            {
                FailureCategory.PATCH_APPLICATION_FAILURE,
                FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
                FailureCategory.TEST_FAILURE,
            }
        ),
        prerequisites=("Valid pre-apply recovery snapshot exists",),
        risk_level=ToolRiskLevel.MEDIUM,
        max_attempts=2,
        required_evidence=(EvidenceCategory.RECOVERY_EVENT,),
        approval_required=False,
        description=(
            "Restore workspace files to pre-apply snapshot cleanly using PatchRecoveryManager."
        ),
    ),
    RecoveryStrategy.CHANGE_MODEL: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.CHANGE_MODEL,
        supported_failure_categories=frozenset(
            {
                FailureCategory.VERIFICATION_FAILURE,
                FailureCategory.PATCH_APPLICATION_FAILURE,
                FailureCategory.TEST_FAILURE,
            }
        ),
        prerequisites=("Alternate registered model provider available in registry",),
        risk_level=ToolRiskLevel.MEDIUM,
        max_attempts=1,
        required_evidence=(EvidenceCategory.PROPOSED_CHANGE,),
        approval_required=False,
        description=(
            "Switch to an alternate registered model provider to avoid model-specific deadlocks."
        ),
    ),
    RecoveryStrategy.TERMINATE: RecoveryStrategyDefinition(
        strategy=RecoveryStrategy.TERMINATE,
        supported_failure_categories=frozenset(FailureCategory),
        prerequisites=(),
        risk_level=ToolRiskLevel.LOW,
        max_attempts=1,
        required_evidence=(EvidenceCategory.RECOVERY_EVENT,),
        approval_required=False,
        description="Halt self-healing execution and report structured failure audit.",
    ),
}


class RecoveryStrategyRegistry:
    """Registry maintaining authorized recovery strategy specifications."""

    def __init__(
        self,
        custom_definitions: dict[RecoveryStrategy, RecoveryStrategyDefinition] | None = None,
    ) -> None:
        self._strategies: dict[RecoveryStrategy, RecoveryStrategyDefinition] = dict(
            custom_definitions or DEFAULT_STRATEGY_DEFINITIONS
        )

    def get(self, strategy: RecoveryStrategy | str) -> RecoveryStrategyDefinition:
        """Retrieve strategy definition or raise UnregisteredStrategyError."""
        try:
            strat_enum = RecoveryStrategy(strategy) if isinstance(strategy, str) else strategy
        except ValueError as exc:
            raise UnregisteredStrategyError(
                f"Unknown or dynamic recovery strategy '{strategy}'. "
                f"Permitted strategies: {[s.value for s in RecoveryStrategy]}"
            ) from exc

        if strat_enum not in self._strategies:
            raise UnregisteredStrategyError(
                f"Recovery strategy '{strat_enum.value}' is not registered."
            )
        return self._strategies[strat_enum]

    get_definition = get

    def is_registered(self, strategy: RecoveryStrategy | str) -> bool:
        """Check if a strategy is registered."""
        try:
            strat_enum = RecoveryStrategy(strategy) if isinstance(strategy, str) else strategy
            return strat_enum in self._strategies
        except ValueError:
            return False

    def list_strategies_for_category(
        self,
        category: FailureCategory,
    ) -> list[RecoveryStrategyDefinition]:
        """Return all strategies supporting the given failure category."""
        return [
            defn
            for defn in self._strategies.values()
            if category in defn.supported_failure_categories
        ]

"""Phase 6: Bounded Self-Healing Recovery Subsystem."""

from __future__ import annotations

from orion.core.swe.recovery.attempt import (
    VALID_RECOVERY_TRANSITIONS,
    RecoveryAttemptLifecycle,
)
from orion.core.swe.recovery.budget import (
    BudgetSnapshot,
    RecoveryBudget,
)
from orion.core.swe.recovery.classification import (
    FailureCategory,
    FailureClassification,
    FailureClassifier,
)
from orion.core.swe.recovery.contracts import (
    RecoveryAttempt,
    RecoveryAttemptState,
    RecoveryAuditReport,
    RecoveryPlan,
    RecoveryStateTransition,
    RollbackRecord,
)
from orion.core.swe.recovery.coordinator import SWERecoveryCoordinator
from orion.core.swe.recovery.errors import (
    BudgetExhaustedError,
    InvalidRecoveryTransitionError,
    Phase6RecoveryError,
    RecoveryDepthExceededError,
    RecoveryPolicyViolationError,
    RollbackExecutionError,
    StrategyExecutionError,
    UnauthorizedRecoveryError,
    UnregisteredStrategyError,
)
from orion.core.swe.recovery.planner import RecoveryPlanner
from orion.core.swe.recovery.policy import RecoveryPolicy
from orion.core.swe.recovery.strategies import (
    DEFAULT_STRATEGY_DEFINITIONS,
    RecoveryStrategy,
    RecoveryStrategyDefinition,
    RecoveryStrategyRegistry,
)

__all__ = [
    "DEFAULT_STRATEGY_DEFINITIONS",
    "VALID_RECOVERY_TRANSITIONS",
    "BudgetExhaustedError",
    "BudgetSnapshot",
    "FailureCategory",
    "FailureClassification",
    "FailureClassifier",
    "InvalidRecoveryTransitionError",
    "Phase6RecoveryError",
    "RecoveryAttempt",
    "RecoveryAttemptLifecycle",
    "RecoveryAttemptState",
    "RecoveryAuditReport",
    "RecoveryBudget",
    "RecoveryDepthExceededError",
    "RecoveryPlan",
    "RecoveryPlanner",
    "RecoveryPolicy",
    "RecoveryPolicyViolationError",
    "RecoveryStateTransition",
    "RecoveryStrategy",
    "RecoveryStrategyDefinition",
    "RecoveryStrategyRegistry",
    "RollbackExecutionError",
    "RollbackRecord",
    "SWERecoveryCoordinator",
    "StrategyExecutionError",
    "UnauthorizedRecoveryError",
    "UnregisteredStrategyError",
]

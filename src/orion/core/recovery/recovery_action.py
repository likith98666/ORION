from dataclasses import dataclass
from enum import Enum

from orion.core.recovery.recovery_strategy import RecoveryStrategy


class RecoveryActionType(str, Enum):
    """Concrete action types produced from recovery strategies."""

    RETRY_TASK = "retry_task"
    CHANGE_AGENT = "change_agent"
    CHANGE_TOOL = "change_tool"
    CHANGE_MODEL = "change_model"
    MODIFY_TASK = "modify_task"
    CHANGE_TASK_ORDER = "change_task_order"
    SKIP_TASK = "skip_task"
    ESCALATE_TO_HUMAN = "escalate_to_human"


@dataclass(frozen=True)
class RecoveryAction:
    """Represents a concrete action derived from a recovery strategy."""

    action_type: RecoveryActionType
    requires_human: bool = False

    @classmethod
    def from_strategy(
        cls,
        strategy: RecoveryStrategy,
    ) -> "RecoveryAction":
        """Convert a recovery strategy into a concrete recovery action."""

        if not isinstance(strategy, RecoveryStrategy):
            raise TypeError(
                "strategy must be a RecoveryStrategy instance."
            )

        action_type = {
            RecoveryStrategy.RETRY_CURRENT_TASK: (
                RecoveryActionType.RETRY_TASK
            ),
            RecoveryStrategy.CHANGE_AGENT: (
                RecoveryActionType.CHANGE_AGENT
            ),
            RecoveryStrategy.CHANGE_TOOL: (
                RecoveryActionType.CHANGE_TOOL
            ),
            RecoveryStrategy.CHANGE_MODEL: (
                RecoveryActionType.CHANGE_MODEL
            ),
            RecoveryStrategy.MODIFY_TASK: (
                RecoveryActionType.MODIFY_TASK
            ),
            RecoveryStrategy.CHANGE_TASK_ORDER: (
                RecoveryActionType.CHANGE_TASK_ORDER
            ),
            RecoveryStrategy.SKIP_NONESSENTIAL_TASK: (
                RecoveryActionType.SKIP_TASK
            ),
            RecoveryStrategy.ESCALATE_TO_HUMAN: (
                RecoveryActionType.ESCALATE_TO_HUMAN
            ),
        }[strategy]

        return cls(
            action_type=action_type,
            requires_human=(
                strategy == RecoveryStrategy.ESCALATE_TO_HUMAN
            ),
        )

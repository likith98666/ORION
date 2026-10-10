from dataclasses import dataclass
from enum import Enum


class RecoveryStrategy(str, Enum):
    """Actions ORION may choose after an execution failure."""

    RETRY_CURRENT_TASK = "retry_current_task"
    CHANGE_TOOL = "change_tool"
    CHANGE_AGENT = "change_agent"
    CHANGE_MODEL = "change_model"
    MODIFY_TASK = "modify_task"
    CHANGE_TASK_ORDER = "change_task_order"
    SKIP_NONESSENTIAL_TASK = "skip_nonessential_task"
    ESCALATE_TO_HUMAN = "escalate_to_human"


@dataclass(frozen=True)
class RecoveryDecision:
    """Represents a recovery strategy selected by ORION."""

    strategy: RecoveryStrategy
    reason: str
    requires_human: bool = False

    def __post_init__(self) -> None:
        cleaned_reason = self.reason.strip()

        if not cleaned_reason:
            raise ValueError("Recovery decision reason cannot be empty.")

        if len(cleaned_reason) > 5000:
            raise ValueError("Recovery decision reason cannot exceed 5,000 characters.")

        object.__setattr__(self, "reason", cleaned_reason)

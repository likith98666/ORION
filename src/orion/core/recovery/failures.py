from dataclasses import dataclass
from enum import Enum


class FailureType(str, Enum):
    """Classification of failures that can occur during ORION execution."""

    AGENT_FAILURE = "agent_failure"
    MODEL_FAILURE = "model_failure"
    TOOL_FAILURE = "tool_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    INVALID_INPUT = "invalid_input"
    CONSTRAINT_VIOLATION = "constraint_violation"
    SECURITY_BLOCK = "security_block"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    VERIFICATION_FAILURE = "verification_failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Failure:
    """Represents a classified failure from an ORION execution."""

    failure_type: FailureType
    message: str

    def __post_init__(self) -> None:
        cleaned_message = self.message.strip()

        if not cleaned_message:
            raise ValueError("Failure message cannot be empty.")

        if len(cleaned_message) > 5000:
            raise ValueError("Failure message cannot exceed 5,000 characters.")

        object.__setattr__(self, "message", cleaned_message)

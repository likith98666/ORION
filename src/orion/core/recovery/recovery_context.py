from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryContext:
    """Context used by ORION to make recovery decisions."""

    retry_count: int = 0
    max_retries: int = 3
    task_criticality: float = 0.5
    alternative_agents_available: bool = False
    alternative_tools_available: bool = False
    alternative_models_available: bool = False
    remaining_budget: float = 0.0
    remaining_time_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative.")

        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative.")

        if self.retry_count > self.max_retries:
            raise ValueError("retry_count cannot exceed max_retries.")

        if not 0.0 <= self.task_criticality <= 1.0:
            raise ValueError("task_criticality must be between 0.0 and 1.0.")

        if self.remaining_budget < 0.0:
            raise ValueError("remaining_budget cannot be negative.")

        if self.remaining_time_ms < 0.0:
            raise ValueError("remaining_time_ms cannot be negative.")

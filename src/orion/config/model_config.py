from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for ORION model execution."""

    provider_name: str
    temperature: float = 0.0
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("Provider name cannot be empty.")

        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(
                "Temperature must be between 0.0 and 2.0.",
            )

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError(
                "max_tokens must be greater than zero.",
            )
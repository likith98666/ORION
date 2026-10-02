from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for ORION model execution."""

    provider_name: str
    temperature: float = 0.0
    max_tokens: int | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 1048576  # 1MB cap

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

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero.",
            )

        if self.max_response_bytes <= 0:
            raise ValueError(
                "max_response_bytes must be greater than zero.",
            )

    def __repr__(self) -> str:
        masked_key = "[REDACTED]" if self.api_key else None
        return (
            f"ModelConfig(provider_name={self.provider_name!r}, "
            f"model_name={self.model_name!r}, "
            f"base_url={self.base_url!r}, "
            f"temperature={self.temperature}, "
            f"max_tokens={self.max_tokens}, "
            f"timeout_seconds={self.timeout_seconds}, "
            f"max_response_bytes={self.max_response_bytes}, "
            f"api_key={masked_key!r})"
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ModelConfig:
        """Load ModelConfig explicitly from environment variables."""
        e = env if env is not None else os.environ
        provider_name = e.get("ORION_MODEL_PROVIDER", "mock").strip()
        model_name = e.get("ORION_MODEL_NAME", "gpt-4o").strip() or None
        base_url = e.get("ORION_MODEL_BASE_URL", "https://api.openai.com/v1").strip() or None
        api_key = e.get("ORION_MODEL_API_KEY", "").strip() or None

        timeout_str = e.get("ORION_MODEL_TIMEOUT", "30.0").strip()
        try:
            timeout_seconds = float(timeout_str)
        except ValueError:
            timeout_seconds = 30.0

        temp_str = e.get("ORION_MODEL_TEMPERATURE", "0.0").strip()
        try:
            temperature = float(temp_str)
        except ValueError:
            temperature = 0.0

        max_tokens_str = e.get("ORION_MODEL_MAX_TOKENS", "").strip()
        max_tokens = int(max_tokens_str) if max_tokens_str.isdigit() else None

        return cls(
            provider_name=provider_name,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_tokens=max_tokens,
        )

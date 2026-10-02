from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelRequest:
    """Represents a request sent to an AI model."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    metadata: dict[str, Any] | None = None
    structured_output: bool = False
    response_format: dict[str, Any] | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    """Represents a response returned by an AI model."""

    text: str
    model_name: str
    provider_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    request_id: str | None = None
    raw_usage: dict[str, int] | None = None

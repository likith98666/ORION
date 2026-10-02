from __future__ import annotations

from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import (
    ModelError,
    ModelProviderError,
    ModelRequestError,
    ModelResponseSizeExceededError,
    sanitize_error_message,
)
from orion.models.providers.base import BaseModelProvider


class ModelGateway:
    """Secure boundary and single entry point for model inference in ORION.

    Enforces:
    - Strict request validation (prompt non-empty, temperature range, positive tokens)
    - Request size bounding (preventing memory exhaustion via huge prompts)
    - Response size bounding (capping unbounded model outputs)
    - Secret protection (redacting sensitive keys and tokens from exceptions)
    - Pure data generation (cannot execute tools, write files, or bypass verification)
    """

    DEFAULT_MAX_PROMPT_CHARS = 100_000
    DEFAULT_MAX_RESPONSE_CHARS = 200_000

    def __init__(
        self,
        provider: BaseModelProvider,
        max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
        max_response_chars: int = DEFAULT_MAX_RESPONSE_CHARS,
    ) -> None:
        if not isinstance(provider, BaseModelProvider):
            raise TypeError("provider must implement BaseModelProvider.")
        self._provider = provider
        self._max_prompt_chars = max(100, int(max_prompt_chars))
        self._max_response_chars = max(100, int(max_response_chars))

    @property
    def provider_name(self) -> str:
        """Return the name of the active model provider."""
        return self._provider.name

    @property
    def model_name(self) -> str:
        """Return the active model name."""
        return self._provider.model_name

    @property
    def max_prompt_chars(self) -> int:
        return self._max_prompt_chars

    @property
    def max_response_chars(self) -> int:
        return self._max_response_chars

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Validate request bounds, delegate to provider, and enforce response security bounds."""
        self._validate_request(request)

        try:
            response = self._provider.generate(request)
        except ModelError:
            raise
        except Exception as exc:
            clean_msg = sanitize_error_message(
                f"Model provider '{self.provider_name}' failed: {exc}"
            )
            raise ModelProviderError(clean_msg) from exc

        # Enforce response length limits at the gateway security boundary
        if len(response.text) > self._max_response_chars:
            raise ModelResponseSizeExceededError(
                f"Model response text length ({len(response.text)} chars) exceeded "
                f"gateway maximum limit of {self._max_response_chars} chars."
            )

        return response

    def health_check(self) -> bool:
        """Check whether the active model provider is available."""
        try:
            return self._provider.health_check()
        except Exception:
            return False

    def _validate_request(self, request: ModelRequest) -> None:
        """Validate model request parameters and security bounds before execution."""
        if not isinstance(request, ModelRequest):
            raise TypeError("request must be an instance of ModelRequest.")

        if not request.prompt.strip():
            raise ModelRequestError("Prompt cannot be empty")

        if len(request.prompt) > self._max_prompt_chars:
            raise ModelRequestError(
                f"Prompt length ({len(request.prompt)} chars) exceeds maximum allowed limit "
                f"of {self._max_prompt_chars} chars."
            )

        if request.system_prompt and len(request.system_prompt) > self._max_prompt_chars:
            raise ModelRequestError(
                f"System prompt length ({len(request.system_prompt)} chars) exceeds maximum "
                f"allowed limit of {self._max_prompt_chars} chars."
            )

        if not 0.0 <= request.temperature <= 2.0:
            raise ModelRequestError(
                "Temperature must be between 0.0 and 2.0",
            )

        if request.max_tokens is not None and request.max_tokens <= 0:
            raise ModelRequestError(
                "max_tokens must be greater than zero",
            )

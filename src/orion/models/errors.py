import re

BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)


def sanitize_error_message(message: str, secrets: tuple[str | None, ...] = ()) -> str:
    """Sanitize error messages to ensure API keys and bearer tokens are never leaked."""
    sanitized = BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", message)
    for secret in secrets:
        if secret and secret.strip():
            sanitized = sanitized.replace(secret.strip(), "[REDACTED]")
    return sanitized


class ModelError(Exception):
    """Base exception for model-related failures."""

    def __init__(self, message: str = "", *args: object) -> None:
        clean_msg = sanitize_error_message(str(message))
        super().__init__(clean_msg, *args)


class ModelProviderError(ModelError):
    """Raised when a model provider fails."""


class ModelProviderUnavailableError(ModelProviderError):
    """Raised when a model provider is unavailable (e.g. HTTP 5xx or server down)."""


class ModelAuthenticationError(ModelProviderError):
    """Raised when authentication fails (e.g. invalid or missing API key, HTTP 401/403)."""


class ModelRateLimitError(ModelProviderError):
    """Raised when model provider rate limits are exceeded (HTTP 429)."""


class ModelTimeoutError(ModelProviderError):
    """Raised when model request execution times out."""


class ModelConnectionError(ModelProviderError):
    """Raised when connection to model provider fails (e.g. DNS failure, network reset)."""


class ModelRequestError(ModelError):
    """Raised when a model request is invalid."""


class ModelConfigurationError(ModelRequestError):
    """Raised when model or provider configuration is missing or invalid."""


class ModelResponseError(ModelError):
    """Raised when a model returns an invalid or malformed response."""


class ModelMalformedResponseError(ModelResponseError):
    """Raised when provider response cannot be parsed or lacks expected structure."""


class ModelResponseSizeExceededError(ModelResponseError):
    """Raised when provider response exceeds configured size limit."""

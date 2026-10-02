import pytest

from orion.models.errors import (
    ModelError,
    ModelProviderError,
    ModelProviderUnavailableError,
    ModelRequestError,
    ModelResponseError,
)


def test_model_error_is_base_exception() -> None:
    error = ModelError("Model operation failed.")

    assert str(error) == "Model operation failed."


def test_provider_error_inherits_from_model_error() -> None:
    error = ModelProviderError("Provider failed.")

    assert isinstance(error, ModelError)


def test_provider_unavailable_error_inherits_correctly() -> None:
    error = ModelProviderUnavailableError("Provider unavailable.")

    assert isinstance(error, ModelProviderError)
    assert isinstance(error, ModelError)


def test_request_error_inherits_from_model_error() -> None:
    error = ModelRequestError("Invalid request.")

    assert isinstance(error, ModelError)


def test_response_error_inherits_from_model_error() -> None:
    error = ModelResponseError("Invalid response.")

    assert isinstance(error, ModelError)


def test_errors_can_be_raised_and_caught_as_model_error() -> None:
    with pytest.raises(ModelError):
        raise ModelProviderUnavailableError("Provider unavailable.")


def test_new_typed_errors_hierarchy() -> None:
    from orion.models.errors import (
        ModelAuthenticationError,
        ModelConfigurationError,
        ModelConnectionError,
        ModelMalformedResponseError,
        ModelRateLimitError,
        ModelResponseSizeExceededError,
        ModelTimeoutError,
    )

    assert issubclass(ModelAuthenticationError, ModelProviderError)
    assert issubclass(ModelRateLimitError, ModelProviderError)
    assert issubclass(ModelTimeoutError, ModelProviderError)
    assert issubclass(ModelConnectionError, ModelProviderError)
    assert issubclass(ModelConfigurationError, ModelRequestError)
    assert issubclass(ModelMalformedResponseError, ModelResponseError)
    assert issubclass(ModelResponseSizeExceededError, ModelResponseError)


def test_sanitize_error_message_redacts_tokens_and_secrets() -> None:
    from orion.models.errors import sanitize_error_message

    msg = "Call to endpoint failed: Authorization: Bearer sk-secret-12345678"
    sanitized = sanitize_error_message(msg, secrets=("sk-secret-12345678",))
    assert "sk-secret-12345678" not in sanitized
    assert "Bearer [REDACTED]" in sanitized

    msg2 = "API key key_abcdef123456 failed"
    sanitized2 = sanitize_error_message(msg2, secrets=("key_abcdef123456",))
    assert "key_abcdef123456" not in sanitized2
    assert "[REDACTED]" in sanitized2

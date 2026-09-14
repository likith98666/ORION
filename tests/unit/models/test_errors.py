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
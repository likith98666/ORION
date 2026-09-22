import pytest

from orion.core.recovery.failure_classifier import FailureClassifier
from orion.core.recovery.failures import FailureType
from orion.models.errors import (
    ModelProviderError,
    ModelProviderUnavailableError,
    ModelRequestError,
    ModelResponseError,
)


@pytest.fixture
def classifier() -> FailureClassifier:
    return FailureClassifier()


def test_classifies_model_provider_unavailable_as_model_failure(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(
        ModelProviderUnavailableError("Provider unavailable")
    )

    assert failure.failure_type == FailureType.MODEL_FAILURE
    assert failure.message == "Provider unavailable"


def test_classifies_model_provider_error_as_model_failure(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(ModelProviderError("Provider failed"))

    assert failure.failure_type == FailureType.MODEL_FAILURE
    assert failure.message == "Provider failed"


def test_classifies_model_request_error_as_invalid_input(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(ModelRequestError("Invalid request"))

    assert failure.failure_type == FailureType.INVALID_INPUT
    assert failure.message == "Invalid request"


def test_classifies_model_response_error_as_model_failure(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(ModelResponseError("Invalid response"))

    assert failure.failure_type == FailureType.MODEL_FAILURE
    assert failure.message == "Invalid response"


def test_classifies_value_error_as_invalid_input(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(ValueError("Invalid value"))

    assert failure.failure_type == FailureType.INVALID_INPUT
    assert failure.message == "Invalid value"


def test_classifies_unknown_exception_as_unknown(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(RuntimeError("Unexpected failure"))

    assert failure.failure_type == FailureType.UNKNOWN
    assert failure.message == "Unexpected failure"


def test_specific_model_request_error_takes_precedence_over_model_error(
    classifier: FailureClassifier,
) -> None:
    failure = classifier.classify(ModelRequestError("Bad model request"))

    assert failure.failure_type == FailureType.INVALID_INPUT


def test_rejects_non_exception_input(
    classifier: FailureClassifier,
) -> None:
    with pytest.raises(TypeError, match="exception"):
        classifier.classify("not an exception")  # type: ignore[arg-type]

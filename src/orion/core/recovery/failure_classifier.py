from orion.core.recovery.failures import Failure, FailureType
from orion.models.errors import (
    ModelProviderError,
    ModelProviderUnavailableError,
    ModelRequestError,
    ModelResponseError,
)


class FailureClassifier:
    """Classifies execution exceptions into structured ORION failure types."""

    def classify(self, exception: Exception) -> Failure:
        """Classify an exception and return a structured failure."""

        if not isinstance(exception, Exception):
            raise TypeError("exception must be an Exception instance.")

        if isinstance(exception, ModelRequestError):
            failure_type = FailureType.INVALID_INPUT
        elif isinstance(
            exception,
            (
                ModelProviderUnavailableError,
                ModelProviderError,
                ModelResponseError,
            ),
        ):
            failure_type = FailureType.MODEL_FAILURE
        elif isinstance(exception, ValueError):
            failure_type = FailureType.INVALID_INPUT
        else:
            failure_type = FailureType.UNKNOWN

        return Failure(
            failure_type=failure_type,
            message=str(exception),
        )

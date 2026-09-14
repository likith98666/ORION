from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import ModelProviderError, ModelRequestError
from orion.models.providers.base import BaseModelProvider


class ModelGateway:
    """Entry point for sending model requests through ORION."""

    def __init__(self, provider: BaseModelProvider) -> None:
        self._provider = provider

    @property
    def provider_name(self) -> str:
        """Return the name of the active model provider."""
        return self._provider.name

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Validate a request and generate a response."""
        self._validate_request(request)

        try:
            return self._provider.generate(request)
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(
                f"Model provider '{self.provider_name}' failed: {exc}",
            ) from exc

    def health_check(self) -> bool:
        """Check whether the active model provider is available."""
        return self._provider.health_check()

    @staticmethod
    def _validate_request(request: ModelRequest) -> None:
        """Validate model request parameters before provider execution."""
        if not request.prompt.strip():
            raise ModelRequestError("Prompt cannot be empty")

        if not 0.0 <= request.temperature <= 2.0:
            raise ModelRequestError(
                "Temperature must be between 0.0 and 2.0",
            )

        if request.max_tokens is not None and request.max_tokens <= 0:
            raise ModelRequestError(
                "max_tokens must be greater than zero",
            )
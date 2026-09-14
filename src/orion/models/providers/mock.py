from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.providers.base import BaseModelProvider


class MockModelProvider(BaseModelProvider):
    """A deterministic model provider used for testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"text_generation"})

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Return a deterministic response without calling a real model."""
        return ModelResponse(
            text=f"Mock response for: {request.prompt}",
            model_name=self.model_name,
            provider_name=self.name,
        )

    def health_check(self) -> bool:
        """Return whether the mock provider is available."""
        return True
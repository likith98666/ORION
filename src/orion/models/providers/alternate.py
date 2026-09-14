from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.providers.base import BaseModelProvider


class AlternateModelProvider(BaseModelProvider):
    """A second deterministic provider for testing provider independence."""

    @property
    def name(self) -> str:
        return "alternate"

    @property
    def model_name(self) -> str:
        return "alternate-model"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"text_generation"})

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a deterministic response."""
        return ModelResponse(
            text=f"Alternate response for: {request.prompt}",
            model_name=self.model_name,
            provider_name=self.name,
        )

    def health_check(self) -> bool:
        """Return whether the provider is available."""
        return True
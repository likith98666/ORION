from abc import ABC, abstractmethod

from orion.models.contracts import ModelRequest, ModelResponse


class BaseModelProvider(ABC):
    """Base interface for all ORION model providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider's unique name."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the provider's active model name."""

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[str]:
        """Return the capabilities supported by the provider."""

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a response."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check whether the provider is available."""

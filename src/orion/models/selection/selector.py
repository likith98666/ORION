from orion.models.providers.base import BaseModelProvider
from orion.models.providers.registry import ModelProviderRegistry


class ModelSelector:
    """Selects a model provider from the ORION provider registry."""

    def __init__(self, registry: ModelProviderRegistry) -> None:
        self._registry = registry

    def select(self, provider_name: str) -> BaseModelProvider:
        """Select a registered provider by name."""
        cleaned_name = provider_name.strip()

        if not cleaned_name:
            raise ValueError(
                "Provider name cannot be empty.",
            )

        return self._registry.get(cleaned_name)

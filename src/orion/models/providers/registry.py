from orion.models.providers.base import BaseModelProvider


class ModelProviderRegistry:
    """Registry for managing ORION model providers."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseModelProvider] = {}

    def register(self, provider: BaseModelProvider) -> None:
        """Register a model provider."""
        if not isinstance(provider, BaseModelProvider):
            raise TypeError(
                "Provider must implement BaseModelProvider",
            )

        provider_name = provider.name

        if provider_name in self._providers:
            raise ValueError(
                f"Provider '{provider_name}' is already registered",
            )

        self._providers[provider_name] = provider

    def get(self, name: str) -> BaseModelProvider:
        """Retrieve a registered provider by name."""
        if name not in self._providers:
            raise KeyError(
                f"Provider '{name}' is not registered",
            )

        return self._providers[name]

    def list_names(self) -> list[str]:
        """Return the names of all registered providers."""
        return list(self._providers.keys())

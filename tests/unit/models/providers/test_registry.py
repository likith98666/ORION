import pytest

from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.registry import ModelProviderRegistry


def test_registry_registers_and_retrieves_provider() -> None:
    registry = ModelProviderRegistry()
    provider = MockModelProvider()

    registry.register(provider)

    assert registry.get("mock") is provider


def test_registry_supports_multiple_providers() -> None:
    registry = ModelProviderRegistry()

    mock_provider = MockModelProvider()
    alternate_provider = AlternateModelProvider()

    registry.register(mock_provider)
    registry.register(alternate_provider)

    assert registry.get("mock") is mock_provider
    assert registry.get("alternate") is alternate_provider


def test_registry_lists_registered_provider_names() -> None:
    registry = ModelProviderRegistry()

    registry.register(MockModelProvider())
    registry.register(AlternateModelProvider())

    assert registry.list_names() == ["mock", "alternate"]


def test_registry_rejects_duplicate_provider_name() -> None:
    registry = ModelProviderRegistry()

    registry.register(MockModelProvider())

    with pytest.raises(
        ValueError,
        match="Provider 'mock' is already registered",
    ):
        registry.register(MockModelProvider())


def test_registry_rejects_unknown_provider() -> None:
    registry = ModelProviderRegistry()

    with pytest.raises(
        KeyError,
        match="Provider 'unknown' is not registered",
    ):
        registry.get("unknown")


def test_registry_rejects_invalid_provider() -> None:
    registry = ModelProviderRegistry()

    class InvalidProvider:
        pass

    with pytest.raises(
        TypeError,
        match="Provider must implement BaseModelProvider",
    ):
        registry.register(InvalidProvider())  # type: ignore[arg-type]
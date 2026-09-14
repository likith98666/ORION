import pytest

from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.selection.selector import ModelSelector


def test_selector_returns_registered_provider() -> None:
    registry = ModelProviderRegistry()
    provider = MockModelProvider()

    registry.register(provider)

    selector = ModelSelector(registry)

    selected_provider = selector.select("mock")

    assert selected_provider is provider


def test_selector_supports_multiple_providers() -> None:
    registry = ModelProviderRegistry()

    mock_provider = MockModelProvider()
    alternate_provider = AlternateModelProvider()

    registry.register(mock_provider)
    registry.register(alternate_provider)

    selector = ModelSelector(registry)

    selected_mock = selector.select("mock")
    selected_alternate = selector.select("alternate")

    assert selected_mock is mock_provider
    assert selected_alternate is alternate_provider


def test_selector_strips_provider_name() -> None:
    registry = ModelProviderRegistry()
    provider = MockModelProvider()

    registry.register(provider)

    selector = ModelSelector(registry)

    selected_provider = selector.select("  mock  ")

    assert selected_provider is provider


def test_selector_rejects_empty_provider_name() -> None:
    registry = ModelProviderRegistry()
    selector = ModelSelector(registry)

    with pytest.raises(
        ValueError,
        match="Provider name cannot be empty",
    ):
        selector.select("   ")


def test_selector_rejects_unknown_provider() -> None:
    registry = ModelProviderRegistry()
    selector = ModelSelector(registry)

    with pytest.raises(
        KeyError,
        match="Provider 'unknown' is not registered",
    ):
        selector.select("unknown")
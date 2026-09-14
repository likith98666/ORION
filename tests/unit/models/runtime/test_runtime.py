from orion.config.model_config import ModelConfig
from orion.models.contracts import ModelRequest
from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.runtime.runtime import ModelRuntime
from orion.models.selection.selector import ModelSelector


def create_runtime() -> ModelRuntime:
    registry = ModelProviderRegistry()

    registry.register(MockModelProvider())
    registry.register(AlternateModelProvider())

    selector = ModelSelector(registry)

    return ModelRuntime(selector)


def test_runtime_selects_provider_and_generates_response() -> None:
    runtime = create_runtime()

    config = ModelConfig(
        provider_name="mock",
    )

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = runtime.generate(
        config,
        request,
    )

    assert response.text == "Mock response for: Hello ORION"
    assert response.provider_name == "mock"
    assert response.model_name == "mock-model"


def test_runtime_can_use_different_provider() -> None:
    runtime = create_runtime()

    config = ModelConfig(
        provider_name="alternate",
    )

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = runtime.generate(
        config,
        request,
    )

    assert response.text == "Alternate response for: Hello ORION"
    assert response.provider_name == "alternate"
    assert response.model_name == "alternate-model"


def test_runtime_passes_configured_values_to_provider() -> None:
    runtime = create_runtime()

    config = ModelConfig(
        provider_name="mock",
        temperature=0.7,
        max_tokens=100,
    )

    request = ModelRequest(
        prompt="Analyze this task",
        temperature=0.2,
        max_tokens=50,
    )

    response = runtime.generate(
        config,
        request,
    )

    assert response.text == "Mock response for: Analyze this task"
    assert response.provider_name == "mock"
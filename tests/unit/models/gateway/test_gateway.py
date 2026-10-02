import pytest

from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import ModelProviderError, ModelRequestError
from orion.models.gateway.gateway import ModelGateway
from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.registry import ModelProviderRegistry


def test_gateway_uses_provider() -> None:
    provider = MockModelProvider()
    gateway = ModelGateway(provider)

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = gateway.generate(request)

    assert response.text == "Mock response for: Hello ORION"
    assert response.provider_name == "mock"
    assert response.model_name == "mock-model"


def test_gateway_reports_provider_name() -> None:
    provider = MockModelProvider()
    gateway = ModelGateway(provider)

    assert gateway.provider_name == "mock"


def test_gateway_health_check() -> None:
    provider = MockModelProvider()
    gateway = ModelGateway(provider)

    assert gateway.health_check() is True


def test_gateway_rejects_empty_prompt() -> None:
    gateway = ModelGateway(MockModelProvider())

    request = ModelRequest(
        prompt="   ",
    )

    with pytest.raises(
        ModelRequestError,
        match="Prompt cannot be empty",
    ):
        gateway.generate(request)


def test_gateway_rejects_negative_temperature() -> None:
    gateway = ModelGateway(MockModelProvider())

    request = ModelRequest(
        prompt="Test prompt",
        temperature=-0.1,
    )

    with pytest.raises(
        ModelRequestError,
        match="Temperature must be between 0.0 and 2.0",
    ):
        gateway.generate(request)


def test_gateway_rejects_temperature_above_limit() -> None:
    gateway = ModelGateway(MockModelProvider())

    request = ModelRequest(
        prompt="Test prompt",
        temperature=2.1,
    )

    with pytest.raises(
        ModelRequestError,
        match="Temperature must be between 0.0 and 2.0",
    ):
        gateway.generate(request)


def test_gateway_rejects_zero_max_tokens() -> None:
    gateway = ModelGateway(MockModelProvider())

    request = ModelRequest(
        prompt="Test prompt",
        max_tokens=0,
    )

    with pytest.raises(
        ModelRequestError,
        match="max_tokens must be greater than zero",
    ):
        gateway.generate(request)


def test_gateway_rejects_negative_max_tokens() -> None:
    gateway = ModelGateway(MockModelProvider())

    request = ModelRequest(
        prompt="Test prompt",
        max_tokens=-10,
    )

    with pytest.raises(
        ModelRequestError,
        match="max_tokens must be greater than zero",
    ):
        gateway.generate(request)


def test_gateway_wraps_provider_failure() -> None:
    class FailingProvider(MockModelProvider):
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError("Provider crashed")

    gateway = ModelGateway(FailingProvider())

    request = ModelRequest(
        prompt="Test provider failure",
    )

    with pytest.raises(
        ModelProviderError,
        match="Provider crashed",
    ):
        gateway.generate(request)


def test_gateway_preserves_model_provider_error() -> None:
    class FailingProvider(MockModelProvider):
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise ModelProviderError("Original provider error")

    gateway = ModelGateway(FailingProvider())

    request = ModelRequest(
        prompt="Test provider error",
    )

    with pytest.raises(
        ModelProviderError,
        match="Original provider error",
    ) as exc_info:
        gateway.generate(request)

    assert str(exc_info.value) == "Original provider error"


def test_gateway_supports_alternate_provider() -> None:
    provider = AlternateModelProvider()
    gateway = ModelGateway(provider)

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = gateway.generate(request)

    assert response.text == "Alternate response for: Hello ORION"
    assert response.provider_name == "alternate"
    assert response.model_name == "alternate-model"


def test_gateway_can_use_provider_from_registry() -> None:
    registry = ModelProviderRegistry()
    provider = AlternateModelProvider()

    registry.register(provider)

    gateway = ModelGateway(
        registry.get("alternate"),
    )

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = gateway.generate(request)

    assert response.text == "Alternate response for: Hello ORION"
    assert response.provider_name == "alternate"
    assert response.model_name == "alternate-model"


def test_gateway_wraps_unexpected_provider_exception() -> None:
    class FailingProvider(MockModelProvider):
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError("Unexpected failure")

    gateway = ModelGateway(FailingProvider())

    request = ModelRequest(
        prompt="Test failure",
    )

    with pytest.raises(
        ModelProviderError,
        match="Model provider 'mock' failed: Unexpected failure",
    ):
        gateway.generate(request)

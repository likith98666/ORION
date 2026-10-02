from orion.models.contracts import ModelRequest
from orion.models.providers.mock import MockModelProvider


def test_mock_provider_name() -> None:
    provider = MockModelProvider()

    assert provider.name == "mock"


def test_mock_provider_health_check() -> None:
    provider = MockModelProvider()

    assert provider.health_check() is True


def test_mock_provider_model_name() -> None:
    provider = MockModelProvider()

    assert provider.model_name == "mock-model"


def test_mock_provider_capabilities() -> None:
    provider = MockModelProvider()

    assert provider.capabilities == frozenset({"text_generation"})


def test_mock_provider_generates_response() -> None:
    provider = MockModelProvider()

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = provider.generate(request)

    assert response.text == "Mock response for: Hello ORION"
    assert response.provider_name == "mock"
    assert response.model_name == "mock-model"


def test_mock_provider_preserves_request_prompt() -> None:
    provider = MockModelProvider()

    request = ModelRequest(
        prompt="Analyze this task",
    )

    response = provider.generate(request)

    assert "Analyze this task" in response.text

from orion.models.contracts import ModelRequest
from orion.models.providers.alternate import AlternateModelProvider


def test_alternate_provider_name() -> None:
    provider = AlternateModelProvider()

    assert provider.name == "alternate"


def test_alternate_provider_health_check() -> None:
    provider = AlternateModelProvider()

    assert provider.health_check() is True


def test_alternate_provider_model_name() -> None:
    provider = AlternateModelProvider()

    assert provider.model_name == "alternate-model"


def test_alternate_provider_capabilities() -> None:
    provider = AlternateModelProvider()

    assert provider.capabilities == frozenset({"text_generation"})


def test_alternate_provider_generates_response() -> None:
    provider = AlternateModelProvider()

    request = ModelRequest(
        prompt="Hello ORION",
    )

    response = provider.generate(request)

    assert response.text == "Alternate response for: Hello ORION"
    assert response.provider_name == "alternate"
    assert response.model_name == "alternate-model"


def test_alternate_provider_preserves_request_prompt() -> None:
    provider = AlternateModelProvider()

    request = ModelRequest(
        prompt="Analyze this task",
    )

    response = provider.generate(request)

    assert "Analyze this task" in response.text

import pytest

from orion.models.contracts import (
    ModelRequest,
    ModelResponse,
)


def test_model_request_defaults() -> None:
    request = ModelRequest(
        prompt="Hello ORION",
    )

    assert request.prompt == "Hello ORION"
    assert request.system_prompt is None
    assert request.temperature == 0.0
    assert request.max_tokens is None
    assert request.metadata is None


def test_model_request_accepts_configuration() -> None:
    request = ModelRequest(
        prompt="Analyze this data.",
        system_prompt="You are a data analyst.",
        temperature=0.2,
        max_tokens=500,
        metadata={"task_id": "test-123"},
    )

    assert request.prompt == "Analyze this data."
    assert request.system_prompt == "You are a data analyst."
    assert request.temperature == 0.2
    assert request.max_tokens == 500
    assert request.metadata == {"task_id": "test-123"}


def test_model_response_defaults() -> None:
    response = ModelResponse(
        text="Hello!",
        model_name="test-model",
        provider_name="test-provider",
    )

    assert response.text == "Hello!"
    assert response.model_name == "test-model"
    assert response.provider_name == "test-provider"
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.latency_ms is None


def test_model_response_accepts_metrics() -> None:
    response = ModelResponse(
        text="Analysis complete.",
        model_name="test-model",
        provider_name="local",
        input_tokens=100,
        output_tokens=50,
        latency_ms=245.7,
    )

    assert response.input_tokens == 100
    assert response.output_tokens == 50
    assert response.latency_ms == 245.7


def test_model_request_is_immutable() -> None:
    request = ModelRequest(
        prompt="Test prompt",
    )

    with pytest.raises(AttributeError):
        request.prompt = "Changed"


def test_model_response_is_immutable() -> None:
    response = ModelResponse(
        text="Test response",
        model_name="test-model",
        provider_name="test-provider",
    )

    with pytest.raises(AttributeError):
        response.text = "Changed"
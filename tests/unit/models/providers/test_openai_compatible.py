"""Deterministic unit tests for OpenAICompatibleProvider using an injectable transport boundary."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from orion.models.contracts import ModelRequest
from orion.models.errors import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelMalformedResponseError,
    ModelProviderUnavailableError,
    ModelRateLimitError,
    ModelRequestError,
    ModelResponseSizeExceededError,
    ModelTimeoutError,
)
from orion.models.providers.openai_compatible import OpenAICompatibleProvider


def _build_openai_response(
    content: str = "Test response text",
    model: str = "gpt-4o",
    finish_reason: str = "stop",
    prompt_tokens: int = 12,
    completion_tokens: int = 8,
    response_id: str = "chatcmpl-test-123",
) -> bytes:
    """Helper creating standard OpenAI chat completion JSON payload."""
    payload = {
        "id": response_id,
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return json.dumps(payload).encode("utf-8")


def test_provider_attributes_and_defaults():
    """Verify default attributes and capability definitions."""
    provider = OpenAICompatibleProvider(api_key="sk-test-key")
    assert provider.name == "openai"
    assert provider.model_name == "gpt-4o"
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.timeout_seconds == 30.0
    assert provider.max_response_bytes == 1048576
    assert "text_generation" in provider.capabilities
    assert "structured_output" in provider.capabilities


def test_provider_health_check():
    """Verify health check returns False without key, True with key."""
    p_no_key = OpenAICompatibleProvider(api_key=None)
    assert p_no_key.health_check() is False

    p_empty_key = OpenAICompatibleProvider(api_key="   ")
    assert p_empty_key.health_check() is False

    p_valid_key = OpenAICompatibleProvider(api_key="sk-valid-key")
    assert p_valid_key.health_check() is True


def test_provider_rejects_missing_api_key_on_generate():
    """Verify generate() raises ModelAuthenticationError if API key is not configured."""
    provider = OpenAICompatibleProvider(api_key=None)
    request = ModelRequest(prompt="Hello")

    with pytest.raises(ModelAuthenticationError) as exc_info:
        provider.generate(request)

    assert "API key is not configured" in str(exc_info.value)


def test_provider_request_construction_with_transport():
    """Verify endpoint, HTTP headers, and JSON body payload construction."""
    captured_req: list[urllib.request.Request] = []

    def mock_transport(req: urllib.request.Request, timeout: float):
        captured_req.append(req)
        return 200, _build_openai_response(content="Generated reply"), {}

    provider = OpenAICompatibleProvider(
        name="custom-openai",
        model_name="gpt-4o-mini",
        api_key="sk-secret-token-12345",
        base_url="https://custom.endpoint.com/v1",
        timeout_seconds=45.0,
        transport=mock_transport,
    )

    request = ModelRequest(
        prompt="Explain recursion.",
        system_prompt="You are a computer science professor.",
        temperature=0.3,
        max_tokens=250,
        structured_output=True,
    )

    resp = provider.generate(request)

    assert len(captured_req) == 1
    req = captured_req[0]
    assert req.full_url == "https://custom.endpoint.com/v1/chat/completions"
    assert req.headers.get("Content-type") == "application/json"
    assert req.headers.get("Authorization") == "Bearer sk-secret-token-12345"

    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "gpt-4o-mini"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 250
    assert body["response_format"] == {"type": "json_object"}
    assert len(body["messages"]) == 2
    assert body["messages"][0] == {
        "role": "system",
        "content": "You are a computer science professor.",
    }
    assert body["messages"][1] == {"role": "user", "content": "Explain recursion."}

    assert resp.text == "Generated reply"
    assert resp.model_name == "gpt-4o"
    assert resp.provider_name == "custom-openai"
    assert resp.input_tokens == 12
    assert resp.output_tokens == 8
    assert resp.finish_reason == "stop"
    assert resp.request_id == "chatcmpl-test-123"
    assert resp.latency_ms is not None and resp.latency_ms >= 0


def test_provider_rejects_malformed_json():
    """Verify malformed JSON from provider raises ModelMalformedResponseError."""

    def mock_transport(req, timeout):
        return 200, b"<html>502 Bad Gateway</html>", {}

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(ModelMalformedResponseError) as exc_info:
        provider.generate(ModelRequest(prompt="Hi"))

    assert "Malformed JSON" in str(exc_info.value)


def test_provider_rejects_missing_choices():
    """Verify response without choices raises ModelMalformedResponseError."""

    def mock_transport(req, timeout):
        return 200, json.dumps({"id": "123", "choices": []}).encode("utf-8"), {}

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(ModelMalformedResponseError):
        provider.generate(ModelRequest(prompt="Hi"))


def test_provider_rejects_missing_content():
    """Verify choice without content string raises ModelMalformedResponseError."""

    def mock_transport(req, timeout):
        return 200, json.dumps({"choices": [{"message": {}}]}).encode("utf-8"), {}

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(ModelMalformedResponseError):
        provider.generate(ModelRequest(prompt="Hi"))


def test_provider_enforces_max_response_bytes():
    """Verify response exceeding max_response_bytes raises ModelResponseSizeExceededError."""
    huge_text = "A" * 5000
    huge_payload = _build_openai_response(content=huge_text)

    def mock_transport(req, timeout):
        return 200, huge_payload, {}

    # Set tight limit of 1024 bytes
    provider = OpenAICompatibleProvider(
        api_key="sk-key",
        max_response_bytes=1024,
        transport=mock_transport,
    )

    with pytest.raises(ModelResponseSizeExceededError) as exc_info:
        provider.generate(ModelRequest(prompt="Generate big text"))

    assert "exceeded maximum configured limit" in str(exc_info.value)


@pytest.mark.parametrize(
    "status_code,expected_error",
    [
        (401, ModelAuthenticationError),
        (403, ModelAuthenticationError),
        (429, ModelRateLimitError),
        (400, ModelRequestError),
        (500, ModelProviderUnavailableError),
        (502, ModelProviderUnavailableError),
        (503, ModelProviderUnavailableError),
    ],
)
def test_provider_http_error_mapping(status_code: int, expected_error: type[Exception]):
    """Verify HTTP status codes map to specific typed exceptions."""

    def mock_transport(req, timeout):
        err_json = json.dumps({"error": {"message": f"Server reported {status_code}"}}).encode(
            "utf-8"
        )
        return status_code, err_json, {}

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(expected_error) as exc_info:
        provider.generate(ModelRequest(prompt="Hello"))

    assert str(status_code) in str(exc_info.value)


def test_provider_timeout_handling():
    """Verify socket/network timeouts raise ModelTimeoutError."""

    def mock_transport(req, timeout):
        raise TimeoutError("Operation timed out")

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(ModelTimeoutError) as exc_info:
        provider.generate(ModelRequest(prompt="Wait forever"))

    assert "timed out" in str(exc_info.value).lower()


def test_provider_connection_failure():
    """Verify connection errors raise ModelConnectionError."""

    def mock_transport(req, timeout):
        raise urllib.error.URLError("Name or service not known")

    provider = OpenAICompatibleProvider(api_key="sk-key", transport=mock_transport)
    with pytest.raises(ModelConnectionError) as exc_info:
        provider.generate(ModelRequest(prompt="Check DNS"))

    assert "failed" in str(exc_info.value).lower()


def test_provider_secret_redaction_in_exceptions():
    """Verify API keys are never leaked into error messages or exception details."""
    sensitive_key = "sk-super-secret-key-must-never-leak"

    def mock_transport(req, timeout):
        # Transport receives request containing the bearer header
        auth_hdr = req.headers.get("Authorization", "")
        # Return an error that echoes the header back maliciously
        err_body = json.dumps({"error": f"Bad auth header: {auth_hdr}"}).encode("utf-8")
        return 401, err_body, {}

    provider = OpenAICompatibleProvider(api_key=sensitive_key, transport=mock_transport)

    with pytest.raises(ModelAuthenticationError) as exc_info:
        provider.generate(ModelRequest(prompt="Test auth leak"))

    err_msg = str(exc_info.value)
    # The actual key must NEVER be in the error message
    assert sensitive_key not in err_msg
    assert "[REDACTED]" in err_msg


def test_provider_from_env_factory():
    """Verify provider correctly parses configuration from environment mapping."""
    fake_env = {
        "ORION_MODEL_PROVIDER": "azure-openai",
        "ORION_MODEL_NAME": "gpt-4-turbo",
        "ORION_MODEL_BASE_URL": "https://my-azure.openai.azure.com/v1",
        "ORION_MODEL_API_KEY": "sk-azure-12345",
        "ORION_MODEL_TIMEOUT": "25.5",
    }

    provider = OpenAICompatibleProvider.from_env(env=fake_env)
    assert provider.name == "azure-openai"
    assert provider.model_name == "gpt-4-turbo"
    assert provider.base_url == "https://my-azure.openai.azure.com/v1"
    assert provider._api_key == "sk-azure-12345"
    assert provider.timeout_seconds == 25.5
    assert provider.health_check() is True

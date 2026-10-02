from __future__ import annotations

import re
from pathlib import Path

import pytest

import orion
from orion.api.server import ORION_VERSION
from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import (
    ModelProviderError,
    ModelRequestError,
    ModelResponseSizeExceededError,
)
from orion.models.gateway.gateway import ModelGateway
from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.openai_compatible import OpenAICompatibleProvider


def test_gateway_rejects_oversized_prompt() -> None:
    gateway = ModelGateway(MockModelProvider(), max_prompt_chars=500)
    oversized_prompt = "A" * 501
    request = ModelRequest(prompt=oversized_prompt)

    with pytest.raises(ModelRequestError, match="Prompt length .* exceeds maximum allowed limit"):
        gateway.generate(request)


def test_gateway_rejects_oversized_system_prompt() -> None:
    gateway = ModelGateway(MockModelProvider(), max_prompt_chars=500)
    oversized_system = "S" * 501
    request = ModelRequest(prompt="Valid prompt", system_prompt=oversized_system)

    with pytest.raises(
        ModelRequestError, match="System prompt length .* exceeds maximum allowed limit"
    ):
        gateway.generate(request)


def test_gateway_enforces_response_size_limit() -> None:
    class BigOutputProvider(MockModelProvider):
        def generate(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(
                text="X" * 1000,
                model_name=self.model_name,
                provider_name=self.name,
            )

    gateway = ModelGateway(BigOutputProvider(), max_response_chars=500)
    request = ModelRequest(prompt="Generate big response")

    with pytest.raises(
        ModelResponseSizeExceededError,
        match="Model response text length .* exceeded gateway maximum limit",
    ):
        gateway.generate(request)


def test_gateway_sanitizes_secrets_in_exceptions() -> None:
    class LeakySecretProvider(MockModelProvider):
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError(
                "Request with Bearer sk-live-secret-key-12345 failed to authenticate"
            )

    gateway = ModelGateway(LeakySecretProvider())
    request = ModelRequest(prompt="Hello")

    with pytest.raises(ModelProviderError) as exc_info:
        gateway.generate(request)

    err_msg = str(exc_info.value)
    assert "sk-live-secret-key-12345" not in err_msg
    assert "Bearer [REDACTED]" in err_msg


def test_gateway_authority_separation_invariant() -> None:
    """Verify architectural invariant: ModelGateway is pure cognitive data generation only.

    It must NEVER expose or implement tool execution, file modification,
    verification assertion, or approval bypass methods.
    """
    gateway = ModelGateway(MockModelProvider())

    forbidden_attributes = [
        "execute_tool",
        "run_tool",
        "write_file",
        "delete_file",
        "approve",
        "verify",
        "mark_verified",
        "bypass_security",
        "tool_executor",
        "approval_service",
        "verification_engine",
    ]

    for attr in forbidden_attributes:
        assert not hasattr(gateway, attr), f"ModelGateway must not expose '{attr}'"

    # Must only return data response
    res = gateway.generate(ModelRequest(prompt="What is 2+2?"))
    assert isinstance(res, ModelResponse)
    assert isinstance(res.text, str)


def test_gateway_provider_interchangeability() -> None:
    """Verify mock, alternate, and real provider can all be driven by ModelGateway."""
    # 1. Mock
    gw_mock = ModelGateway(MockModelProvider())
    res_mock = gw_mock.generate(ModelRequest(prompt="test mock"))
    assert res_mock.provider_name == "mock"

    # 2. Alternate
    gw_alt = ModelGateway(AlternateModelProvider())
    res_alt = gw_alt.generate(ModelRequest(prompt="test alt"))
    assert res_alt.provider_name == "alternate"

    # 3. Real OpenAI-compatible provider with injectable transport
    def fake_transport(req: object, timeout: float) -> tuple[int, bytes, dict[str, str]]:
        payload = {
            "id": "chatcmpl-gw-test",
            "choices": [
                {"message": {"role": "assistant", "content": "Real response through gateway"}}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }
        import json

        return 200, json.dumps(payload).encode("utf-8"), {"content-type": "application/json"}

    real_provider = OpenAICompatibleProvider(
        api_key="test-key",
        transport=fake_transport,
    )
    gw_real = ModelGateway(real_provider)
    res_real = gw_real.generate(ModelRequest(prompt="test real"))
    assert res_real.provider_name == "openai"
    assert res_real.text == "Real response through gateway"
    assert res_real.input_tokens == 5
    assert res_real.output_tokens == 5


def test_gateway_rejects_non_provider() -> None:
    with pytest.raises(TypeError, match="provider must implement BaseModelProvider"):
        ModelGateway("not a provider")  # type: ignore[arg-type]


def test_version_harmonization() -> None:
    """Verify pyproject.toml, server.py, and orion.__version__ are consistently 1.0.0."""
    # 1. orion.__version__
    assert orion.__version__ == "1.0.0"

    # 2. ORION_VERSION in server.py
    assert ORION_VERSION == "1.0.0"

    # 3. pyproject.toml
    pyproject_path = Path(__file__).resolve().parents[4] / "pyproject.toml"
    assert pyproject_path.is_file(), f"pyproject.toml not found at {pyproject_path}"

    content = pyproject_path.read_text(encoding="utf-8")
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
    assert version_match is not None, "Version not found in pyproject.toml"
    assert version_match.group(1) == "1.0.0"

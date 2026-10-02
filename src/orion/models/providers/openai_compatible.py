"""Production-grade OpenAI-compatible HTTP Model Provider using Python standard library networking.

Supports:
- OpenAI, Azure OpenAI, vLLM, Ollama, and any OpenAI-compatible HTTP inference endpoint
- Zero third-party runtime HTTP dependencies (pure urllib.request, urllib.error, json, ssl)
- Explicit timeouts, bounded response streams, and secret redaction
- Injectable transport boundary for deterministic unit/integration testing
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelMalformedResponseError,
    ModelProviderError,
    ModelProviderUnavailableError,
    ModelRateLimitError,
    ModelRequestError,
    ModelResponseError,
    ModelResponseSizeExceededError,
    ModelTimeoutError,
    sanitize_error_message,
)
from orion.models.providers.base import BaseModelProvider

TransportCallable = Callable[[urllib.request.Request, float], tuple[int, bytes, dict[str, str]]]


class OpenAICompatibleProvider(BaseModelProvider):
    """OpenAI-compatible HTTP model provider using Python standard library networking."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_TIMEOUT_SECONDS = 30.0
    DEFAULT_MAX_RESPONSE_BYTES = 1048576  # 1 MB

    def __init__(
        self,
        name: str = "openai",
        model_name: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        transport: TransportCallable | None = None,
    ) -> None:
        self._name = name.strip() or "openai"
        self._model_name = model_name.strip() or self.DEFAULT_MODEL
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._base_url = (base_url.strip() or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._max_response_bytes = max(1024, int(max_response_bytes))
        self._transport = transport

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset(
            {
                "text_generation",
                "chat",
                "structured_output",
                "code_synthesis",
            }
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @property
    def max_response_bytes(self) -> int:
        return self._max_response_bytes

    def health_check(self) -> bool:
        """Check whether the provider has minimum viable configuration."""
        return self._api_key is not None and len(self._api_key) > 0

    def _sanitize(self, message: str) -> str:
        """Sanitize message using the provider's active API key."""
        return sanitize_error_message(message, secrets=(self._api_key,))

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Execute a completion request against the OpenAI-compatible HTTP endpoint."""
        if not self._api_key:
            raise ModelAuthenticationError(
                f"API key is not configured for model provider '{self._name}'. "
                "Set ORION_MODEL_API_KEY environment variable or supply api_key in configuration."
            )

        endpoint = f"{self._base_url}/chat/completions"

        # Build messages payload
        messages: list[dict[str, str]] = []
        if request.system_prompt and request.system_prompt.strip():
            messages.append({"role": "system", "content": request.system_prompt.strip()})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        if request.response_format is not None:
            payload["response_format"] = request.response_format
        elif request.structured_output:
            payload["response_format"] = {"type": "json_object"}

        encoded_data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "ORION-Autonomous-Platform/1.0.0",
        }

        http_req = urllib.request.Request(
            url=endpoint,
            data=encoded_data,
            headers=headers,
            method="POST",
        )

        start_time = time.perf_counter()

        try:
            if self._transport is not None:
                status_code, body_bytes, _ = self._transport(http_req, self._timeout_seconds)
                if status_code >= 400:
                    self._handle_http_error_code(status_code, body_bytes)
            else:
                with urllib.request.urlopen(http_req, timeout=self._timeout_seconds) as resp:
                    status_code = resp.status
                    # Bounded read to avoid unbounded memory consumption
                    body_bytes = resp.read(self._max_response_bytes + 1)

        except urllib.error.HTTPError as exc:
            err_body = b""
            try:
                err_body = exc.read(4096)
            except Exception:
                pass
            self._handle_http_error_code(exc.code, err_body, exc)

        except TimeoutError as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            clean_msg = self._sanitize(
                f"Model request to '{self._name}' timed out after {self._timeout_seconds}s."
            )
            raise ModelTimeoutError(clean_msg) from exc

        except urllib.error.URLError as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            reason_str = str(exc.reason).lower()
            if "timed out" in reason_str:
                clean_msg = self._sanitize(
                    f"Model request to '{self._name}' timed out: {exc.reason}"
                )
                raise ModelTimeoutError(clean_msg) from exc
            clean_msg = self._sanitize(
                f"Connection to model provider '{self._name}' failed: {exc.reason}"
            )
            raise ModelConnectionError(clean_msg) from exc

        except (ModelProviderError, ModelRequestError, ModelResponseError):
            raise

        except Exception as exc:
            clean_msg = self._sanitize(
                f"Unexpected error communicating with provider '{self._name}': {exc}"
            )
            raise ModelProviderError(clean_msg) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Enforce maximum response size bound
        if len(body_bytes) > self._max_response_bytes:
            raise ModelResponseSizeExceededError(
                f"Model response size ({len(body_bytes)} bytes) exceeded maximum configured limit "
                f"({self._max_response_bytes} bytes)."
            )

        # Parse JSON response
        try:
            resp_json = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            clean_msg = self._sanitize(f"Malformed JSON returned by provider '{self._name}': {exc}")
            raise ModelMalformedResponseError(clean_msg) from exc

        if not isinstance(resp_json, dict):
            raise ModelMalformedResponseError(
                f"Provider '{self._name}' response must be a JSON object."
            )

        choices = resp_json.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise ModelMalformedResponseError(
                f"Provider '{self._name}' response missing choices list."
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict) or "message" not in first_choice:
            raise ModelMalformedResponseError(
                f"Provider '{self._name}' response choice missing message object."
            )

        message_obj = first_choice.get("message", {})
        content = message_obj.get("content")
        if content is None or not isinstance(content, str):
            raise ModelMalformedResponseError(
                f"Provider '{self._name}' response message missing content string."
            )

        finish_reason = first_choice.get("finish_reason")
        request_id = resp_json.get("id")

        # Extract usage metrics safely
        usage_obj = resp_json.get("usage", {})
        input_tokens = usage_obj.get("prompt_tokens") if isinstance(usage_obj, dict) else None
        output_tokens = usage_obj.get("completion_tokens") if isinstance(usage_obj, dict) else None
        raw_usage = dict(usage_obj) if isinstance(usage_obj, dict) else None

        return ModelResponse(
            text=content,
            model_name=resp_json.get("model", self._model_name),
            provider_name=self._name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            request_id=request_id,
            raw_usage=raw_usage,
        )

    def _handle_http_error_code(
        self,
        status_code: int,
        body_bytes: bytes,
        original_exc: Exception | None = None,
    ) -> None:
        """Map HTTP error status codes to typed exceptions without leaking credentials."""
        detail = ""
        try:
            if body_bytes:
                err_data = json.loads(body_bytes.decode("utf-8"))
                if isinstance(err_data, dict):
                    err_inner = err_data.get("error", {})
                    if isinstance(err_inner, dict):
                        detail = err_inner.get("message", "")
                    elif isinstance(err_inner, str):
                        detail = err_inner
                    else:
                        detail = str(err_data)
        except Exception:
            detail = body_bytes[:200].decode("utf-8", errors="replace")

        clean_detail = self._sanitize(detail.strip())
        detail_suffix = f": {clean_detail}" if clean_detail else ""

        if status_code in (401, 403):
            msg = self._sanitize(
                f"Authentication failed for provider '{self._name}' "
                f"(HTTP {status_code}){detail_suffix}"
            )
            raise ModelAuthenticationError(msg) from original_exc

        if status_code == 429:
            msg = self._sanitize(
                f"Rate limit exceeded for provider '{self._name}' (HTTP 429){detail_suffix}"
            )
            raise ModelRateLimitError(msg) from original_exc

        if status_code == 400:
            msg = self._sanitize(
                f"Invalid model request to provider '{self._name}' (HTTP 400){detail_suffix}"
            )
            raise ModelRequestError(msg) from original_exc

        if status_code in (500, 502, 503, 504):
            msg = self._sanitize(
                f"Model provider '{self._name}' is unavailable (HTTP {status_code}){detail_suffix}"
            )
            raise ModelProviderUnavailableError(msg) from original_exc

        msg = self._sanitize(
            f"Model provider '{self._name}' request failed with HTTP {status_code}{detail_suffix}"
        )
        raise ModelProviderError(msg) from original_exc

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        transport: TransportCallable | None = None,
    ) -> OpenAICompatibleProvider:
        """Instantiate OpenAICompatibleProvider from environment variables."""
        import os

        e = env if env is not None else os.environ
        name = e.get("ORION_MODEL_PROVIDER", "openai").strip() or "openai"
        model_name = e.get("ORION_MODEL_NAME", cls.DEFAULT_MODEL).strip() or cls.DEFAULT_MODEL
        base_url = (
            e.get("ORION_MODEL_BASE_URL", cls.DEFAULT_BASE_URL).strip() or cls.DEFAULT_BASE_URL
        )
        api_key = e.get("ORION_MODEL_API_KEY", "").strip() or None

        timeout_str = e.get("ORION_MODEL_TIMEOUT", str(cls.DEFAULT_TIMEOUT_SECONDS)).strip()
        try:
            timeout_seconds = float(timeout_str)
        except ValueError:
            timeout_seconds = cls.DEFAULT_TIMEOUT_SECONDS

        return cls(
            name=name,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

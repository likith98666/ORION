"""ORION Model Abstraction and Gateway Subsystem."""

from orion.models.context import (
    ContextAssembler,
    ContextLimits,
    PromptInjectionDetector,
    SecureModelContext,
)
from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.errors import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelError,
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
from orion.models.gateway.gateway import ModelGateway
from orion.models.providers.alternate import AlternateModelProvider
from orion.models.providers.base import BaseModelProvider
from orion.models.providers.mock import MockModelProvider
from orion.models.providers.openai_compatible import OpenAICompatibleProvider
from orion.models.providers.registry import ModelProviderRegistry
from orion.models.runtime.runtime import ModelRuntime
from orion.models.selection.selector import ModelSelector

__all__ = [
    "AlternateModelProvider",
    "BaseModelProvider",
    "ContextAssembler",
    "ContextLimits",
    "MockModelProvider",
    "ModelAuthenticationError",
    "ModelConnectionError",
    "ModelError",
    "ModelGateway",
    "ModelMalformedResponseError",
    "ModelProviderError",
    "ModelProviderRegistry",
    "ModelProviderUnavailableError",
    "ModelRateLimitError",
    "ModelRequest",
    "ModelRequestError",
    "ModelResponse",
    "ModelResponseError",
    "ModelResponseSizeExceededError",
    "ModelRuntime",
    "ModelSelector",
    "ModelTimeoutError",
    "OpenAICompatibleProvider",
    "PromptInjectionDetector",
    "SecureModelContext",
    "sanitize_error_message",
]

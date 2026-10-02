from orion.config.model_config import ModelConfig
from orion.models.contracts import ModelRequest, ModelResponse
from orion.models.gateway.gateway import ModelGateway
from orion.models.selection.selector import ModelSelector


class ModelRuntime:
    """Coordinates model selection and model execution."""

    def __init__(
        self,
        selector: ModelSelector,
    ) -> None:
        self._selector = selector

    def generate(
        self,
        config: ModelConfig,
        request: ModelRequest,
    ) -> ModelResponse:
        """Select a provider and execute a model request through ModelGateway."""
        provider = self._selector.select(config.provider_name)
        gateway = ModelGateway(
            provider=provider,
            max_response_chars=config.max_response_bytes,
        )

        configured_request = ModelRequest(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            metadata=request.metadata,
            structured_output=request.structured_output,
            response_format=request.response_format,
            request_id=request.request_id,
        )

        return gateway.generate(configured_request)

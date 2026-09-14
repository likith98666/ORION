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
        """Select a provider and execute a model request."""
        provider = self._selector.select(config.provider_name)
        gateway = ModelGateway(provider)

        configured_request = ModelRequest(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            metadata=request.metadata,
        )

        return gateway.generate(configured_request)
class ModelError(Exception):
    """Base exception for model-related failures."""


class ModelProviderError(ModelError):
    """Raised when a model provider fails."""


class ModelProviderUnavailableError(ModelProviderError):
    """Raised when a model provider is unavailable."""


class ModelRequestError(ModelError):
    """Raised when a model request is invalid."""


class ModelResponseError(ModelError):
    """Raised when a model returns an invalid response."""
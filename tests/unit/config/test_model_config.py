import pytest

from orion.config.model_config import ModelConfig


def test_model_config_uses_defaults() -> None:
    config = ModelConfig(provider_name="mock")

    assert config.provider_name == "mock"
    assert config.temperature == 0.0
    assert config.max_tokens is None


def test_model_config_accepts_custom_values() -> None:
    config = ModelConfig(
        provider_name="mock",
        temperature=0.7,
        max_tokens=500,
    )

    assert config.provider_name == "mock"
    assert config.temperature == 0.7
    assert config.max_tokens == 500


def test_model_config_rejects_empty_provider() -> None:
    with pytest.raises(
        ValueError,
        match="Provider name cannot be empty",
    ):
        ModelConfig(provider_name="   ")


def test_model_config_rejects_invalid_temperature() -> None:
    with pytest.raises(
        ValueError,
        match="Temperature must be between 0.0 and 2.0",
    ):
        ModelConfig(
            provider_name="mock",
            temperature=2.1,
        )


def test_model_config_rejects_invalid_max_tokens() -> None:
    with pytest.raises(
        ValueError,
        match="max_tokens must be greater than zero",
    ):
        ModelConfig(
            provider_name="mock",
            max_tokens=0,
        )


def test_model_config_masks_api_key_in_repr() -> None:
    config = ModelConfig(
        provider_name="openai",
        api_key="super-secret-sk-123456789",
    )
    repr_str = repr(config)
    assert "super-secret-sk-123456789" not in repr_str
    assert "[REDACTED]" in repr_str


def test_model_config_from_env() -> None:
    env = {
        "ORION_MODEL_PROVIDER": "openai",
        "ORION_MODEL_NAME": "gpt-4o-mini",
        "ORION_MODEL_BASE_URL": "https://custom.endpoint.com/v1",
        "ORION_MODEL_API_KEY": "sk-env-key-999",
        "ORION_MODEL_TIMEOUT": "45.0",
        "ORION_MODEL_TEMPERATURE": "0.3",
        "ORION_MODEL_MAX_TOKENS": "1024",
    }
    config = ModelConfig.from_env(env)
    assert config.provider_name == "openai"
    assert config.model_name == "gpt-4o-mini"
    assert config.base_url == "https://custom.endpoint.com/v1"
    assert config.api_key == "sk-env-key-999"
    assert config.timeout_seconds == 45.0
    assert config.temperature == 0.3
    assert config.max_tokens == 1024


def test_model_config_from_env_defaults() -> None:
    config = ModelConfig.from_env({})
    assert config.provider_name == "mock"
    assert config.model_name == "gpt-4o"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.api_key is None
    assert config.timeout_seconds == 30.0
    assert config.temperature == 0.0


def test_model_config_rejects_invalid_timeout_or_response_bytes() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be greater than zero"):
        ModelConfig(provider_name="mock", timeout_seconds=0.0)

    with pytest.raises(ValueError, match="max_response_bytes must be greater than zero"):
        ModelConfig(provider_name="mock", max_response_bytes=-1)

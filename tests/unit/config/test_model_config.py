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
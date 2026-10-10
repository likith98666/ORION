import pytest

from orion.core.security import (
    InMemorySecretProvider,
    SecretReference,
)


def test_secret_reference_is_immutable() -> None:
    reference = SecretReference("  github_token  ")

    assert reference.name == "github_token"

    with pytest.raises(AttributeError):
        reference.name = "other"


def test_secret_reference_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        SecretReference("   ")


def test_secret_provider_resolves_by_reference() -> None:
    provider = InMemorySecretProvider({"github_token": "super-secret-value"})

    result = provider.get(SecretReference("github_token"))

    assert result == "super-secret-value"


def test_secret_provider_rejects_unknown_reference() -> None:
    provider = InMemorySecretProvider()

    with pytest.raises(KeyError, match="was not found"):
        provider.get(SecretReference("missing"))


def test_secret_provider_rejects_invalid_reference_type() -> None:
    provider = InMemorySecretProvider({"github_token": "super-secret-value"})

    with pytest.raises(TypeError, match="SecretReference"):
        provider.get("github_token")

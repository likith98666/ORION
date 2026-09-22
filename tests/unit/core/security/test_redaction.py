from orion.core.security.redaction import REDACTED_VALUE, RedactionEngine
from orion.core.security.secrets import SecretReference


def test_redacts_exact_secret() -> None:
    engine = RedactionEngine(("super-secret",))

    assert engine.redact("super-secret") == REDACTED_VALUE


def test_redacts_secret_inside_string() -> None:
    engine = RedactionEngine(("super-secret",))

    result = engine.redact("Authorization: Bearer super-secret")

    assert result == f"Authorization: Bearer {REDACTED_VALUE}"
    assert "super-secret" not in result


def test_redacts_nested_dictionary() -> None:
    engine = RedactionEngine(("secret-value",))

    value = {
        "username": "agent",
        "credentials": {
            "token": "secret-value",
        },
    }

    result = engine.redact(value)

    assert result["username"] == "agent"
    assert result["credentials"]["token"] == REDACTED_VALUE


def test_redacts_nested_collections() -> None:
    engine = RedactionEngine(("secret-value",))

    value = [
        "safe",
        "secret-value",
        {"token": "secret-value"},
        ("secret-value",),
    ]

    result = engine.redact(value)

    assert result == [
        "safe",
        REDACTED_VALUE,
        {"token": REDACTED_VALUE},
        (REDACTED_VALUE,),
    ]


def test_redacts_secret_reference() -> None:
    engine = RedactionEngine()

    reference = SecretReference("API_KEY")

    assert engine.redact(reference) == REDACTED_VALUE


def test_preserves_non_secret_values() -> None:
    engine = RedactionEngine(("secret-value",))

    value = {
        "count": 42,
        "enabled": True,
        "missing": None,
    }

    assert engine.redact(value) == value


def test_register_adds_secret() -> None:
    engine = RedactionEngine()

    engine.register("new-secret")

    assert engine.redact("new-secret") == REDACTED_VALUE


def test_empty_secret_is_not_registered() -> None:
    engine = RedactionEngine(("",))

    assert engine.redact("ordinary text") == "ordinary text"


def test_longer_secrets_are_replaced_first() -> None:
    engine = RedactionEngine(("secret", "secret-value"))

    result = engine.redact("secret-value")

    assert result == REDACTED_VALUE


def test_redaction_does_not_mutate_input() -> None:
    engine = RedactionEngine(("secret-value",))

    value = {
        "token": "secret-value",
        "nested": ["secret-value"],
    }

    result = engine.redact(value)

    assert value["token"] == "secret-value"
    assert value["nested"] == ["secret-value"]
    assert result["token"] == REDACTED_VALUE

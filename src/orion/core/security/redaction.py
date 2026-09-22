from collections.abc import Mapping
from typing import Any

from orion.core.security.secrets import SecretReference

REDACTED_VALUE = "[REDACTED]"


class RedactionEngine:
    """Recursively removes known secret values from security-visible data."""

    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        self._secrets: set[str] = set()

        for secret in secrets:
            self.register(secret)

    def register(self, secret: str) -> None:
        """Register a concrete secret value for redaction."""
        if not isinstance(secret, str):
            raise TypeError("Secret value must be a string.")

        if secret:
            self._secrets.add(secret)

    def redact(self, value: Any) -> Any:
        """Return a recursively redacted copy of the supplied value."""
        if isinstance(value, SecretReference):
            return REDACTED_VALUE

        if isinstance(value, str):
            return self._redact_string(value)

        if isinstance(value, Mapping):
            return {
                key: self.redact(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self.redact(item) for item in value]

        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)

        if isinstance(value, set):
            return {self.redact(item) for item in value}

        return value

    def _redact_string(self, value: str) -> str:
        redacted = value

        for secret in sorted(self._secrets, key=len, reverse=True):
            redacted = redacted.replace(secret, REDACTED_VALUE)

        return redacted

from orion.core.security.secrets import SecretReference


class InMemorySecretProvider:
    """Test-oriented secret provider.

    Secrets remain inside the provider and are accessed only by reference.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    def get(self, reference: SecretReference) -> str:
        if not isinstance(reference, SecretReference):
            raise TypeError("reference must be a SecretReference.")

        try:
            return self._secrets[reference.name]
        except KeyError as exc:
            raise KeyError(
                f"Secret '{reference.name}' was not found."
            ) from exc

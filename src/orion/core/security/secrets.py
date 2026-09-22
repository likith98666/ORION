from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SecretReference:
    """Opaque reference to a secret stored outside agent-visible state."""

    name: str

    def __post_init__(self) -> None:
        cleaned_name = self.name.strip()

        if not cleaned_name:
            raise ValueError("Secret reference name cannot be empty.")

        object.__setattr__(self, "name", cleaned_name)


class SecretProvider(Protocol):
    """Controlled interface for resolving secrets at execution time."""

    def get(self, reference: SecretReference) -> str:
        """Resolve a secret without exposing storage details."""
        ...

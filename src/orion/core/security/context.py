from dataclasses import dataclass

from orion.core.security.trust import ContentTrustLevel


@dataclass(frozen=True)
class ModelContextSection:
    """A bounded section of model context with an explicit trust boundary."""

    content: str
    trust_level: ContentTrustLevel
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string.")

        if not self.content.strip():
            raise ValueError("content cannot be empty.")

        if not isinstance(self.trust_level, ContentTrustLevel):
            raise TypeError("trust_level must be a ContentTrustLevel.")

        if not isinstance(self.source, str):
            raise TypeError("source must be a string.")

        if not self.source.strip():
            raise ValueError("source cannot be empty.")

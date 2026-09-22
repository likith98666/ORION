import pytest

from orion.core.security.context import ModelContextSection
from orion.core.security.trust import ContentTrustLevel


def test_model_context_section_preserves_trust_boundary() -> None:
    section = ModelContextSection(
        content="Retrieved document content.",
        trust_level=ContentTrustLevel.UNTRUSTED,
        source="memory",
    )

    assert section.content == "Retrieved document content."
    assert section.trust_level == ContentTrustLevel.UNTRUSTED
    assert section.source == "memory"


def test_model_context_section_is_immutable() -> None:
    section = ModelContextSection(
        content="Reference data.",
        trust_level=ContentTrustLevel.UNTRUSTED,
        source="memory",
    )

    with pytest.raises(AttributeError):
        section.content = "Changed."


def test_model_context_section_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content cannot be empty"):
        ModelContextSection(
            content="   ",
            trust_level=ContentTrustLevel.UNTRUSTED,
            source="memory",
        )


def test_model_context_section_rejects_invalid_trust_level() -> None:
    with pytest.raises(TypeError, match="trust_level"):
        ModelContextSection(
            content="Reference data.",
            trust_level="untrusted",
            source="memory",
        )


def test_model_context_section_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="source cannot be empty"):
        ModelContextSection(
            content="Reference data.",
            trust_level=ContentTrustLevel.UNTRUSTED,
            source="   ",
        )

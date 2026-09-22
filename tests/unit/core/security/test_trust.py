from orion.core.security.trust import ContentTrustLevel


def test_content_trust_levels_are_explicit() -> None:
    assert ContentTrustLevel.TRUSTED.value == "trusted"
    assert ContentTrustLevel.UNTRUSTED.value == "untrusted"


def test_content_trust_levels_are_distinct() -> None:
    assert ContentTrustLevel.TRUSTED != ContentTrustLevel.UNTRUSTED

from enum import Enum


class ContentTrustLevel(str, Enum):
    """Trust classification for content entering ORION model contexts."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"

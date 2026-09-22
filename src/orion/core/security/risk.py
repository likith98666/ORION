from enum import IntEnum


class ToolRiskLevel(IntEnum):
    """Risk classification for actions performed by ORION tools."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

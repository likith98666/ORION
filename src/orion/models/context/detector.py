"""Advisory prompt-injection signal detector for ORION cognitive context.

IMPORTANT ARCHITECTURAL INVARIANT:
This detector provides ADVISORY signals for observability and telemetry ONLY.
The detector MUST NEVER BE THE SECURITY AUTHORITY.
Untrusted repository content is fenced as data regardless of detector output.
A 'clean' or 'none' detector result NEVER bypasses ORION authorization,
ToolExecutor, ApprovalService, or VerificationEngine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class InjectionRiskLevel(str, Enum):
    """Advisory risk classification of untrusted content."""

    NONE = "none"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "high_risk"


@dataclass(frozen=True)
class InjectionSignal:
    """Advisory diagnostic signal capturing potential prompt injection indicators."""

    risk_level: InjectionRiskLevel
    reasons: tuple[str, ...] = ()
    matched_patterns: tuple[str, ...] = ()

    @property
    def is_flagged(self) -> bool:
        """Return True if any suspicious or high-risk signal was detected."""
        return self.risk_level != InjectionRiskLevel.NONE


# Patterns indicative of high-risk prompt injection (instruction override / prompt extraction)
HIGH_RISK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions?",
            re.IGNORECASE,
        ),
        "Instruction override: attempt to ignore prior instructions",
    ),
    (
        re.compile(
            r"disregard\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions?",
            re.IGNORECASE,
        ),
        "Instruction override: attempt to disregard prior instructions",
    ),
    (
        re.compile(
            r"(reveal|print|show|output|leak|display)\s+(your\s+)?(system\s+)?(prompt|instructions)",
            re.IGNORECASE,
        ),
        "System prompt extraction: attempt to reveal system instructions",
    ),
    (
        re.compile(
            r"(you\s+are\s+now|new\s+role|act\s+as\s+an?\s+unrestricted)\s+",
            re.IGNORECASE,
        ),
        "Role hijacking: attempt to redefine model persona or constraints",
    ),
    (
        re.compile(
            r"(treat\s+this\s+(file|message|text)\s+as\s+(the\s+)?(new\s+)?system\s+(message|prompt))",
            re.IGNORECASE,
        ),
        "System instruction elevation: attempt to promote data to system message",
    ),
    (
        re.compile(
            r"(bypass|override|disable)\s+(all\s+)?(security|guardrails|safety|verification)",
            re.IGNORECASE,
        ),
        "Security bypass: attempt to disable safety or verification controls",
    ),
)

# Patterns indicative of suspicious instruction-like language in passive data
SUSPICIOUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"system\s*override", re.IGNORECASE),
        "Suspicious keyword: system override",
    ),
    (
        re.compile(r"send\s+(the\s+)?(api[_\s]?key|secret|token|password)\s+to", re.IGNORECASE),
        "Exfiltration pattern: directive to transmit credentials",
    ),
    (
        re.compile(r"delete\s+(all\s+)?(files|repository|workspace|database)", re.IGNORECASE),
        "Destructive directive: command to delete workspace assets",
    ),
    (
        re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]", re.IGNORECASE),
        "Special token injection: attempt to inject LLM chat delimiter tokens",
    ),
)


class PromptInjectionDetector:
    """Advisory prompt injection scanner for untrusted repository and execution content."""

    def analyze(self, text: str) -> InjectionSignal:
        """Scan text and produce an advisory InjectionSignal.

        NOTE: This does NOT filter or modify text. It provides visibility into
        adversarial patterns without corrupting legitimate source code or tests.
        """
        if not text or not text.strip():
            return InjectionSignal(risk_level=InjectionRiskLevel.NONE)

        reasons: list[str] = []
        matched: list[str] = []
        risk = InjectionRiskLevel.NONE

        for pattern, reason in HIGH_RISK_PATTERNS:
            if pattern.search(text):
                risk = InjectionRiskLevel.HIGH_RISK
                reasons.append(reason)
                matched.append(pattern.pattern)

        for pattern, reason in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                if risk != InjectionRiskLevel.HIGH_RISK:
                    risk = InjectionRiskLevel.SUSPICIOUS
                reasons.append(reason)
                matched.append(pattern.pattern)

        return InjectionSignal(
            risk_level=risk,
            reasons=tuple(reasons),
            matched_patterns=tuple(matched),
        )

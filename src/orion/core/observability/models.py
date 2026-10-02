from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SpanKind(str, Enum):
    """Semantic category of a distributed execution span."""

    INTERNAL = "internal"
    CLIENT = "client"
    SERVER = "server"
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"


class SpanStatus(str, Enum):
    """Terminal outcome of a span."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class InsightSeverity(str, Enum):
    """Severity level of an optimization recommendation."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SpanEvent:
    """In-span timestamped event or annotation."""

    name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class SpanRecord:
    """Detailed record of a single distributed execution span."""

    name: str
    trace_id: UUID = field(default_factory=uuid4)
    span_id: UUID = field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.OK
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    duration_ms: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)

    def end(self, status: SpanStatus = SpanStatus.OK) -> None:
        """Mark span as ended and calculate duration."""
        if self.end_time is None:
            self.end_time = datetime.now(UTC)
            self.duration_ms = max(
                0.0,
                (self.end_time - self.start_time).total_seconds() * 1000.0,
            )
        self.status = status

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": str(self.trace_id),
            "span_id": str(self.span_id),
            "parent_span_id": str(self.parent_span_id) if self.parent_span_id else None,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass(frozen=True)
class OptimizationInsight:
    """Actionable performance, token, or cost optimization recommendation."""

    category: str
    title: str
    description: str
    severity: InsightSeverity
    target_component: str
    recommendation: str
    potential_savings: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "target_component": self.target_component,
            "recommendation": self.recommendation,
            "potential_savings": self.potential_savings,
        }

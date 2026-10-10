from __future__ import annotations

import contextvars
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

from orion.core.observability.models import (
    SpanKind,
    SpanRecord,
    SpanStatus,
)

_current_span_var: contextvars.ContextVar[SpanRecord | None] = contextvars.ContextVar(
    "current_span", default=None
)


class DistributedTracer:
    """Thread-safe distributed tracer supporting nested span tracking."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._spans: list[SpanRecord] = []

    def record_span(self, span: SpanRecord) -> None:
        """Store a completed span record."""
        with self._lock:
            self._spans.append(span)
            if len(self._spans) > 5000:
                self._spans = self._spans[-5000:]

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        trace_id: UUID | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[SpanRecord]:
        """Context manager creating a new span linked to the current trace hierarchy."""
        parent = _current_span_var.get()
        active_trace_id = trace_id or (parent.trace_id if parent else uuid4())
        parent_id = parent.span_id if parent else None

        span = SpanRecord(
            name=name,
            trace_id=active_trace_id,
            span_id=uuid4(),
            parent_span_id=parent_id,
            kind=kind,
            attributes=attributes or {},
        )

        token = _current_span_var.set(span)
        try:
            yield span
            span.end(status=SpanStatus.OK)
        except Exception as exc:
            span.add_event("exception", {"error": str(exc), "type": type(exc).__name__})
            span.end(status=SpanStatus.ERROR)
            raise
        finally:
            _current_span_var.reset(token)
            self.record_span(span)

    def get_trace(self, trace_id: UUID) -> list[SpanRecord]:
        """Retrieve all spans belonging to a trace, sorted by start time."""
        with self._lock:
            return sorted(
                [s for s in self._spans if s.trace_id == trace_id],
                key=lambda s: s.start_time,
            )

    def get_mission_spans(self, mission_id: UUID) -> list[SpanRecord]:
        """Retrieve spans associated with a mission ID in attributes or trace."""
        mid_str = str(mission_id)
        with self._lock:
            return sorted(
                [
                    s
                    for s in self._spans
                    if str(s.trace_id) == mid_str or s.attributes.get("mission_id") == mid_str
                ],
                key=lambda s: s.start_time,
            )

    def list_spans(self, limit: int = 200) -> list[SpanRecord]:
        """List most recent spans."""
        with self._lock:
            return list(self._spans[-limit:])

    def clear(self) -> None:
        """Clear all stored spans."""
        with self._lock:
            self._spans.clear()

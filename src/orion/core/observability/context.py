from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TelemetryContext:
    request_id: UUID | None = None
    trace_id: UUID | None = None
    span_id: UUID | None = None
    parent_span_id: UUID | None = None
    task_id: UUID | None = None
    execution_id: UUID | None = None
    agent_id: UUID | None = None
    tool_id: UUID | None = None

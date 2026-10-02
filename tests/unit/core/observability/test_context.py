from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from orion.core.observability.context import TelemetryContext


def test_telemetry_context_defaults_to_empty() -> None:
    context = TelemetryContext()

    assert context.request_id is None
    assert context.trace_id is None
    assert context.span_id is None
    assert context.parent_span_id is None
    assert context.task_id is None
    assert context.execution_id is None
    assert context.agent_id is None
    assert context.tool_id is None


def test_telemetry_context_preserves_correlation_ids() -> None:
    request_id = uuid4()
    trace_id = uuid4()
    span_id = uuid4()
    parent_span_id = uuid4()
    task_id = uuid4()
    execution_id = uuid4()
    agent_id = uuid4()
    tool_id = uuid4()

    context = TelemetryContext(
        request_id=request_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        task_id=task_id,
        execution_id=execution_id,
        agent_id=agent_id,
        tool_id=tool_id,
    )

    assert context.request_id == request_id
    assert context.trace_id == trace_id
    assert context.span_id == span_id
    assert context.parent_span_id == parent_span_id
    assert context.task_id == task_id
    assert context.execution_id == execution_id
    assert context.agent_id == agent_id
    assert context.tool_id == tool_id


def test_telemetry_context_is_immutable() -> None:
    context = TelemetryContext(task_id=uuid4())

    with pytest.raises(FrozenInstanceError):
        context.task_id = uuid4()  # type: ignore[misc]

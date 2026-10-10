import http.client
import json
import threading
import time
from typing import Any
from uuid import uuid4

import pytest

from orion.api.server import create_server
from orion.api.service import MissionAPIService
from orion.core.observability import (
    DistributedTracer,
    InsightSeverity,
    SpanKind,
    SpanRecord,
    SpanStatus,
    SystemOptimizer,
)


def test_span_record_lifecycle() -> None:
    """Validate span creation, events, completion, and duration calculation."""
    span = SpanRecord(
        name="test_span",
        kind=SpanKind.AGENT,
    )
    span.add_event("agent_started", {"role": "planner"})
    time.sleep(0.01)
    span.end(status=SpanStatus.OK)

    assert span.status == SpanStatus.OK
    assert span.duration_ms > 0
    assert len(span.events) == 1
    assert span.events[0].name == "agent_started"

    data = span.to_dict()
    assert data["name"] == "test_span"
    assert data["kind"] == "agent"
    assert data["status"] == "ok"
    assert data["duration_ms"] > 0


def test_distributed_tracer_hierarchical_spans() -> None:
    """Validate that nested spans correctly inherit trace_id and parent_span_id."""
    tracer = DistributedTracer()

    with tracer.start_as_current_span("root_orchestration", kind=SpanKind.SERVER):
        with tracer.start_as_current_span("planner_agent", kind=SpanKind.AGENT):
            with tracer.start_as_current_span("llm_reasoning", kind=SpanKind.LLM):
                time.sleep(0.005)

    spans = tracer.list_spans(limit=10)
    assert len(spans) == 3

    # Reverse order in list: inner child ends first
    s_llm = [s for s in spans if s.name == "llm_reasoning"][0]
    s_planner = [s for s in spans if s.name == "planner_agent"][0]
    s_root = [s for s in spans if s.name == "root_orchestration"][0]

    assert s_llm.trace_id == s_planner.trace_id == s_root.trace_id
    assert s_llm.parent_span_id == s_planner.span_id
    assert s_planner.parent_span_id == s_root.span_id
    assert s_root.parent_span_id is None


def test_distributed_tracer_exception_handling() -> None:
    """Validate that exceptions mark span status as ERROR and record exception event."""
    tracer = DistributedTracer()

    with pytest.raises(RuntimeError, match="Simulated tool failure"):
        with tracer.start_as_current_span("failing_tool", kind=SpanKind.TOOL):
            raise RuntimeError("Simulated tool failure")

    spans = tracer.list_spans(limit=1)
    assert len(spans) == 1
    failed_span = spans[0]
    assert failed_span.status == SpanStatus.ERROR
    assert len(failed_span.events) == 1
    assert failed_span.events[0].name == "exception"
    assert "Simulated tool failure" in failed_span.events[0].attributes["error"]


def test_system_optimizer_cost_metrics() -> None:
    """Validate token and cost aggregation by component."""
    tracer = DistributedTracer()
    mission_id = uuid4()

    # Record 2 LLM spans
    s1 = SpanRecord(
        name="gemini_planner",
        attributes={
            "mission_id": str(mission_id),
            "component": "planner",
            "input_tokens": 1200,
            "output_tokens": 400,
            "cost_usd": 0.0032,
        },
    )
    s2 = SpanRecord(
        name="gemini_coder",
        attributes={
            "mission_id": str(mission_id),
            "component": "coder",
            "input_tokens": 2500,
            "output_tokens": 1100,
            "cost_usd": 0.0072,
        },
    )
    tracer.record_span(s1)
    tracer.record_span(s2)

    optimizer = SystemOptimizer(tracer)
    metrics = optimizer.calculate_cost_metrics(mission_id=mission_id)

    assert metrics["total_input_tokens"] == 3700
    assert metrics["total_output_tokens"] == 1500
    assert metrics["total_tokens"] == 5200
    assert round(metrics["total_cost_usd"], 4) == 0.0104
    assert "planner" in metrics["by_component"]
    assert "coder" in metrics["by_component"]


def test_system_optimizer_bottlenecks_and_quantiles() -> None:
    """Validate latency summary statistics and top slowest span detection."""
    tracer = DistributedTracer()
    mission_id = uuid4()

    for idx, duration in enumerate([10.0, 20.0, 50.0, 100.0, 500.0]):
        span = SpanRecord(
            name=f"task_step_{idx}",
            attributes={"mission_id": str(mission_id)},
            duration_ms=duration,
        )
        tracer.record_span(span)

    optimizer = SystemOptimizer(tracer)
    bottlenecks = optimizer.analyze_bottlenecks(mission_id=mission_id, top_n=2)

    assert bottlenecks["total_spans"] == 5
    assert bottlenecks["error_rate"] == 0.0
    summary = bottlenecks["latency_summary"]
    assert summary["min_ms"] == 10.0
    assert summary["max_ms"] == 500.0
    assert summary["avg_ms"] == 136.0
    assert len(bottlenecks["slowest_spans"]) == 2
    assert bottlenecks["slowest_spans"][0]["duration_ms"] == 500.0


def test_system_optimizer_recommendations() -> None:
    """Validate proactive optimization insight generation for caching and latency."""
    tracer = DistributedTracer()
    mission_id = uuid4()

    # 1. 3 identical tool calls (caching candidate)
    for _ in range(3):
        span = SpanRecord(
            name="read_workspace_file",
            kind=SpanKind.TOOL,
            attributes={"mission_id": str(mission_id)},
            duration_ms=10.0,
        )
        tracer.record_span(span)

    # 2. 1 very slow span (>40% of duration)
    slow_span = SpanRecord(
        name="exhaustive_full_repo_ast_parse",
        kind=SpanKind.INTERNAL,
        attributes={"mission_id": str(mission_id)},
        duration_ms=200.0,
    )
    tracer.record_span(slow_span)

    optimizer = SystemOptimizer(tracer)
    recommendations = optimizer.generate_recommendations(mission_id=mission_id)

    assert len(recommendations) >= 2
    categories = [r.category for r in recommendations]
    assert "caching" in categories
    assert "latency" in categories

    caching_rec = [r for r in recommendations if r.category == "caching"][0]
    assert caching_rec.severity == InsightSeverity.INFO
    assert "read_workspace_file" in caching_rec.target_component


# -------------------------------------------------------------------------
# Integration / REST API Verification for Advanced Observability
# -------------------------------------------------------------------------


@pytest.fixture
def obs_api_server() -> Any:
    service = MissionAPIService()
    server = create_server("127.0.0.1", 0, service=service)
    host, port = server.server_address
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield host, port, service
    server.shutdown()
    server.server_close()


def _request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    conn = http.client.HTTPConnection(host, port, timeout=10)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    payload = json.dumps(body) if body is not None else None
    conn.request(method, path, body=payload, headers=headers)
    resp = conn.getresponse()
    status = resp.status
    data = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return status, data


def test_api_observability_endpoints(obs_api_server: Any) -> None:
    """Test observability REST endpoints: span ingestion, query, cost, bottlenecks, optimize."""
    host, port, _ = obs_api_server
    mission_id = str(uuid4())

    # 1. POST /api/v1/observability/spans (ingest 3 spans)
    for i in range(3):
        payload = {
            "name": f"subagent_step_{i}",
            "kind": "tool" if i == 0 else "agent",
            "status": "ok",
            "duration_ms": 25.0 * (i + 1),
            "attributes": {
                "mission_id": mission_id,
                "component": f"worker_{i}",
                "input_tokens": 500,
                "output_tokens": 150,
                "cost_usd": 0.0015,
            },
        }
        status, data = _request_json(host, port, "POST", "/api/v1/observability/spans", payload)
        assert status == 201
        assert data["name"] == f"subagent_step_{i}"

    # 2. GET /api/v1/observability/spans/{mission_id}
    status, spans_resp = _request_json(
        host, port, "GET", f"/api/v1/observability/spans/{mission_id}"
    )
    assert status == 200
    assert spans_resp["total"] == 3

    # 3. GET /api/v1/observability/metrics/cost
    status, cost_resp = _request_json(
        host, port, "GET", f"/api/v1/observability/metrics/cost?mission_id={mission_id}"
    )
    assert status == 200
    assert cost_resp["total_tokens"] == (500 + 150) * 3
    assert cost_resp["total_cost_usd"] > 0

    # 4. GET /api/v1/observability/bottlenecks
    status, bneck_resp = _request_json(
        host, port, "GET", f"/api/v1/observability/bottlenecks?mission_id={mission_id}&top_n=2"
    )
    assert status == 200
    assert bneck_resp["total_spans"] == 3
    assert len(bneck_resp["slowest_spans"]) == 2

    # 5. GET /api/v1/observability/optimize
    status, opt_resp = _request_json(
        host, port, "GET", f"/api/v1/observability/optimize?mission_id={mission_id}"
    )
    assert status == 200
    assert "recommendations" in opt_resp

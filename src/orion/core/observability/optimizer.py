from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from orion.core.observability.models import (
    InsightSeverity,
    OptimizationInsight,
    SpanKind,
    SpanStatus,
)
from orion.core.observability.tracer import DistributedTracer


class SystemOptimizer:
    """Telemetry analyzer and system optimizer discovering bottlenecks and savings."""

    def __init__(self, tracer: DistributedTracer) -> None:
        self._tracer = tracer

    def calculate_cost_metrics(
        self,
        mission_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Aggregate token usage and cost metrics across spans."""
        spans = (
            self._tracer.get_mission_spans(mission_id)
            if mission_id
            else self._tracer.list_spans(limit=1000)
        )

        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        by_component: dict[str, dict[str, Any]] = {}

        for span in spans:
            in_tok = int(span.attributes.get("input_tokens", 0))
            out_tok = int(span.attributes.get("output_tokens", 0))
            cost = float(span.attributes.get("cost_usd", 0.0))

            if in_tok == 0 and out_tok == 0 and cost == 0.0:
                continue

            total_input_tokens += in_tok
            total_output_tokens += out_tok
            total_cost_usd += cost

            comp = span.attributes.get("component") or span.name
            if comp not in by_component:
                by_component[comp] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            by_component[comp]["input_tokens"] += in_tok
            by_component[comp]["output_tokens"] += out_tok
            by_component[comp]["total_tokens"] += in_tok + out_tok
            by_component[comp]["cost_usd"] += cost
            by_component[comp]["calls"] += 1

        return {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "by_component": by_component,
        }

    def analyze_bottlenecks(
        self,
        mission_id: UUID | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Identify slowest execution spans, error rates, and latency quantiles."""
        spans = (
            self._tracer.get_mission_spans(mission_id)
            if mission_id
            else self._tracer.list_spans(limit=1000)
        )

        if not spans:
            return {
                "total_spans": 0,
                "slowest_spans": [],
                "error_rate": 0.0,
                "latency_summary": {},
            }

        durations = sorted([s.duration_ms for s in spans])
        error_count = sum(1 for s in spans if s.status == SpanStatus.ERROR)
        error_rate = error_count / len(spans)

        p50 = durations[int(len(durations) * 0.50)]
        p90 = durations[min(int(len(durations) * 0.90), len(durations) - 1)]
        p99 = durations[min(int(len(durations) * 0.99), len(durations) - 1)]

        slowest = sorted(spans, key=lambda s: s.duration_ms, reverse=True)[:top_n]

        return {
            "total_spans": len(spans),
            "error_rate": round(error_rate, 4),
            "latency_summary": {
                "min_ms": round(durations[0], 2),
                "max_ms": round(durations[-1], 2),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "p50_ms": round(p50, 2),
                "p90_ms": round(p90, 2),
                "p99_ms": round(p99, 2),
            },
            "slowest_spans": [s.to_dict() for s in slowest],
        }

    def generate_recommendations(
        self,
        mission_id: UUID | None = None,
    ) -> list[OptimizationInsight]:
        """Generate actionable performance, token, and architecture recommendations."""
        spans = (
            self._tracer.get_mission_spans(mission_id)
            if mission_id
            else self._tracer.list_spans(limit=1000)
        )

        insights: list[OptimizationInsight] = []
        if not spans:
            return insights

        total_duration = sum(s.duration_ms for s in spans)

        # 1. Repetitive tool calls check (caching opportunity)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL]
        call_counts = Counter(s.name for s in tool_spans)
        for tool_name, count in call_counts.items():
            if count >= 3:
                insights.append(
                    OptimizationInsight(
                        category="caching",
                        title=f"Repeated Tool Invocations for '{tool_name}'",
                        description=(
                            f"Tool '{tool_name}' was executed {count} times during this run."
                        ),
                        severity=InsightSeverity.INFO,
                        target_component=tool_name,
                        recommendation=(
                            "Enable deterministic result caching or memoization to reduce "
                            "redundant IO and tool latency."
                        ),
                        potential_savings=f"Up to {(count - 1) * 20}% latency reduction",
                    )
                )

        # 2. Long-tail latency bottleneck
        for span in spans:
            if total_duration > 0 and (span.duration_ms / total_duration) > 0.4:
                insights.append(
                    OptimizationInsight(
                        category="latency",
                        title=f"Dominant Execution Bottleneck in '{span.name}'",
                        description=(
                            f"Span '{span.name}' consumed "
                            f"{round((span.duration_ms / total_duration) * 100, 1)}% "
                            f"({round(span.duration_ms, 1)}ms) of total recorded mission execution."
                        ),
                        severity=InsightSeverity.WARNING,
                        target_component=span.name,
                        recommendation=(
                            "Profile internal operations of this span, break down into "
                            "asynchronous parallel sub-tasks, or optimize underlying "
                            "prompts and IO."
                        ),
                        potential_savings="30-50% mission wall-clock speedup",
                    )
                )

        # 3. High failure / error rate
        failed_spans = [s for s in spans if s.status == SpanStatus.ERROR]
        if failed_spans:
            fail_comp_counts = Counter(s.name for s in failed_spans)
            top_failing, top_fail_count = fail_comp_counts.most_common(1)[0]
            insights.append(
                OptimizationInsight(
                    category="reliability",
                    title=f"Elevated Failure Rate in '{top_failing}'",
                    description=(
                        f"Detected {top_fail_count} span failure(s) in component '{top_failing}'."
                    ),
                    severity=InsightSeverity.CRITICAL,
                    target_component=top_failing,
                    recommendation=(
                        "Inspect span error events for root cause. Ensure input validation, "
                        "pre-execution guardrails, or targeted recovery strategies are configured."
                    ),
                )
            )

        # 4. Token concentration
        cost_metrics = self.calculate_cost_metrics(mission_id)
        if cost_metrics["total_tokens"] > 50000:
            insights.append(
                OptimizationInsight(
                    category="cost",
                    title="High Token Volume Detected",
                    description=(
                        f"Mission consumed {cost_metrics['total_tokens']:,} total tokens."
                    ),
                    severity=InsightSeverity.WARNING,
                    target_component="llm_orchestrator",
                    recommendation=(
                        "Employ prompt pruning, context summarization, or routing of routine tasks "
                        "to Gemini 1.5 Flash models."
                    ),
                    potential_savings="Up to 60% token cost reduction",
                )
            )

        return insights

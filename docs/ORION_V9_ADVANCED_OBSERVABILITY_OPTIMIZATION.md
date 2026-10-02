# ORION V9 — Advanced Observability, Distributed Telemetry & System Optimization

## 1. Overview and Architecture

ORION V9 implements full distributed tracing, granular token and cost accounting, and self-optimizing telemetry as specified in:
* `docs/09_observability_architecture.md`
* `docs/47_performance_architecture.md`
* `docs/48_reliability_architecture.md`

In complex, long-running autonomous missions involving hierarchical agents, asynchronous queues, dynamic tool calls, and self-healing recovery loops, understanding system behavior requires deep contextual observability across the three pillars: **Logs**, **Metrics**, and **Traces**.

```text
       Incoming Mission / Task Execution
                      ↓
       DistributedTracer (Contextvars & UUID Trace)
 ┌────────────────────────────────────────────────────────┐
 │ Root Orchestration Span (Server)                       │
 │  ├── Planner Agent Span (Agent)                        │
 │  │    └── LLM Reasoning & Prompt Span (LLM)            │
 │  ├── SWE Code Graph Span (Internal)                    │
 │  ├── Tool Execution Spans (Tool)                       │
 │  │    ├── read_file, git_status, terminal_exec         │
 │  └── Verification & Self-Healing Recovery Spans        │
 └────────────────────────────────────────────────────────┘
                      ↓
      Span Telemetry & Token/Cost Ingestion
                      ↓
          SystemOptimizer Analyzer
 ┌────────────────────────────────────────────────────────┐
 │ - Latency Breakdown & Quantiles (p50, p90, p99)        │
 │ - Token & Cost Attribution by Agent & Model            │
 │ - Bottleneck Detection (>40% total mission wall-time)  │
 │ - Tool Repetition & Caching Opportunities              │
 │ - Component Failure & Reliability Hotspots             │
 └────────────────────────────────────────────────────────┘
                      ↓
        Actionable Optimization Insights
```

---

## 2. Distributed Tracing Engine (`DistributedTracer`)

### 2.1 Span Hierarchy & Context Propagation
* **Contextvar Integration**: Nested `start_as_current_span(...)` context managers automatically link `parent_span_id` and maintain `trace_id` continuity across subagent calls without manual ID plumbing.
* **Semantic Span Kinds**:
  * `SERVER`: Top-level HTTP and orchestrator boundaries.
  * `AGENT`: High-level agent lifecycle (e.g. planner, coder, reviewer).
  * `TOOL`: Tool invocations (e.g. repo search, file modification, tests).
  * `LLM`: Frontier and reasoning model generations.
  * `INTERNAL`: Algorithms, AST parsing, and graph indexing.
* **Resilient Exception Recording**: Exceptions automatically transition spans to `SpanStatus.ERROR` and record structured exception event metadata with error types and stack snippets.

---

## 3. System Optimizer & Telemetry Analytics (`SystemOptimizer`)

### 3.1 Token & Cost Attribution
Aggregates input, output, and total token counts and USD expenditure across each component, agent, and tool, enabling exact unit economics for autonomous missions.

### 3.2 Latency Breakdown & Quantiles
Computes min, max, avg, p50, p90, and p99 duration percentiles and surfaces the top-N slowest execution spans to direct engineering focus to critical-path bottlenecks.

### 3.3 Automated Optimization Recommendations (`OptimizationInsight`)
* **Caching Candidates**: Discovers repeated identical tool calls ($\ge 3$) and recommends memoization or workspace caching.
* **Long-Tail Latency Hotspots**: Discovers spans consuming $> 40\%$ of total mission wall-clock time and recommends asynchronous parallelization or prompt tuning.
* **Reliability Hotspots**: Flags components with elevated failure rates for targeted pre-flight verification or self-healing strategies.
* **Cost Pruning**: Detects excessive token volume and suggests routing routine tasks to lightweight fast models.

---

## 4. REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/observability/spans/{mission_id}` | `GET` | Retrieves all distributed execution spans recorded for a mission. |
| `/api/v1/observability/spans` | `POST` | Ingests an execution span record with durations, token attributes, and events. |
| `/api/v1/observability/metrics/cost` | `GET` | Retrieves aggregated token volumes and cost breakdown by component. |
| `/api/v1/observability/bottlenecks` | `GET` | Analyzes slowest spans, error rates, and latency quantiles (p50, p90, p99). |
| `/api/v1/observability/optimize` | `GET` | Generates actionable optimization insights and potential efficiency savings. |

---

## 5. Verification Metrics

* Dedicated Observability Test Suite: 7 tests passed in 1.32s.
* Static Type Checking: `mypy src` clean across 234 source files.
* Linter: `ruff check .` clean with 0 warnings or errors.

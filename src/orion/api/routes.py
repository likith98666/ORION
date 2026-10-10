"""Authoritative Route Registry and Documentation Generator for ORION REST API.

Defines all 61 REST API endpoints and static assets served by OrionAPIHandler,
enforcing strict contract parity between router implementations and docs/API.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDoc:
    """Specification of an ORION API endpoint."""

    method: str
    path: str
    summary: str
    description: str
    request_body: str | None
    response_body: str
    status_codes: tuple[int, ...]
    tag: str


ROUTE_REGISTRY: tuple[RouteDoc, ...] = (
    # =========================================================================
    # 1. System & Health Probes (2 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/health",
        summary="System Health Probe",
        description="Returns system operational status, version, uptime, and active mission count.",
        request_body=None,
        response_body='{"status": "healthy", "version": "1.0.0", "uptime_seconds": 12.3, "missions_count": 0}',  # noqa: E501
        status_codes=(200,),
        tag="System",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/readiness",
        summary="Service Readiness Probe",
        description="Checks filesystem containment, workspace validity, and tool executor availability.",  # noqa: E501
        request_body=None,
        response_body='{"status": "ready", "checks": {"workspace": true, "tools": true}}',
        status_codes=(200, 503),
        tag="System",
    ),
    # =========================================================================
    # 2. Missions & Lifecycle (18 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/missions",
        summary="List Missions",
        description="Returns all active, historical, and completed autonomous software engineering missions.",  # noqa: E501
        request_body=None,
        response_body='{"missions": [...], "tasks": [...], "total": 1}',
        status_codes=(200, 401),
        tag="Missions",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions",
        summary="Initialize Mission",
        description="Submits an autonomous engineering directive, creates a mission record, and bounds workspace.",  # noqa: E501
        request_body='{"task": "Fix bug", "workspace": "/path/to/repo", "execution_mode": "controlled"}',  # noqa: E501
        response_body='{"mission_id": "uuid", "task_id": "uuid", "status": "initialized", "lifecycle_state": "RECEIVED"}',  # noqa: E501
        status_codes=(201, 400, 401, 422, 429),
        tag="Missions",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/plan",
        summary="Plan Mission Decomposition",
        description="Decomposes high-level objective into deterministic 7-stage task graph and resource budget.",  # noqa: E501
        request_body='{"objective": "Implement feature", "max_duration_seconds": 300.0}',
        response_body='{"plan_id": "uuid", "stages": [...], "budget": {...}}',
        status_codes=(201, 400, 401),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}",
        summary="Get Mission Details",
        description="Retrieves current execution state, active stage, and telemetry for a specific mission.",  # noqa: E501
        request_body=None,
        response_body='{"mission_id": "uuid", "status": "running_inspect_repository", "lifecycle_state": "INSPECT_REPOSITORY"}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/events",
        summary="Mission Event Stream (SSE)",
        description="Real-time Server-Sent Events (SSE) telemetry stream publishing chronological mission events.",  # noqa: E501
        request_body=None,
        response_body="text/event-stream (event: CONNECTED, STAGE_STARTED, etc.)",
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/execution",
        summary="Get Task Execution Details",
        description="Returns low-level task execution state, stage details, and execution identifiers.",  # noqa: E501
        request_body=None,
        response_body='{"execution_id": "uuid", "status": "running", "current_stage": "inspect_repository"}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/timeline",
        summary="Get Mission Timeline",
        description="Returns chronological sequence of recorded events for mission replay and timeline scrubber.",  # noqa: E501
        request_body=None,
        response_body='{"timeline": [{"event_id": "uuid", "stage": "...", "title": "...", "timestamp": "..."}]}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/evidence",
        summary="Get Forensic Evidence Ledger",
        description="Returns evidence ledger items filtered by level (CLAIMED, OBSERVED, VERIFIED) and category.",  # noqa: E501
        request_body=None,
        response_body='{"evidence": [{"id": "uuid", "level": "VERIFIED", "category": "TEST_RESULT", ...}]}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/changes",
        summary="Get Code Changes & Diffs",
        description="Returns unified git diffs, modified file paths, and patch operation statistics.",  # noqa: E501
        request_body=None,
        response_body='{"diff": "--- a/file.py\\n+++ b/file.py...", "files_modified": 1, "lines_added": 2, "lines_removed": 1}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/tests",
        summary="Get Test Execution Logs",
        description="Returns sandboxed pytest test results, selected target scopes, and execution logs.",  # noqa: E501
        request_body=None,
        response_body='{"exit_code": 0, "stdout": "1 passed...", "targets": ["tests/unit/test_fix.py"]}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/recovery",
        summary="Get Self-Healing Recovery State",
        description="Returns recovery attempts, active strategy (RETRY_TASK, CHANGE_MODEL), and budget bars.",  # noqa: E501
        request_body=None,
        response_body='{"recovery_attempts": 0, "failure_category": "NONE", "strategy": "RETRY_TASK"}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/verification",
        summary="Get Authoritative Verification",
        description="Returns ground-truth verification verdict, test suite pass status, and integrity checks.",  # noqa: E501
        request_body=None,
        response_body='{"is_verified": true, "verification_passed": true, "ground_truth": "PASS"}',
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/evaluation",
        summary="Get Evaluation Scorecard",
        description="Returns evaluation metrics, criteria outcomes, and quality scorecards for the mission.",  # noqa: E501
        request_body=None,
        response_body='{"status": "PASS", "tests_passed": 1, "tests_failed": 0, "verification_passed": true}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/report",
        summary="Get Certified Final Report",
        description="Returns structured cryptographic software engineering report with full audit trail.",  # noqa: E501
        request_body=None,
        response_body='{"report_id": "uuid", "status": "verified_success", "summary": "...", "evidence": [...]}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/agents",
        summary="Get Mission Workforce Telemetry",
        description="Returns specialized agent roster, assignments, and telemetry for the specified mission.",  # noqa: E501
        request_body=None,
        response_body='{"roster": [{"name": "Orion-SWE-Engineer", "status": "active", ...}]}',
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/graph",
        summary="Get DAG Execution Graph",
        description="Returns deterministic 7-stage DAG topology nodes and monotonic execution states.",  # noqa: E501
        request_body=None,
        response_body='{"nodes": [{"id": "inspect_repository", "status": "COMPLETED", ...}], "edges": [...]}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/missions/{id}/memory",
        summary="Get Mission Memory Context",
        description="Returns episodic memories, semantic search results, and repository context snapshots.",  # noqa: E501
        request_body=None,
        response_body='{"memory": {"episodes": [...], "working_context": {...}}}',
        status_codes=(200, 401, 404),
        tag="Missions",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/run",
        summary="Execute Pipeline",
        description="Triggers automated sequential progression through all uncompleted engineering stages.",  # noqa: E501
        request_body='{"auto_approve": false, "background": true}',
        response_body='{"status": "executing", "mission_id": "uuid", "message": "Pipeline execution initiated."}',  # noqa: E501
        status_codes=(202, 401, 404, 422),
        tag="Missions",
    ),
    # =========================================================================
    # 3. Stage Execution & Human Oversight (6 endpoints)
    # =========================================================================
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/advance",
        summary="Advance Execution Stage",
        description="Transitions mission execution to the specified target stage if valid.",
        request_body='{"stage": "inspect_repository"}',
        response_body='{"mission_id": "uuid", "status": "running_inspect_repository"}',
        status_codes=(200, 400, 401, 404, 422),
        tag="Execution",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/tool",
        summary="Execute Sandboxed Tool",
        description="Executes a capability tool within stage permissions and sandboxed workspace boundaries.",  # noqa: E501
        request_body='{"stage": "inspect_repository", "tool_name": "list_files", "arguments": {}}',
        response_body='{"success": true, "tool_name": "list_files", "output": [...], "error": null}',  # noqa: E501
        status_codes=(200, 400, 401, 404, 422),
        tag="Execution",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/complete-stage",
        summary="Complete Execution Stage",
        description="Finalizes the specified stage with verified evidence and unlocks subsequent stages.",  # noqa: E501
        request_body='{"stage": "inspect_repository"}',
        response_body='{"mission_id": "uuid", "lifecycle_state": "ANALYZE_FAILURE"}',
        status_codes=(200, 400, 401, 404, 422),
        tag="Execution",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/report",
        summary="Generate Final Report",
        description="Compiles verified evidence ledger and signs final certified software engineering report.",  # noqa: E501
        request_body='{"summary": "Successfully fixed bug."}',
        response_body='{"report_id": "uuid", "status": "verified_success", "evidence_count": 5}',
        status_codes=(200, 401, 404, 422),
        tag="Execution",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/approve",
        summary="Submit Approval Decision",
        description="Submits single-use human operator authorization or denial for staged code patch.",  # noqa: E501
        request_body='{"decision": "approve", "rationale": "Approved after inspection"}',
        response_body='{"decision": "approve", "status": "authorized", "mission_id": "uuid"}',
        status_codes=(200, 400, 401, 404, 422),
        tag="Execution",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/missions/{id}/cancel",
        summary="Cancel Mission",
        description="Immediately and safely terminates active mission execution and records reason.",  # noqa: E501
        request_body='{"reason": "Cancelled by operator"}',
        response_body='{"mission_id": "uuid", "status": "cancelled", "message": "Mission cancelled successfully."}',  # noqa: E501
        status_codes=(200, 401, 404),
        tag="Execution",
    ),
    # =========================================================================
    # 4. Repository Intelligence (3 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/repo/index",
        summary="Get Repository AST Index",
        description="Returns code graph, symbol index, import hierarchy, and structural analysis.",
        request_body=None,
        response_body='{"symbols": [...], "dependencies": [...], "total_files": 42}',
        status_codes=(200, 400, 401),
        tag="Repository Intelligence",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/repo/impact",
        summary="Analyze Change Impact",
        description="Calculates impact radius and affected dependents for modified files and symbols.",  # noqa: E501
        request_body='{"workspace_path": "/path/to/repo", "modified_files": ["src/fix.py"]}',
        response_body='{"impact_score": 0.25, "affected_modules": ["tests/unit/test_fix.py"]}',
        status_codes=(200, 400, 401),
        tag="Repository Intelligence",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/repo/context",
        summary="Optimize Repository Context",
        description="Assembles high-signal, token-budgeted prompt context for cognitive reasoning agents.",  # noqa: E501
        request_body='{"workspace_path": "/path/to/repo", "target_symbols": ["solve_bug"]}',
        response_body='{"context_summary": "...", "included_tokens": 1420}',
        status_codes=(200, 400, 401),
        tag="Repository Intelligence",
    ),
    # =========================================================================
    # 5. Workforce & Multi-Agent (3 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/workforce/roster",
        summary="Get Workforce Roster",
        description="Returns registered agent contracts, capabilities, and role definitions.",
        request_body=None,
        response_body='{"roster": [{"role": "SWE_ENGINEER", "agent_name": "Orion-SWE-Engineer", ...}]}',  # noqa: E501
        status_codes=(200, 401),
        tag="Workforce",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/workforce/review",
        summary="Independent Review",
        description="Executes independent workforce review of proposed code changes by reviewer agent.",  # noqa: E501
        request_body='{"proposal": {...}}',
        response_body='{"verdict": "APPROVED", "comments": []}',
        status_codes=(200, 400, 401),
        tag="Workforce",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/workforce/resolve-conflict",
        summary="Resolve Workforce Conflict",
        description="Mediates conflicting multi-agent patch proposals using authoritative verification rules.",  # noqa: E501
        request_body='{"proposals": [...]}',
        response_body='{"winner": "proposal-1", "resolution_strategy": "VERIFIED_TEST_SCORE"}',
        status_codes=(200, 400, 401),
        tag="Workforce",
    ),
    # =========================================================================
    # 6. Self-Healing & Recovery (4 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/recovery/metrics",
        summary="Get Recovery Metrics",
        description="Returns historical recovery statistics, failure taxonomies, and repair success rates.",  # noqa: E501
        request_body=None,
        response_body='{"total_recoveries": 12, "strategies": {"RETRY_TASK": 8, "CHANGE_MODEL": 4}}',  # noqa: E501
        status_codes=(200, 401),
        tag="Recovery",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/recovery/classify",
        summary="Classify Failure",
        description="Classifies test failure or execution error into standard root-cause recovery taxonomy.",  # noqa: E501
        request_body='{"error_message": "AssertionError: expected 5 got 4"}',
        response_body='{"category": "LOGIC_ERROR", "recommended_action": "RETRY_TASK"}',
        status_codes=(200, 400, 401),
        tag="Recovery",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/recovery/simulate",
        summary="Simulate Recovery Strategy",
        description="Simulates alternative recovery strategies before mutating real repository files.",  # noqa: E501
        request_body='{"failure_category": "SYNTAX_ERROR"}',
        response_body='{"predicted_success_rate": 0.88, "strategy": "RETRY_TASK"}',
        status_codes=(200, 400, 401),
        tag="Recovery",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/recovery/plan",
        summary="Generate Recovery Plan",
        description="Produces bounded multi-step recovery plan with rollback safety checkpoints.",
        request_body='{"failure_category": "TIMEOUT"}',
        response_body='{"plan_id": "uuid", "steps": [...], "max_attempts": 3}',
        status_codes=(200, 400, 401),
        tag="Recovery",
    ),
    # =========================================================================
    # 7. Human Oversight (HITL) (7 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/hitl/clarifications",
        summary="List Clarifications",
        description="Returns active and resolved human-in-the-loop clarification requests.",
        request_body=None,
        response_body='{"clarifications": [...]}',
        status_codes=(200, 401),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/hitl/clarifications/request",
        summary="Request Clarification",
        description="Agent requests human clarification when requirement ambiguity exceeds threshold.",  # noqa: E501
        request_body='{"question": "Confirm target branch", "options": ["main", "dev"]}',
        response_body='{"clarification_id": "uuid", "status": "PENDING"}',
        status_codes=(201, 400, 401),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/hitl/clarifications/{id}/respond",
        summary="Respond to Clarification",
        description="Operator submits answer to an open clarification request, unblocking the agent.",  # noqa: E501
        request_body='{"response": "main"}',
        response_body='{"clarification_id": "uuid", "status": "RESOLVED"}',
        status_codes=(200, 400, 401, 404),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/hitl/interventions/{id}",
        summary="Get Interventions",
        description="Retrieves operator interventions injected into a specific mission lifecycle.",
        request_body=None,
        response_body='{"interventions": [...]}',
        status_codes=(200, 401),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/hitl/intervene",
        summary="Inject Operator Intervention",
        description="Injects real-time steering directive, pause/resume, or emergency termination.",
        request_body='{"mission_id": "uuid", "type": "STEER", "directive": "Focus on unit tests"}',
        response_body='{"intervention_id": "uuid", "status": "APPLIED"}',
        status_codes=(200, 400, 401),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/hitl/feedback/{id}",
        summary="Get Mission Feedback",
        description="Retrieves operator evaluation and calibration feedback for a finished mission.",  # noqa: E501
        request_body=None,
        response_body='{"feedback": [...]}',
        status_codes=(200, 401),
        tag="Human Oversight",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/hitl/feedback",
        summary="Submit Mission Feedback",
        description="Records post-mission operator satisfaction score, comments, and grading.",
        request_body='{"mission_id": "uuid", "rating": 5, "comment": "Clean fix"}',
        response_body='{"feedback_id": "uuid", "status": "RECORDED"}',
        status_codes=(201, 400, 401),
        tag="Human Oversight",
    ),
    # =========================================================================
    # 8. Policy & Security (4 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/policy/rules",
        summary="List Policy Rules",
        description="Returns active central security, tool permission, and workspace containment rules.",  # noqa: E501
        request_body=None,
        response_body='{"rules": [{"id": "...", "effect": "DENY", "action": "delete_file"}]}',
        status_codes=(200, 401),
        tag="Policy",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/policy/rules",
        summary="Register Policy Rule",
        description="Adds a custom security policy rule to the central policy engine.",
        request_body='{"name": "Deny Delete", "action": "delete_file", "effect": "DENY"}',
        response_body='{"rule_id": "uuid", "status": "CREATED"}',
        status_codes=(201, 400, 401),
        tag="Policy",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/policy/decisions",
        summary="Get Policy Decisions Audit",
        description="Returns immutable audit trail of policy evaluations and authorization decisions.",  # noqa: E501
        request_body=None,
        response_body='{"decisions": [{"action": "write_file", "decision": "ALLOW", "timestamp": "..."}]}',  # noqa: E501
        status_codes=(200, 401),
        tag="Policy",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/policy/evaluate",
        summary="Evaluate Policy Action",
        description="Evaluates proposed tool execution against policy rules and returns ALLOW/DENY verdict.",  # noqa: E501
        request_body='{"subject": "agent", "action": "write_file", "resource": "file.py"}',
        response_body='{"decision": "ALLOW", "risk_tier": "LOW"}',
        status_codes=(200, 400, 401),
        tag="Policy",
    ),
    # =========================================================================
    # 9. Evaluation Lab & Benchmarks (9 endpoints)
    # =========================================================================
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/benchmarks",
        summary="List Benchmark Tasks",
        description="Returns available reproducible software engineering bug-fix benchmark corpora.",  # noqa: E501
        request_body=None,
        response_body='{"corpora": ["SMOKE", "STANDARD", "FAILURE_TAXONOMY"], "tasks": [...]}',
        status_codes=(200, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/benchmarks/run",
        summary="Run Benchmark Suite",
        description="Executes SWE benchmark suite runner across defined test tasks.",
        request_body='{"corpus": "SMOKE"}',
        response_body='{"benchmark_id": "uuid", "status": "completed", "score": 1.0}',
        status_codes=(200, 400, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/runs",
        summary="List Evaluation Runs",
        description="Returns historical evaluation runs with aggregate metrics and verification rates.",  # noqa: E501
        request_body=None,
        response_body='{"runs": [{"run_id": "uuid", "pass_rate": 0.85, ...}]}',
        status_codes=(200, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/evaluation/run",
        summary="Execute Evaluation Run",
        description="Triggers a controlled evaluation run across selected benchmark corpus.",
        request_body='{"corpus": "STANDARD", "parallel": false}',
        response_body='{"run_id": "uuid", "status": "running"}',
        status_codes=(201, 400, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/compare",
        summary="Compare Evaluation Runs",
        description="Compares metrics and regression statistics across two evaluation runs via GET query.",  # noqa: E501
        request_body=None,
        response_body='{"run_a": "uuid-1", "run_b": "uuid-2", "delta_pass_rate": 0.05}',
        status_codes=(200, 400, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="POST",
        path="/api/v1/evaluation/compare",
        summary="Compare Evaluation Runs (POST)",
        description="Compares metrics and failure taxonomy shifts across two evaluation runs via POST body.",  # noqa: E501
        request_body='{"run_id_a": "uuid-1", "run_id_b": "uuid-2"}',
        response_body='{"comparison": {"pass_rate_diff": 0.05, "regressions": []}}',
        status_codes=(200, 400, 401),
        tag="Evaluation",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/runs/{id}",
        summary="Get Evaluation Run Detail",
        description="Returns detailed scorecard, task breakdown, and duration of an evaluation run.",  # noqa: E501
        request_body=None,
        response_body='{"run_id": "uuid", "total_tasks": 10, "passed": 8, "failed": 2}',
        status_codes=(200, 401, 404),
        tag="Evaluation",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/runs/{id}/metrics",
        summary="Get Evaluation Run Metrics",
        description="Returns fine-grained duration, cost, test coverage, and verification metrics.",
        request_body=None,
        response_body='{"metrics": {"duration_seconds": 45.2, "verification_rate": 0.8}}',
        status_codes=(200, 401, 404),
        tag="Evaluation",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/evaluation/runs/{id}/failures",
        summary="Get Evaluation Run Failures",
        description="Returns detailed categorized failure list and error logs for an evaluation run.",  # noqa: E501
        request_body=None,
        response_body='{"failures": [{"task_id": "...", "reason": "timeout"}]}',
        status_codes=(200, 401, 404),
        tag="Evaluation",
    ),
    # =========================================================================
    # 10. Distributed Telemetry & Observability (5 endpoints)
    # =========================================================================
    RouteDoc(
        method="POST",
        path="/api/v1/observability/spans",
        summary="Record Telemetry Span",
        description="Ingests distributed trace span for performance, latency, and duration observability.",  # noqa: E501
        request_body='{"name": "agent_reasoning", "duration_ms": 145.2}',
        response_body='{"span_id": "uuid", "status": "RECORDED"}',
        status_codes=(201, 400, 401),
        tag="Observability",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/observability/spans/{id}",
        summary="Get Trace Spans",
        description="Retrieves distributed trace spans belonging to a specific trace identifier.",
        request_body=None,
        response_body='{"trace_id": "uuid", "spans": [...]}',
        status_codes=(200, 401),
        tag="Observability",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/observability/metrics/cost",
        summary="Get Resource & Cost Metrics",
        description="Returns token consumption, execution durations, and estimated operation costs.",  # noqa: E501
        request_body=None,
        response_body='{"total_tokens": 12400, "estimated_cost_usd": 0.024}',
        status_codes=(200, 401),
        tag="Observability",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/observability/bottlenecks",
        summary="Get System Bottlenecks",
        description="Detects high-latency pipeline bottlenecks and slow execution stages.",
        request_body=None,
        response_body='{"bottlenecks": [{"stage": "run_tests", "avg_duration_ms": 4200}]}',
        status_codes=(200, 401),
        tag="Observability",
    ),
    RouteDoc(
        method="GET",
        path="/api/v1/observability/optimize",
        summary="Get Optimization Advice",
        description="Returns automated system optimization and caching recommendations.",
        request_body=None,
        response_body='{"recommendations": [{"action": "enable_test_caching", "impact": "HIGH"}]}',
        status_codes=(200, 401),
        tag="Observability",
    ),
)


STATIC_ROUTES: tuple[RouteDoc, ...] = (
    RouteDoc(
        method="GET",
        path="/",
        summary="ORION Mission Command Cockpit UI",
        description="Serves the primary production web application shell and interactive views.",
        request_body=None,
        response_body="HTML5 document (text/html)",
        status_codes=(200,),
        tag="UI",
    ),
    RouteDoc(
        method="GET",
        path="/favicon.svg",
        summary="Geometric Brand Mark",
        description="Serves the authentic geometric ORION orbital brand mark.",
        request_body=None,
        response_body="SVG image (image/svg+xml)",
        status_codes=(200,),
        tag="UI",
    ),
    RouteDoc(
        method="GET",
        path="/static/{file}",
        summary="Client Static Assets",
        description="Serves client stylesheets, scripts, and media with strict MIME validation.",
        request_body=None,
        response_body="CSS, JavaScript, or static media file",
        status_codes=(200, 403, 404),
        tag="UI",
    ),
)


def generate_api_markdown() -> str:
    """Generate docs/API.md directly from the authoritative route registry."""
    total_rest = len(ROUTE_REGISTRY)
    total_static = len(STATIC_ROUTES)
    total_all = total_rest + total_static

    lines = [
        "# ORION REST API SPECIFICATION",
        "",
        f"**Authoritative Route Count**: **{total_rest} REST Endpoints** ({total_all} Total Routes including UI Static)",  # noqa: E501
        "**Runtime Standard**: 100% Python Standard Library (0 third-party runtime dependencies)",
        "**Protocol**: HTTP/1.1 with Server-Sent Events (SSE)",
        "**Base Paths**: `/api/v1/*` (Primary), `/api/*` (Backward-Compatible Aliases)",
        "",
        "---",
        "",
        "## 1. Executive Summary & Routing Table",
        "",
        "| Tag | Method | Path | Summary | Status Codes |",
        "|---|---|---|---|---|",
    ]

    for r in ROUTE_REGISTRY:
        codes_str = ", ".join(str(c) for c in r.status_codes)
        lines.append(f"| {r.tag} | `{r.method}` | `{r.path}` | {r.summary} | `{codes_str}` |")

    for s in STATIC_ROUTES:
        codes_str = ", ".join(str(c) for c in s.status_codes)
        lines.append(f"| {s.tag} | `{s.method}` | `{s.path}` | {s.summary} | `{codes_str}` |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Authentication, Security & Invariants",
            "",
            "1. **API Token Authentication**: Configured via `ORION_API_KEY` / `ORION_API_TOKEN` in `AppConfig`. Optional on local loopback (`127.0.0.1`), strictly required when binding to non-loopback network interfaces.",  # noqa: E501
            "2. **Strict Content-Type**: POST requests with non-empty payloads require `Content-Type: application/json`.",  # noqa: E501
            "3. **Bounded Request Payloads**: Request bodies are capped at `max_request_body_bytes` (default 10 MB) to prevent denial of service.",  # noqa: E501
            "4. **Path Traversal Protection**: Static asset serving strictly contains paths within `src/orion/ui/static` and rejects directory traversal (`..`).",  # noqa: E501
            "5. **Single-Use Approval Tokens**: Approval gates require cryptographically isolated single-use tokens to prevent replay attacks.",  # noqa: E501
            "",
            "---",
            "",
            "## 3. Detailed Endpoint Specifications",
            "",
        ]
    )

    current_tag = ""
    for idx, r in enumerate(ROUTE_REGISTRY, 1):
        if r.tag != current_tag:
            current_tag = r.tag
            lines.extend([f"### Category: {current_tag}", ""])

        lines.extend(
            [
                f"#### {idx}. `{r.method} {r.path}` — {r.summary}",
                f"- **Description**: {r.description}",
                f"- **Status Codes**: {', '.join(str(c) for c in r.status_codes)}",
            ]
        )
        if r.request_body:
            lines.extend(
                [
                    "- **Request Body**:",
                    "```json",
                    r.request_body,
                    "```",
                ]
            )
        lines.extend(
            [
                "- **Response Body**:",
                "```json",
                r.response_body,
                "```",
                "",
            ]
        )

    return "\n".join(lines) + "\n"

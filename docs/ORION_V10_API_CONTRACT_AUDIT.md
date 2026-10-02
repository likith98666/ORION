# ORION V10 — Final API Contract Audit & Specification

**Release Candidate Version:** `10.0.0-rc1`  
**API Specification Version:** `v1`  
**Protocol:** HTTP/1.1 REST + Server-Sent Events (SSE)  
**Status:** **AUDITED & CERTIFIED**

---

## 1. Executive Summary

This document certifies the exhaustive audit of all REST and real-time streaming endpoints exposed by the ORION Autonomous AI Engineering platform (`src/orion/api/server.py` and `src/orion/api/service.py`).

Every endpoint has been verified against:
1. Strict input validation and sanitization.
2. Path containment and security boundary enforcement.
3. Central Policy Engine (`PolicyEngine`) evaluation.
4. Deterministic single-key/dual-key authorization where applicable.
5. Error schemas adhering to structured JSON responses (`{"error": str, "code": int}`).
6. Active integration with the V10 Flagship Frontend cockpit.

---

## 2. API Contract Matrix

### 2.1 System Health & Lifecycle

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health`<br>`/api/health` | Subsystem liveness & uptime | Public | `{"status": "healthy", "uptime_seconds": float, "missions_count": int}` | `200 OK` |
| `GET` | `/api/v1/readiness`<br>`/api/readiness` | Subsystem readiness & workspace writeability check | Public | `{"status": "ready", "workspace": str}` | `200 OK` |

---

### 2.2 Missions & Engineering Tasks (V1, V2)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/tasks`<br>`/api/v1/missions` | Initialize autonomous engineering mission | Validated Path, Policy: `init_mission` | `{"mission_id": UUID, "task_id": UUID, "status": "initialized", "objective": str}` | `201 Created` |
| `GET` | `/api/tasks`<br>`/api/v1/missions` | List all tracked missions | Tenant / Scope | `{"missions": [...], "total": int}` | `200 OK` |
| `GET` | `/api/tasks/{id}`<br>`/api/v1/missions/{id}` | Retrieve mission record & lifecycle status | Resource ID | Serialized `MissionRecord` | `200 OK` |
| `POST` | `/api/tasks/{id}/run`<br>`/api/v1/missions/{id}/run` | Execute full multi-stage autonomous pipeline asynchronously | Single-run Lock | `{"status": "running"}` | `200 OK` |
| `POST` | `/api/tasks/{id}/cancel`<br>`/api/v1/missions/{id}/cancel` | Immediately cancel and halt pipeline | Idempotent | `{"status": "cancelled", "mission_id": UUID}` | `200 OK` |
| `POST` | `/api/v1/missions/{id}/advance` | Step-advance single stage in workflow | Stage Transition Guard | `{"status": "advanced", "current_stage": str}` | `200 OK` |
| `GET` | `/api/v1/missions/{id}/report` | Retrieve certified SWE mission report | Verification Authority | `{"report": SWEReport}` | `200 OK` |

---

### 2.3 Mission Telemetry & Forensic Subresources

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/tasks/{id}/execution` | Real-time execution telemetry and pending approval status | Read-only | `{"task_id": UUID, "status": str, "current_stage": str, "approval_required": bool}` | `200 OK` |
| `GET` | `/api/tasks/{id}/changes` | Code changes, affected files, additions/deletions, unified diff | Read-only | `{"affected_files": [...], "diff": str, "lines_added": int, "lines_removed": int}` | `200 OK` |
| `GET` | `/api/tasks/{id}/tests` | Controlled pytest execution output and exit code | Read-only | `{"exit_code": int, "output": str, "tests_passed": int, "tests_failed": int}` | `200 OK` |
| `GET` | `/api/tasks/{id}/recovery` | Recovery state, failure diagnosis, and budget progress | Read-only | `{"attempts": int, "strategy": str, "budget_remaining": {...}}` | `200 OK` |
| `GET` | `/api/tasks/{id}/verification`| Authoritative verification criteria and ground-truth decision | Read-only | `{"status": "verified", "criteria": [...], "authority": "VerificationEngine"}` | `200 OK` |
| `GET` | `/api/tasks/{id}/evidence` | Forensic evidence ledger records | Read-only | `{"evidence": [...], "counts": {...}}` | `200 OK` |
| `GET` | `/api/tasks/{id}/timeline` | Chronological mission lifecycle events | Read-only | `{"timeline": [...]}` | `200 OK` |
| `GET` | `/api/tasks/{id}/graph` | Mission DAG nodes, dependencies, and state | Read-only | `{"nodes": [...], "edges": [...]}` | `200 OK` |
| `GET` | `/api/tasks/{id}/agents` | Active workforce roster and specialist assignments | Read-only | `{"agents": [...], "active_count": int}` | `200 OK` |
| `POST` | `/api/tasks/{id}/approve` | Authorize or deny high-risk patch modification | Single-use Token | `{"approval_status": "APPROVED" \| "DENIED"}` | `200 OK` |
| `GET` | `/api/tasks/{id}/events` | Real-time Server-Sent Events (SSE) telemetry stream | SSE Stream | `text/event-stream` | `200 OK` |

---

### 2.4 Repository Intelligence (V3)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/repo/index` | Retrieve repository file and AST symbol count | Workspace Bound | `{"total_files": int, "total_symbols": int}` | `200 OK` |
| `POST` | `/api/v1/repo/impact` | Analyze direct and transitive blast radius of a file change | Workspace Bound | `{"direct_dependents": [...], "transitive_dependents": [...], "blast_radius_score": float}` | `200 OK` |
| `POST` | `/api/v1/repo/context` | Construct token-bounded context neighborhood around file | Workspace Bound | `{"included_files": [...], "total_tokens": int}` | `200 OK` |

---

### 2.5 Multi-Agent Workforce (V4)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/workforce/roster` | Roster of active agents, roles, capabilities, and permissions | Read-only | `{"agents": [...], "total_agents": int, "active_agents": int}` | `200 OK` |
| `POST` | `/api/v1/workforce/review` | Trigger independent multi-stage peer review of candidate patch | Policy Guard | `{"verdict": "APPROVED" \| "REJECTED", "critique": [...]}` | `200 OK` |
| `POST` | `/api/v1/workforce/resolve-conflict` | Evidence-based conflict resolution across competing proposals | Policy Guard | `{"winning_proposal_id": UUID, "rationale": str}` | `200 OK` |

---

### 2.6 Self-Healing Recovery (V5)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/recovery/metrics` | Empirical strategy success rates from past recovery attempts | Read-only | `{"strategies": {...}}` | `200 OK` |
| `POST` | `/api/v1/recovery/classify`| Classify execution error output into formal failure taxonomy | Pure Function | `{"category": str, "confidence": float, "diagnosis": str}` | `200 OK` |
| `POST` | `/api/v1/recovery/simulate`| Pre-flight simulation verifying recovery safety and blast radius | Non-destructive | `{"safe": bool, "predicted_duration": float, "blast_radius": float}` | `200 OK` |
| `POST` | `/api/v1/recovery/plan` | Formulate adaptive recovery plan incorporating memory | Recovery Budget | `{"strategy": str, "steps": [...]}` | `200 OK` |

---

### 2.7 Human-in-the-Loop & Collaborative Oversight (V7)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/hitl/clarifications` | List pending clarification requests | Read-only | `{"clarifications": [...]}` | `200 OK` |
| `POST` | `/api/v1/hitl/clarifications/request` | Request human clarification for ambiguous task directives | Bounded Timeout | `{"request_id": UUID, "status": "PENDING"}` | `201 Created` |
| `POST` | `/api/v1/hitl/clarifications/{id}/respond` | Submit human clarification resolution | Authorized Actor | `{"request_id": UUID, "status": "RESOLVED"}` | `200 OK` |
| `POST` | `/api/v1/hitl/intervene` | Dispatch operator intervention (Pause, Resume, Steer, Force Fail) | Authorized Actor | `{"intervention_id": UUID, "status": "APPLIED"}` | `200 OK` |
| `GET` | `/api/v1/hitl/interventions/{mission_id}` | Retrieve historical interventions for a mission | Read-only | `{"interventions": [...]}` | `200 OK` |
| `POST` | `/api/v1/hitl/feedback` | Record operator post-mission review rating and critique | Authorized Actor | `{"feedback_id": UUID, "rating": int}` | `201 Created` |
| `GET` | `/api/v1/hitl/feedback/{mission_id}` | Retrieve recorded feedback for a mission | Read-only | `{"feedback": [...]}` | `200 OK` |

---

### 2.8 Policy Engine & Autonomous Security Hardening (V8)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/policy/rules` | List active policy guardrail rules | Read-only | `{"rules": [...]}` | `200 OK` |
| `POST` | `/api/v1/policy/rules` | Register new policy rule | Admin / Security | `{"status": "added", "rule_id": str}` | `201 Created` |
| `GET` | `/api/v1/policy/decisions` | Query recent policy evaluation decisions audit log | Read-only | `{"decisions": [...], "total": int}` | `200 OK` |
| `POST` | `/api/v1/policy/evaluate` | Interactive policy simulator (what-if evaluation) | PolicyEngine | `{"decision": "ALLOW" \| "DENY" \| "REQUIRE_APPROVAL" \| "MODIFY", "rule_id": str, "reason": str}` | `200 OK` |

---

### 2.9 Evaluation & Benchmarking Intelligence (V6)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/evaluation/benchmarks` | Catalog of available benchmark suites (`standard`, `smoke`, `taxonomy`) | Read-only | `{"suites": [...]}` | `200 OK` |
| `GET` | `/api/v1/evaluation/runs` | List recorded benchmark experiments | Read-only | `{"runs": [...]}` | `200 OK` |
| `GET` | `/api/v1/evaluation/runs/{id}` | Retrieve full experiment details and metrics | Read-only | Serialized `ExperimentRecord` | `200 OK` |
| `POST` | `/api/v1/evaluation/run` | Execute benchmark experiment and register immutable record | Runner | `{"experiment_id": str, "metrics": {...}}` | `201 Created` |
| `POST` | `/api/v1/evaluation/compare` | Compute differential comparison metrics between two experiments | Comparator | `{"delta_success_rate": float, "delta_latency_p90": float, "regressions": [...]}` | `200 OK` |

---

### 2.10 Advanced Observability & Distributed Telemetry (V9)

| Method | Endpoint | Description | Auth / Policy | Response | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/observability/spans/{mission_id}` | Retrieve distributed trace spans waterfall | Read-only | `{"spans": [...], "total": int}` | `200 OK` |
| `GET` | `/api/v1/observability/metrics/cost` | Aggregated prompt/completion tokens and estimated cost | Read-only | `{"prompt_tokens": int, "completion_tokens": int, "total_cost_usd": float}` | `200 OK` |
| `GET` | `/api/v1/observability/bottlenecks` | System bottleneck analysis and latency quantiles (P50, P90, P99) | Read-only | `{"p50_ms": float, "p90_ms": float, "p99_ms": float, "slowest_spans": [...]}` | `200 OK` |
| `GET` | `/api/v1/observability/optimize` | Actionable heuristic performance recommendations | Read-only | `{"recommendations": [...]}` | `200 OK` |

---

## 3. Security & Invariant Verification

1. **Path Traversal Protection:** Every workspace path input is resolved and validated via `validate_workspace_path()`. Escapes to parent directories or system roots are rejected with HTTP 400.
2. **Deterministic Rejection of Malformed IDs:** UUID validation rejects non-conforming IDs with HTTP 400.
3. **Fail-Safe Policy Enforcement:** Tool executions route through `PolicyEngine.evaluate()`. `DENY` decisions raise `PermissionError` and terminate execution safely.
4. **Single-Use Approval Tokens:** Approval tokens generated by `ApprovalService` are invalidated upon first use to prevent replay attacks.
5. **No Secrets in Responses:** All credentials and environment variables are filtered from error and span payloads before transmission.

**Audit Status:** **100% GREEN // CERTIFIED FOR V10 RELEASE CANDIDATE**

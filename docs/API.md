# ORION REST API SPECIFICATION

**Authoritative Route Count**: **61 REST Endpoints** (64 Total Routes including UI Static)
**Runtime Standard**: 100% Python Standard Library (0 third-party runtime dependencies)
**Protocol**: HTTP/1.1 with Server-Sent Events (SSE)
**Base Paths**: `/api/v1/*` (Primary), `/api/*` (Backward-Compatible Aliases)

---

## 1. Executive Summary & Routing Table

| Tag | Method | Path | Summary | Status Codes |
|---|---|---|---|---|
| System | `GET` | `/api/v1/health` | System Health Probe | `200` |
| System | `GET` | `/api/v1/readiness` | Service Readiness Probe | `200, 503` |
| Missions | `GET` | `/api/v1/missions` | List Missions | `200, 401` |
| Missions | `POST` | `/api/v1/missions` | Initialize Mission | `201, 400, 401, 422, 429` |
| Missions | `POST` | `/api/v1/missions/plan` | Plan Mission Decomposition | `201, 400, 401` |
| Missions | `GET` | `/api/v1/missions/{id}` | Get Mission Details | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/events` | Mission Event Stream (SSE) | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/execution` | Get Task Execution Details | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/timeline` | Get Mission Timeline | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/evidence` | Get Forensic Evidence Ledger | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/changes` | Get Code Changes & Diffs | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/tests` | Get Test Execution Logs | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/recovery` | Get Self-Healing Recovery State | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/verification` | Get Authoritative Verification | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/evaluation` | Get Evaluation Scorecard | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/report` | Get Certified Final Report | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/agents` | Get Mission Workforce Telemetry | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/graph` | Get DAG Execution Graph | `200, 401, 404` |
| Missions | `GET` | `/api/v1/missions/{id}/memory` | Get Mission Memory Context | `200, 401, 404` |
| Missions | `POST` | `/api/v1/missions/{id}/run` | Execute Pipeline | `202, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/advance` | Advance Execution Stage | `200, 400, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/tool` | Execute Sandboxed Tool | `200, 400, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/complete-stage` | Complete Execution Stage | `200, 400, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/report` | Generate Final Report | `200, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/approve` | Submit Approval Decision | `200, 400, 401, 404, 422` |
| Execution | `POST` | `/api/v1/missions/{id}/cancel` | Cancel Mission | `200, 401, 404` |
| Repository Intelligence | `GET` | `/api/v1/repo/index` | Get Repository AST Index | `200, 400, 401` |
| Repository Intelligence | `POST` | `/api/v1/repo/impact` | Analyze Change Impact | `200, 400, 401` |
| Repository Intelligence | `POST` | `/api/v1/repo/context` | Optimize Repository Context | `200, 400, 401` |
| Workforce | `GET` | `/api/v1/workforce/roster` | Get Workforce Roster | `200, 401` |
| Workforce | `POST` | `/api/v1/workforce/review` | Independent Review | `200, 400, 401` |
| Workforce | `POST` | `/api/v1/workforce/resolve-conflict` | Resolve Workforce Conflict | `200, 400, 401` |
| Recovery | `GET` | `/api/v1/recovery/metrics` | Get Recovery Metrics | `200, 401` |
| Recovery | `POST` | `/api/v1/recovery/classify` | Classify Failure | `200, 400, 401` |
| Recovery | `POST` | `/api/v1/recovery/simulate` | Simulate Recovery Strategy | `200, 400, 401` |
| Recovery | `POST` | `/api/v1/recovery/plan` | Generate Recovery Plan | `200, 400, 401` |
| Human Oversight | `GET` | `/api/v1/hitl/clarifications` | List Clarifications | `200, 401` |
| Human Oversight | `POST` | `/api/v1/hitl/clarifications/request` | Request Clarification | `201, 400, 401` |
| Human Oversight | `POST` | `/api/v1/hitl/clarifications/{id}/respond` | Respond to Clarification | `200, 400, 401, 404` |
| Human Oversight | `GET` | `/api/v1/hitl/interventions/{id}` | Get Interventions | `200, 401` |
| Human Oversight | `POST` | `/api/v1/hitl/intervene` | Inject Operator Intervention | `200, 400, 401` |
| Human Oversight | `GET` | `/api/v1/hitl/feedback/{id}` | Get Mission Feedback | `200, 401` |
| Human Oversight | `POST` | `/api/v1/hitl/feedback` | Submit Mission Feedback | `201, 400, 401` |
| Policy | `GET` | `/api/v1/policy/rules` | List Policy Rules | `200, 401` |
| Policy | `POST` | `/api/v1/policy/rules` | Register Policy Rule | `201, 400, 401` |
| Policy | `GET` | `/api/v1/policy/decisions` | Get Policy Decisions Audit | `200, 401` |
| Policy | `POST` | `/api/v1/policy/evaluate` | Evaluate Policy Action | `200, 400, 401` |
| Evaluation | `GET` | `/api/v1/evaluation/benchmarks` | List Benchmark Tasks | `200, 401` |
| Evaluation | `POST` | `/api/v1/benchmarks/run` | Run Benchmark Suite | `200, 400, 401` |
| Evaluation | `GET` | `/api/v1/evaluation/runs` | List Evaluation Runs | `200, 401` |
| Evaluation | `POST` | `/api/v1/evaluation/run` | Execute Evaluation Run | `201, 400, 401` |
| Evaluation | `GET` | `/api/v1/evaluation/compare` | Compare Evaluation Runs | `200, 400, 401` |
| Evaluation | `POST` | `/api/v1/evaluation/compare` | Compare Evaluation Runs (POST) | `200, 400, 401` |
| Evaluation | `GET` | `/api/v1/evaluation/runs/{id}` | Get Evaluation Run Detail | `200, 401, 404` |
| Evaluation | `GET` | `/api/v1/evaluation/runs/{id}/metrics` | Get Evaluation Run Metrics | `200, 401, 404` |
| Evaluation | `GET` | `/api/v1/evaluation/runs/{id}/failures` | Get Evaluation Run Failures | `200, 401, 404` |
| Observability | `POST` | `/api/v1/observability/spans` | Record Telemetry Span | `201, 400, 401` |
| Observability | `GET` | `/api/v1/observability/spans/{id}` | Get Trace Spans | `200, 401` |
| Observability | `GET` | `/api/v1/observability/metrics/cost` | Get Resource & Cost Metrics | `200, 401` |
| Observability | `GET` | `/api/v1/observability/bottlenecks` | Get System Bottlenecks | `200, 401` |
| Observability | `GET` | `/api/v1/observability/optimize` | Get Optimization Advice | `200, 401` |
| UI | `GET` | `/` | ORION Mission Command Cockpit UI | `200` |
| UI | `GET` | `/favicon.svg` | Geometric Brand Mark | `200` |
| UI | `GET` | `/static/{file}` | Client Static Assets | `200, 403, 404` |

---

## 2. Authentication, Security & Invariants

1. **API Token Authentication**: Configured via `ORION_API_KEY` / `ORION_API_TOKEN` in `AppConfig`. Optional on local loopback (`127.0.0.1`), strictly required when binding to non-loopback network interfaces.
2. **Strict Content-Type**: POST requests with non-empty payloads require `Content-Type: application/json`.
3. **Bounded Request Payloads**: Request bodies are capped at `max_request_body_bytes` (default 10 MB) to prevent denial of service.
4. **Path Traversal Protection**: Static asset serving strictly contains paths within `src/orion/ui/static` and rejects directory traversal (`..`).
5. **Single-Use Approval Tokens**: Approval gates require cryptographically isolated single-use tokens to prevent replay attacks.

---

## 3. Detailed Endpoint Specifications

### Category: System

#### 1. `GET /api/v1/health` — System Health Probe
- **Description**: Returns system operational status, version, uptime, and active mission count.
- **Status Codes**: 200
- **Response Body**:
```json
{"status": "healthy", "version": "1.0.0", "uptime_seconds": 12.3, "missions_count": 0}
```

#### 2. `GET /api/v1/readiness` — Service Readiness Probe
- **Description**: Checks filesystem containment, workspace validity, and tool executor availability.
- **Status Codes**: 200, 503
- **Response Body**:
```json
{"status": "ready", "checks": {"workspace": true, "tools": true}}
```

### Category: Missions

#### 3. `GET /api/v1/missions` — List Missions
- **Description**: Returns all active, historical, and completed autonomous software engineering missions.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"missions": [...], "tasks": [...], "total": 1}
```

#### 4. `POST /api/v1/missions` — Initialize Mission
- **Description**: Submits an autonomous engineering directive, creates a mission record, and bounds workspace.
- **Status Codes**: 201, 400, 401, 422, 429
- **Request Body**:
```json
{"task": "Fix bug", "workspace": "/path/to/repo", "execution_mode": "controlled"}
```
- **Response Body**:
```json
{"mission_id": "uuid", "task_id": "uuid", "status": "initialized", "lifecycle_state": "RECEIVED"}
```

#### 5. `POST /api/v1/missions/plan` — Plan Mission Decomposition
- **Description**: Decomposes high-level objective into deterministic 7-stage task graph and resource budget.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"objective": "Implement feature", "max_duration_seconds": 300.0}
```
- **Response Body**:
```json
{"plan_id": "uuid", "stages": [...], "budget": {...}}
```

#### 6. `GET /api/v1/missions/{id}` — Get Mission Details
- **Description**: Retrieves current execution state, active stage, and telemetry for a specific mission.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"mission_id": "uuid", "status": "running_inspect_repository", "lifecycle_state": "INSPECT_REPOSITORY"}
```

#### 7. `GET /api/v1/missions/{id}/events` — Mission Event Stream (SSE)
- **Description**: Real-time Server-Sent Events (SSE) telemetry stream publishing chronological mission events.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
text/event-stream (event: CONNECTED, STAGE_STARTED, etc.)
```

#### 8. `GET /api/v1/missions/{id}/execution` — Get Task Execution Details
- **Description**: Returns low-level task execution state, stage details, and execution identifiers.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"execution_id": "uuid", "status": "running", "current_stage": "inspect_repository"}
```

#### 9. `GET /api/v1/missions/{id}/timeline` — Get Mission Timeline
- **Description**: Returns chronological sequence of recorded events for mission replay and timeline scrubber.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"timeline": [{"event_id": "uuid", "stage": "...", "title": "...", "timestamp": "..."}]}
```

#### 10. `GET /api/v1/missions/{id}/evidence` — Get Forensic Evidence Ledger
- **Description**: Returns evidence ledger items filtered by level (CLAIMED, OBSERVED, VERIFIED) and category.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"evidence": [{"id": "uuid", "level": "VERIFIED", "category": "TEST_RESULT", ...}]}
```

#### 11. `GET /api/v1/missions/{id}/changes` — Get Code Changes & Diffs
- **Description**: Returns unified git diffs, modified file paths, and patch operation statistics.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"diff": "--- a/file.py\n+++ b/file.py...", "files_modified": 1, "lines_added": 2, "lines_removed": 1}
```

#### 12. `GET /api/v1/missions/{id}/tests` — Get Test Execution Logs
- **Description**: Returns sandboxed pytest test results, selected target scopes, and execution logs.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"exit_code": 0, "stdout": "1 passed...", "targets": ["tests/unit/test_fix.py"]}
```

#### 13. `GET /api/v1/missions/{id}/recovery` — Get Self-Healing Recovery State
- **Description**: Returns recovery attempts, active strategy (RETRY_TASK, CHANGE_MODEL), and budget bars.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"recovery_attempts": 0, "failure_category": "NONE", "strategy": "RETRY_TASK"}
```

#### 14. `GET /api/v1/missions/{id}/verification` — Get Authoritative Verification
- **Description**: Returns ground-truth verification verdict, test suite pass status, and integrity checks.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"is_verified": true, "verification_passed": true, "ground_truth": "PASS"}
```

#### 15. `GET /api/v1/missions/{id}/evaluation` — Get Evaluation Scorecard
- **Description**: Returns evaluation metrics, criteria outcomes, and quality scorecards for the mission.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"status": "PASS", "tests_passed": 1, "tests_failed": 0, "verification_passed": true}
```

#### 16. `GET /api/v1/missions/{id}/report` — Get Certified Final Report
- **Description**: Returns structured cryptographic software engineering report with full audit trail.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"report_id": "uuid", "status": "verified_success", "summary": "...", "evidence": [...]}
```

#### 17. `GET /api/v1/missions/{id}/agents` — Get Mission Workforce Telemetry
- **Description**: Returns specialized agent roster, assignments, and telemetry for the specified mission.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"roster": [{"name": "Orion-SWE-Engineer", "status": "active", ...}]}
```

#### 18. `GET /api/v1/missions/{id}/graph` — Get DAG Execution Graph
- **Description**: Returns deterministic 7-stage DAG topology nodes and monotonic execution states.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"nodes": [{"id": "inspect_repository", "status": "COMPLETED", ...}], "edges": [...]}
```

#### 19. `GET /api/v1/missions/{id}/memory` — Get Mission Memory Context
- **Description**: Returns episodic memories, semantic search results, and repository context snapshots.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"memory": {"episodes": [...], "working_context": {...}}}
```

#### 20. `POST /api/v1/missions/{id}/run` — Execute Pipeline
- **Description**: Triggers automated sequential progression through all uncompleted engineering stages.
- **Status Codes**: 202, 401, 404, 422
- **Request Body**:
```json
{"auto_approve": false, "background": true}
```
- **Response Body**:
```json
{"status": "executing", "mission_id": "uuid", "message": "Pipeline execution initiated."}
```

### Category: Execution

#### 21. `POST /api/v1/missions/{id}/advance` — Advance Execution Stage
- **Description**: Transitions mission execution to the specified target stage if valid.
- **Status Codes**: 200, 400, 401, 404, 422
- **Request Body**:
```json
{"stage": "inspect_repository"}
```
- **Response Body**:
```json
{"mission_id": "uuid", "status": "running_inspect_repository"}
```

#### 22. `POST /api/v1/missions/{id}/tool` — Execute Sandboxed Tool
- **Description**: Executes a capability tool within stage permissions and sandboxed workspace boundaries.
- **Status Codes**: 200, 400, 401, 404, 422
- **Request Body**:
```json
{"stage": "inspect_repository", "tool_name": "list_files", "arguments": {}}
```
- **Response Body**:
```json
{"success": true, "tool_name": "list_files", "output": [...], "error": null}
```

#### 23. `POST /api/v1/missions/{id}/complete-stage` — Complete Execution Stage
- **Description**: Finalizes the specified stage with verified evidence and unlocks subsequent stages.
- **Status Codes**: 200, 400, 401, 404, 422
- **Request Body**:
```json
{"stage": "inspect_repository"}
```
- **Response Body**:
```json
{"mission_id": "uuid", "lifecycle_state": "ANALYZE_FAILURE"}
```

#### 24. `POST /api/v1/missions/{id}/report` — Generate Final Report
- **Description**: Compiles verified evidence ledger and signs final certified software engineering report.
- **Status Codes**: 200, 401, 404, 422
- **Request Body**:
```json
{"summary": "Successfully fixed bug."}
```
- **Response Body**:
```json
{"report_id": "uuid", "status": "verified_success", "evidence_count": 5}
```

#### 25. `POST /api/v1/missions/{id}/approve` — Submit Approval Decision
- **Description**: Submits single-use human operator authorization or denial for staged code patch.
- **Status Codes**: 200, 400, 401, 404, 422
- **Request Body**:
```json
{"decision": "approve", "rationale": "Approved after inspection"}
```
- **Response Body**:
```json
{"decision": "approve", "status": "authorized", "mission_id": "uuid"}
```

#### 26. `POST /api/v1/missions/{id}/cancel` — Cancel Mission
- **Description**: Immediately and safely terminates active mission execution and records reason.
- **Status Codes**: 200, 401, 404
- **Request Body**:
```json
{"reason": "Cancelled by operator"}
```
- **Response Body**:
```json
{"mission_id": "uuid", "status": "cancelled", "message": "Mission cancelled successfully."}
```

### Category: Repository Intelligence

#### 27. `GET /api/v1/repo/index` — Get Repository AST Index
- **Description**: Returns code graph, symbol index, import hierarchy, and structural analysis.
- **Status Codes**: 200, 400, 401
- **Response Body**:
```json
{"symbols": [...], "dependencies": [...], "total_files": 42}
```

#### 28. `POST /api/v1/repo/impact` — Analyze Change Impact
- **Description**: Calculates impact radius and affected dependents for modified files and symbols.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"workspace_path": "/path/to/repo", "modified_files": ["src/fix.py"]}
```
- **Response Body**:
```json
{"impact_score": 0.25, "affected_modules": ["tests/unit/test_fix.py"]}
```

#### 29. `POST /api/v1/repo/context` — Optimize Repository Context
- **Description**: Assembles high-signal, token-budgeted prompt context for cognitive reasoning agents.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"workspace_path": "/path/to/repo", "target_symbols": ["solve_bug"]}
```
- **Response Body**:
```json
{"context_summary": "...", "included_tokens": 1420}
```

### Category: Workforce

#### 30. `GET /api/v1/workforce/roster` — Get Workforce Roster
- **Description**: Returns registered agent contracts, capabilities, and role definitions.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"roster": [{"role": "SWE_ENGINEER", "agent_name": "Orion-SWE-Engineer", ...}]}
```

#### 31. `POST /api/v1/workforce/review` — Independent Review
- **Description**: Executes independent workforce review of proposed code changes by reviewer agent.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"proposal": {...}}
```
- **Response Body**:
```json
{"verdict": "APPROVED", "comments": []}
```

#### 32. `POST /api/v1/workforce/resolve-conflict` — Resolve Workforce Conflict
- **Description**: Mediates conflicting multi-agent patch proposals using authoritative verification rules.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"proposals": [...]}
```
- **Response Body**:
```json
{"winner": "proposal-1", "resolution_strategy": "VERIFIED_TEST_SCORE"}
```

### Category: Recovery

#### 33. `GET /api/v1/recovery/metrics` — Get Recovery Metrics
- **Description**: Returns historical recovery statistics, failure taxonomies, and repair success rates.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"total_recoveries": 12, "strategies": {"RETRY_TASK": 8, "CHANGE_MODEL": 4}}
```

#### 34. `POST /api/v1/recovery/classify` — Classify Failure
- **Description**: Classifies test failure or execution error into standard root-cause recovery taxonomy.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"error_message": "AssertionError: expected 5 got 4"}
```
- **Response Body**:
```json
{"category": "LOGIC_ERROR", "recommended_action": "RETRY_TASK"}
```

#### 35. `POST /api/v1/recovery/simulate` — Simulate Recovery Strategy
- **Description**: Simulates alternative recovery strategies before mutating real repository files.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"failure_category": "SYNTAX_ERROR"}
```
- **Response Body**:
```json
{"predicted_success_rate": 0.88, "strategy": "RETRY_TASK"}
```

#### 36. `POST /api/v1/recovery/plan` — Generate Recovery Plan
- **Description**: Produces bounded multi-step recovery plan with rollback safety checkpoints.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"failure_category": "TIMEOUT"}
```
- **Response Body**:
```json
{"plan_id": "uuid", "steps": [...], "max_attempts": 3}
```

### Category: Human Oversight

#### 37. `GET /api/v1/hitl/clarifications` — List Clarifications
- **Description**: Returns active and resolved human-in-the-loop clarification requests.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"clarifications": [...]}
```

#### 38. `POST /api/v1/hitl/clarifications/request` — Request Clarification
- **Description**: Agent requests human clarification when requirement ambiguity exceeds threshold.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"question": "Confirm target branch", "options": ["main", "dev"]}
```
- **Response Body**:
```json
{"clarification_id": "uuid", "status": "PENDING"}
```

#### 39. `POST /api/v1/hitl/clarifications/{id}/respond` — Respond to Clarification
- **Description**: Operator submits answer to an open clarification request, unblocking the agent.
- **Status Codes**: 200, 400, 401, 404
- **Request Body**:
```json
{"response": "main"}
```
- **Response Body**:
```json
{"clarification_id": "uuid", "status": "RESOLVED"}
```

#### 40. `GET /api/v1/hitl/interventions/{id}` — Get Interventions
- **Description**: Retrieves operator interventions injected into a specific mission lifecycle.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"interventions": [...]}
```

#### 41. `POST /api/v1/hitl/intervene` — Inject Operator Intervention
- **Description**: Injects real-time steering directive, pause/resume, or emergency termination.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"mission_id": "uuid", "type": "STEER", "directive": "Focus on unit tests"}
```
- **Response Body**:
```json
{"intervention_id": "uuid", "status": "APPLIED"}
```

#### 42. `GET /api/v1/hitl/feedback/{id}` — Get Mission Feedback
- **Description**: Retrieves operator evaluation and calibration feedback for a finished mission.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"feedback": [...]}
```

#### 43. `POST /api/v1/hitl/feedback` — Submit Mission Feedback
- **Description**: Records post-mission operator satisfaction score, comments, and grading.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"mission_id": "uuid", "rating": 5, "comment": "Clean fix"}
```
- **Response Body**:
```json
{"feedback_id": "uuid", "status": "RECORDED"}
```

### Category: Policy

#### 44. `GET /api/v1/policy/rules` — List Policy Rules
- **Description**: Returns active central security, tool permission, and workspace containment rules.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"rules": [{"id": "...", "effect": "DENY", "action": "delete_file"}]}
```

#### 45. `POST /api/v1/policy/rules` — Register Policy Rule
- **Description**: Adds a custom security policy rule to the central policy engine.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"name": "Deny Delete", "action": "delete_file", "effect": "DENY"}
```
- **Response Body**:
```json
{"rule_id": "uuid", "status": "CREATED"}
```

#### 46. `GET /api/v1/policy/decisions` — Get Policy Decisions Audit
- **Description**: Returns immutable audit trail of policy evaluations and authorization decisions.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"decisions": [{"action": "write_file", "decision": "ALLOW", "timestamp": "..."}]}
```

#### 47. `POST /api/v1/policy/evaluate` — Evaluate Policy Action
- **Description**: Evaluates proposed tool execution against policy rules and returns ALLOW/DENY verdict.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"subject": "agent", "action": "write_file", "resource": "file.py"}
```
- **Response Body**:
```json
{"decision": "ALLOW", "risk_tier": "LOW"}
```

### Category: Evaluation

#### 48. `GET /api/v1/evaluation/benchmarks` — List Benchmark Tasks
- **Description**: Returns available reproducible software engineering bug-fix benchmark corpora.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"corpora": ["SMOKE", "STANDARD", "FAILURE_TAXONOMY"], "tasks": [...]}
```

#### 49. `POST /api/v1/benchmarks/run` — Run Benchmark Suite
- **Description**: Executes SWE benchmark suite runner across defined test tasks.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"corpus": "SMOKE"}
```
- **Response Body**:
```json
{"benchmark_id": "uuid", "status": "completed", "score": 1.0}
```

#### 50. `GET /api/v1/evaluation/runs` — List Evaluation Runs
- **Description**: Returns historical evaluation runs with aggregate metrics and verification rates.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"runs": [{"run_id": "uuid", "pass_rate": 0.85, ...}]}
```

#### 51. `POST /api/v1/evaluation/run` — Execute Evaluation Run
- **Description**: Triggers a controlled evaluation run across selected benchmark corpus.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"corpus": "STANDARD", "parallel": false}
```
- **Response Body**:
```json
{"run_id": "uuid", "status": "running"}
```

#### 52. `GET /api/v1/evaluation/compare` — Compare Evaluation Runs
- **Description**: Compares metrics and regression statistics across two evaluation runs via GET query.
- **Status Codes**: 200, 400, 401
- **Response Body**:
```json
{"run_a": "uuid-1", "run_b": "uuid-2", "delta_pass_rate": 0.05}
```

#### 53. `POST /api/v1/evaluation/compare` — Compare Evaluation Runs (POST)
- **Description**: Compares metrics and failure taxonomy shifts across two evaluation runs via POST body.
- **Status Codes**: 200, 400, 401
- **Request Body**:
```json
{"run_id_a": "uuid-1", "run_id_b": "uuid-2"}
```
- **Response Body**:
```json
{"comparison": {"pass_rate_diff": 0.05, "regressions": []}}
```

#### 54. `GET /api/v1/evaluation/runs/{id}` — Get Evaluation Run Detail
- **Description**: Returns detailed scorecard, task breakdown, and duration of an evaluation run.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"run_id": "uuid", "total_tasks": 10, "passed": 8, "failed": 2}
```

#### 55. `GET /api/v1/evaluation/runs/{id}/metrics` — Get Evaluation Run Metrics
- **Description**: Returns fine-grained duration, cost, test coverage, and verification metrics.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"metrics": {"duration_seconds": 45.2, "verification_rate": 0.8}}
```

#### 56. `GET /api/v1/evaluation/runs/{id}/failures` — Get Evaluation Run Failures
- **Description**: Returns detailed categorized failure list and error logs for an evaluation run.
- **Status Codes**: 200, 401, 404
- **Response Body**:
```json
{"failures": [{"task_id": "...", "reason": "timeout"}]}
```

### Category: Observability

#### 57. `POST /api/v1/observability/spans` — Record Telemetry Span
- **Description**: Ingests distributed trace span for performance, latency, and duration observability.
- **Status Codes**: 201, 400, 401
- **Request Body**:
```json
{"name": "agent_reasoning", "duration_ms": 145.2}
```
- **Response Body**:
```json
{"span_id": "uuid", "status": "RECORDED"}
```

#### 58. `GET /api/v1/observability/spans/{id}` — Get Trace Spans
- **Description**: Retrieves distributed trace spans belonging to a specific trace identifier.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"trace_id": "uuid", "spans": [...]}
```

#### 59. `GET /api/v1/observability/metrics/cost` — Get Resource & Cost Metrics
- **Description**: Returns token consumption, execution durations, and estimated operation costs.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"total_tokens": 12400, "estimated_cost_usd": 0.024}
```

#### 60. `GET /api/v1/observability/bottlenecks` — Get System Bottlenecks
- **Description**: Detects high-latency pipeline bottlenecks and slow execution stages.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"bottlenecks": [{"stage": "run_tests", "avg_duration_ms": 4200}]}
```

#### 61. `GET /api/v1/observability/optimize` — Get Optimization Advice
- **Description**: Returns automated system optimization and caching recommendations.
- **Status Codes**: 200, 401
- **Response Body**:
```json
{"recommendations": [{"action": "enable_test_caching", "impact": "HIGH"}]}
```


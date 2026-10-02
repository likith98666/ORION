# ORION Phase 7: Product API Specification

## 1. Overview

The ORION Product API exposes typed, deterministic, and audited endpoints for managing engineering missions, tracking real-time telemetry, approving code modifications, and inspecting verification records.

- **Base URL**: `/api/v1`
- **Content-Type**: `application/json` (except SSE streams: `text/event-stream`)
- **Error Format**: RFC-compliant structured JSON with explicit error codes.

---

## 2. Structured Error Format

All 4xx and 5xx responses conform to the following schema:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Mission 'msn-78a9c2' not found in registry.",
    "mission_id": "msn-78a9c2",
    "execution_id": null,
    "details": {}
  }
}
```

Standard error codes:
- `VALIDATION_ERROR`: Malformed input payload or missing required fields.
- `RESOURCE_NOT_FOUND`: Specified mission ID does not exist.
- `APPROVAL_REQUIRED`: Action attempted while waiting for operator sign-off.
- `CONFLICT`: Operation cannot be completed in current mission lifecycle state.
- `EXECUTION_DENIED`: Command or path violates security containment rules.
- `INTERNAL_ERROR`: Unexpected backend processing failure.

---

## 3. Endpoints Reference

### 3.1. Submit Mission
Create a new engineering repair mission.

- **Method**: `POST`
- **Path**: `/api/v1/missions`
- **Request Body**:
```json
{
  "task": "Analyze failing test in test_calculator.py and formulate fix.",
  "workspace": "C:/Projects/Calculator",
  "execution_mode": "controlled"
}
```
- **Response**: `201 Created`
```json
{
  "mission_id": "msn-9a3b4c12",
  "task": "Analyze failing test in test_calculator.py and formulate fix.",
  "status": "initialized",
  "lifecycle_state": "RECEIVED",
  "created_at": "2026-10-02T19:30:00Z"
}
```

---

### 3.2. List Missions
Retrieve all historical and active missions.

- **Method**: `GET`
- **Path**: `/api/v1/missions`
- **Response**: `200 OK`
```json
{
  "total": 3,
  "missions": [
    {
      "mission_id": "msn-9a3b4c12",
      "task": "Fix calculator addition",
      "status": "completed",
      "lifecycle_state": "COMPLETED",
      "created_at": "2026-10-02T19:30:00Z"
    }
  ]
}
```

---

### 3.3. Get Mission Status
Retrieve top-level status and metadata for a specific mission.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}`
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "task": "Fix calculator addition",
  "status": "executing",
  "lifecycle_state": "TESTING",
  "created_at": "2026-10-02T19:30:00Z",
  "cancelled": false
}
```

---

### 3.4. Execute / Resume Mission Pipeline
Start or resume pipeline execution.

- **Method**: `POST`
- **Path**: `/api/v1/missions/{mission_id}/run`
- **Request Body**:
```json
{
  "background": true,
  "auto_approve": false
}
```
- **Response**: `202 Accepted`
```json
{
  "mission_id": "msn-9a3b4c12",
  "status": "started",
  "message": "SWE pipeline execution started in background."
}
```

---

### 3.5. Cancel Mission Execution
Halt an in-progress mission pipeline cleanly.

- **Method**: `POST`
- **Path**: `/api/v1/missions/{mission_id}/cancel`
- **Request Body**:
```json
{
  "reason": "Operator manually requested abort."
}
```
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "status": "cancelled",
  "message": "Mission execution halted successfully."
}
```

---

### 3.6. Real-Time Telemetry Stream (SSE)
Stream real-time server-sent events for mission telemetry.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/events`
- **Response**: `200 OK` (`text/event-stream`)
- **Event Types**:
  - `MISSION_CREATED`
  - `PIPELINE_STARTED`
  - `STAGE_STARTED`
  - `STAGE_COMPLETED`
  - `DIAGNOSTIC_COMPLETED`
  - `PATCH_PROPOSED`
  - `APPROVAL_REQUIRED`
  - `APPROVAL_GRANTED`
  - `APPROVAL_REJECTED`
  - `PATCH_APPLIED`
  - `TESTS_COMPLETED`
  - `VERIFICATION_COMPLETED`
  - `RECOVERY_STARTED`
  - `RECOVERY_ATTEMPTED`
  - `MISSION_COMPLETED`
  - `MISSION_FAILED`
  - `TASK_CANCELLED`
- **Example SSE Payload**:
```text
event: STAGE_STARTED
data: {"event_type": "STAGE_STARTED", "timestamp": "2026-10-02T19:30:05Z", "data": {"stage": "FORMULATE_FIX"}}
```

---

### 3.7. Workforce Roster
Retrieve the list of active agents and their operational status.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/agents`
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "total_agents": 4,
  "agents": [
    {
      "agent_id": "agent-swe-01",
      "name": "Orion-SWE-Engineer",
      "role": "SWE Engineer",
      "status": "BUSY",
      "capabilities": ["code_generation", "patch_synthesis", "ast_analysis"],
      "current_task": "Formulating unified patch for test failure",
      "tasks_completed": 2
    }
  ]
}
```

---

### 3.8. Execution Graph DAG
Retrieve the topological execution graph and per-node states.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/graph`
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "total_nodes_count": 8,
  "nodes": [
    {
      "node_id": "inspect_repository",
      "label": "Inspect Repository",
      "stage": "INSPECT_REPOSITORY",
      "state": "COMPLETED",
      "dependencies": []
    },
    {
      "node_id": "analyze_failure",
      "label": "Analyze Failure",
      "stage": "ANALYZE_FAILURE",
      "state": "COMPLETED",
      "dependencies": ["inspect_repository"]
    },
    {
      "node_id": "approval_gate",
      "label": "Approval Gate",
      "stage": "APPROVAL_GATE",
      "state": "WAITING_APPROVAL",
      "dependencies": ["formulate_fix"]
    }
  ],
  "edges": [
    {"source": "inspect_repository", "target": "analyze_failure"},
    {"source": "analyze_failure", "target": "formulate_fix"},
    {"source": "formulate_fix", "target": "approval_gate"}
  ]
}
```

---

### 3.9. Workspace Changes & Patch Diff
Inspect the synthesized patch and affected workspace files.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/changes`
- **Response**: `200 OK`
```json
{
  "has_changes": true,
  "affected_files": ["src/calculator.py"],
  "total_lines_added": 1,
  "total_lines_removed": 1,
  "unified_diff": "--- src/calculator.py\n+++ src/calculator.py\n@@ -1,2 +1,2 @@\n-    return a - b\n+    return a + b\n",
  "validation_status": "VALID",
  "applied": false
}
```

---

### 3.10. Dual-Key Approval Submission
Submit operator sign-off for a proposed patch.

- **Method**: `POST`
- **Path**: `/api/v1/missions/{mission_id}/approve`
- **Request Body**:
```json
{
  "decision": "approve",
  "approver": "LeadSecurityOfficer",
  "reason": "Authorized modification to arithmetic logic."
}
```
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "status": "approved",
  "decision": "approve",
  "approver": "LeadSecurityOfficer",
  "timestamp": "2026-10-02T19:32:00Z"
}
```

---

### 3.11. Controlled Test Results
Inspect the results of tests executed under `ControlledExecutionAuthority`.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/tests`
- **Response**: `200 OK`
```json
{
  "executed": true,
  "command": "pytest tests/test_calculator.py",
  "exit_code": 0,
  "passed": 5,
  "failed": 0,
  "skipped": 0,
  "duration_ms": 1420.5,
  "stdout": "5 passed in 1.42s"
}
```

---

### 3.12. Verification Evaluation
Retrieve the authoritative verification record.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/verification`
- **Response**: `200 OK`
```json
{
  "status": "passed",
  "confidence_score": 1.0,
  "criteria_results": {
    "test_suite_passed": true,
    "no_regressions": true,
    "patch_contained_in_workspace": true
  },
  "verified_at": "2026-10-02T19:33:00Z"
}
```

---

### 3.13. Bounded Recovery State
Retrieve recovery budget consumption and strategy logs.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/recovery`
- **Response**: `200 OK`
```json
{
  "recovery_active": false,
  "attempts_used": 0,
  "max_attempts": 3,
  "remaining_attempts": 3,
  "budget_remaining_percent": 100.0,
  "history": []
}
```

---

### 3.14. Evidence Ledger
Inspect the complete tamper-evident audit trail with provenance.

- **Method**: `GET`
- **Path**: `/api/v1/missions/{mission_id}/evidence`
- **Response**: `200 OK`
```json
{
  "mission_id": "msn-9a3b4c12",
  "total": 6,
  "evidence": [
    {
      "evidence_id": "ev-001",
      "category": "repository_state",
      "epistemic_status": "OBSERVED",
      "source": "DiagnosticsSpecialist",
      "timestamp": "2026-10-02T19:30:10Z",
      "content_summary": "AST tree analysis of calculator.py"
    }
  ]
}
```

---

### 3.15. Final Certified Report
Generate and retrieve the sealed final mission report.

- **Method**: `POST` / `GET`
- **Path**: `/api/v1/missions/{mission_id}/report`
- **Response**: `200 OK`
```json
{
  "mission": {
    "mission_id": "msn-9a3b4c12",
    "task_id": "msn-9a3b4c12",
    "status": "verified_success",
    "summary": "Calculator addition bug resolved and verified."
  },
  "evaluation": {
    "status": "passed",
    "criteria": {
      "all_tests_passed": true,
      "verification_sealed": true
    }
  }
}
```

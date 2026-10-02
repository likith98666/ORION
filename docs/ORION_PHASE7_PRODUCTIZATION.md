# ORION Phase 7: Productization & Mission Command Center Architecture

## 1. Executive Summary

ORION Phase 7 transforms the verified Phase 1–6 backend engineering, verification, and self-healing recovery subsystems into a production-grade, interactive **Mission Command Center**.

Phase 7 adheres strictly to the core principle:
> **Build the system first. Design the UI around the system.**
> Every button, metric, agent state, execution node, diff line, test outcome, verification criterion, and recovery budget reflects authoritative server-side state. Zero simulated telemetry or decorative mockups exist.

---

## 2. End-to-End System Architecture

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                     ORION MISSION COMMAND CENTER                       │
 │      (Cinematic Obsidian Dark UI · Vanilla HTML5/CSS3/ES2022)          │
 │                                                                        │
 │ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐ │
 │ │ Workforce Roster │ │  Execution DAG   │ │ Real-Time Telemetry/SSE  │ │
 │ └─────────┬────────┘ └─────────┬────────┘ └─────────────┬────────────┘ │
 │           │                    │                        │              │
 │ ┌─────────▼────────┐ ┌─────────▼────────┐ ┌─────────────▼────────────┐ │
 │ │  Approval Gate   │ │  Unified Diffs   │ │ Controlled Test & Verif  │ │
 │ └──────────────────┘ └──────────────────┘ └──────────────────────────┘ │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP REST + SSE Stream
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                       ORION PRODUCT API LAYER                          │
 │                    (Pydantic DTOs · Thread-Safe)                       │
 │                                                                        │
 │  POST/GET /api/v1/missions        POST /api/v1/missions/{id}/cancel    │
 │  GET /api/v1/missions/{id}/events (SSE)                                │
 │  GET /api/v1/missions/{id}/agents GET /api/v1/missions/{id}/graph      │
 │  GET /api/v1/missions/{id}/changes POST /api/v1/missions/{id}/approve  │
 │  GET /api/v1/missions/{id}/tests  GET /api/v1/missions/{id}/verif      │
 │  GET /api/v1/missions/{id}/recovery GET /api/v1/missions/{id}/evidence │
 │  POST/GET /api/v1/missions/{id}/report                                 │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Authoritative Invocations
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                    ORION CORE PIPELINE & CONTROL                       │
 │                                                                        │
 │  ┌──────────────────────────────────────────────────────────────────┐  │
 │  │ SWEWorkflowCoordinator (8-Stage Workflow Orchestration)          │  │
 │  │ Stage 1: Inspect Repo    Stage 5: Implement Changes              │  │
 │  │ Stage 2: Analyze Failure Stage 6: Controlled Tests               │  │
 │  │ Stage 3: Formulate Fix   Stage 7: Authoritative Verification     │  │
 │  │ Stage 4: Approval Gate   Stage 8: Certified Final Report         │  │
 │  └──────────────────────────────────────────────────────────────────┘  │
 │                                                                        │
 │  ┌──────────────────────────┐ ┌──────────────────────────────────────┐ │
 │  │ ApprovalService          │ │ ControlledExecutionAuthority         │ │
 │  │ Capability Token Gate    │ │ Shell=False · Command Allowlist      │ │
 │  └──────────────────────────┘ └──────────────────────────────────────┘ │
 │  ┌──────────────────────────┐ ┌──────────────────────────────────────┐ │
 │  │ VerificationEngine       │ │ RecoveryCoordinator                  │ │
 │  │ Epistemic Gate           │ │ Bounded Budget · Rollback Protection │ │
 │  └──────────────────────────┘ └──────────────────────────────────────┘ │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Append-Only Epistemic Record
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                   AUTHORITATIVE EVIDENCE & STATE                       │
 │                                                                        │
 │   EvidenceLedger: CLAIMED ──▶ OBSERVED ──▶ VERIFIED                   │
 │   Workspace Isolation: Subpath Containment · Symlink / Junction Guards │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mission Lifecycle Contract

The product API projects the internal pipeline states into a deterministic, high-level lifecycle:

| Lifecycle State | Description | Transition Trigger |
| :--- | :--- | :--- |
| `RECEIVED` | Mission registered in ledger; initial repo bounds inspected. | Client `POST /api/v1/missions` |
| `PLANNING` | Diagnostics Specialist isolating fault, analyzing AST and stack traces. | Workflow start (`Stage 1-2`) |
| `PLANNED` | Diagnostic report completed; fix strategy formulated. | End of `Stage 2` |
| `EXECUTING` | SWE Engineer generating patch proposal within workspace bounds. | Start of `Stage 3` |
| `AWAITING_APPROVAL`| Patch proposal generated; execution paused pending dual-key authorization. | Patch synthesis completed |
| `APPLYING` | Human operator approved patch; transactional atomic apply underway. | `POST /api/v1/missions/{id}/approve` |
| `TESTING` | ControlledExecutionAuthority executing non-interactive pytest runner. | `Stage 6` execution |
| `VERIFYING` | VerificationEngine independently validating criteria against evidence ledger. | `Stage 7` execution |
| `RECOVERING` | Failure detected; RecoveryCoordinator executing bounded remediation strategy. | Test failure or verification rejection |
| `COMPLETED` | Certified SWE mission report generated with verifiable evidence chain. | Stage 8 evaluation success |
| `FAILED` | Unrecoverable failure, budget exhausted, or verification failed irreversibly. | Budget exhaustion or hard stop |
| `CANCELLED` | Operator aborted mission execution via API or UI command. | `POST /api/v1/missions/{id}/cancel` |

---

## 4. Subsystems & Product Integrations

### 4.1. Workforce Observatory
ORION’s workforce observatory provides a role-specialized projection of the autonomous SWE subsystem:
1. **Orion-SWE-Engineer**: Backed by the runtime mission agent (`record.agent`). Handles code generation, patch synthesis, and AST analysis. Permissions: `file_read`, `patch_propose`.
2. **Orion-Diagnostics-Specialist**: Represents the automated failure localization and diagnostic subsystem. Active during `ANALYZE_FAILURE`. Permissions: `file_read`, `test_analyze`.
3. **Orion-Verification-Authority**: Represents the independent `VerificationEngine` and evaluation authority. Active during `VERIFY`. Permissions: `evidence_verify`, `report_sign`.
4. **Orion-Recovery-Specialist**: Represents the `RecoveryCoordinator` executing the bounded self-healing recovery loop. Active during `RECOVERING`. Permissions: `recovery_plan`, `rollback_execute`.

Each agent card in the UI displays real-time execution metrics: assigned tasks, live operational status (`IDLE`, `ACTIVE`, `WAITING_APPROVAL`, `COMPLETED`), completed step count, and agent UUID. Status transitions reflect real coordinator stage transitions without simulated activity.

### 4.2. Execution Graph (Topological Workflow Projection)
The mission workflow is projected as a canonical 8-node Directed Acyclic Graph (DAG):
- `inspect_repository` ➔ `analyze_failure` ➔ `formulate_fix` ➔ `approval_gate` ➔ `implement_change` ➔ `run_tests` ➔ `verify` ➔ `generate_report`.

This graph is a deterministic visualization of the canonical SWE workflow stages and the explicit approval boundary:
- `PENDING`: Waiting for upstream node completion.
- `READY`: All dependencies met; ready to run.
- `RUNNING`: Actively executing.
- `WAITING_APPROVAL`: Execution paused for human operator intervention.
- `COMPLETED`: Successfully executed.
- `VERIFIED`: Proven and sealed by VerificationEngine.
- `FAILED`: Node failed execution.

### 4.3. Dual-Key Approval Experience
Security Rule: **The frontend NEVER directly modifies files or authorizes execution.**
1. When a patch is synthesized, the workflow transitions to `AWAITING_APPROVAL`.
2. The UI renders the **Dual-Key Approval Gate**:
   - Assessed risk rating (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - Single-use capability approval token (UUID4) bound to agent ID, execution ID, and proposed actions.
   - List of affected workspace files.
   - Lines added and lines removed.
   - Unified diff viewer highlighting additions and deletions.
3. The human operator enters their operator name, decision (`approve` or `reject`), and operational rationale.
4. The request is dispatched to `POST /api/v1/missions/{mission_id}/approve`.
5. The backend `ApprovalService` verifies token validity, records the audit trail in the append-only evidence ledger, and authorizes the `SWEWorkflowCoordinator` to resume.

### 4.4. Controlled Test Observatory
Tests are executed exclusively through `ControlledExecutionAuthority`:
- Shell execution is strictly prohibited (`shell=False`).
- Command parameters are constrained to an immutable allowlist (`pytest`, `python -m pytest`).
- The UI displays:
  - Command line invocation.
  - Duration in milliseconds.
  - Exit code.
  - Tests collected, passed, failed, and skipped.
  - Raw stdout/stderr terminal output with ANSI rendering.

### 4.5. Epistemic Verification Authority
ORION enforces an explicit epistemic boundary:
$$\text{CLAIMED} \longrightarrow \text{OBSERVED} \longrightarrow \text{VERIFIED}$$

- **Claimed**: Proposed changes, hypothesized fixes.
- **Observed**: Concrete tool outputs, test exit codes, modified file contents.
- **Verified**: Promoted solely by the `VerificationEngine` after checking deterministic criteria (e.g. exit code 0, no regressions, modified file integrity hash match).
- The UI makes this distinction visually unmistakable with distinct status badges and audit trails.

### 4.6. Bounded Self-Healing Recovery Observatory
When tests or verification fail, ORION does not loop infinitely:
- The `RecoveryCoordinator` classifies the failure (`SYNTAX_ERROR`, `ASSERTION_FAILURE`, `REGRESSION`, `ENVIRONMENT_ERROR`).
- Applies a selected bounded strategy (`REGENERATE_PATCH`, `ALTERNATIVE_FIX`, `ROLLBACK`).
- Enforces three hard limits:
  1. Maximum recovery attempts (e.g. 3 attempts).
  2. Model regeneration budget.
  3. Execution time budget.
- The UI exposes real-time recovery budget gauges, remaining attempts, and step-by-step recovery logs.

---

## 5. Security & Isolation Invariants

1. **Zero Client Trust**: All authorization decisions, diff generation, and command executions occur server-side.
2. **Workspace Containment**: All file operations and test runs are locked within the designated workspace directory using resolved canonical paths. Symlinks and junctions targeting external directories are rejected.
3. **No Arbitrary Execution**: The API rejects arbitrary commands. Only predefined test commands vetted by `ControlledExecutionAuthority` are allowed.
4. **Credential & Secret Protection**: No API keys, server tokens, or sensitive environment variables are rendered to the client or logged to telemetry streams.

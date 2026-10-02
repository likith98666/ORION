# ORION — Autonomous AI Execution Platform

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-Controlled%20Workforce-purple.svg)]()
[![Verification](https://img.shields.io/badge/verification-Authoritative-emerald.svg)]()
[![Security](https://img.shields.io/badge/security-Sandbox%20%2B%20Approval-red.svg)]()

> **ORION** is an autonomous AI execution platform that plans, coordinates, executes, verifies, and recovers complex multi-step technical work through a controlled, observable AI workforce.

---

## 1. Executive Overview

Unlike uncontrolled chatbot loops that invoke LLMs in open-ended `while not solved` cycles, ORION operates like an industrial software engineering organization. Every technical mission is governed by a deterministic task graph, bounded filesystem containment, authoritative verification, transparent failure recovery, and an immutable evidence ledger.

### Flagship Capability: Autonomous Software Engineering (SWE)

Given a software engineering mission on any codebase, ORION:
1. **Inspects** the repository without making destructive changes (read-only containment).
2. **Analyzes** test failures and runtime diagnostics to isolate the defect.
3. **Formulates** a structured repair hypothesis and step-by-step modification plan.
4. **Implements** targeted changes under strict cryptographic hash concurrency and human approval gating for high-risk write operations.
5. **Executes** relevant test suites in isolated subprocesses (`shell=False`).
6. **Authoritatively Verifies** that requirements are satisfied using ORION's native `VerificationEngine`.
7. **Recovers** automatically via the `RecoveryCoordinator` if the initial repair fails, preserving full diagnostic audit trails.
8. **Compiles Evidence** separating assertions into `CLAIMED`, `OBSERVED`, and `VERIFIED` tiers.
9. **Evaluates** mission success deterministically against 6 rigorous criteria.
10. **Generates** an evidence-backed final certification report.

---

## 2. Core Product Principles

```text
MISSION
   ↓
UNDERSTAND
   ↓
PLAN
   ↓
ASSIGN
   ↓
EXECUTE
   ↓
VERIFY
   ↓
RECOVER IF NECESSARY
   ↓
EVALUATE
   ↓
REPORT
```

### The 10 Invariants of ORION
1. **No Second Orchestration Engine**: All execution uses ORION's native `Plan`, `PlanStep`, `PlanValidator`, and `Scheduler`.
2. **No Second Verification Engine**: The existing `VerificationEngine` remains the sole authority.
3. **No Uncontrolled Loops**: Autonomy occurs strictly within deterministic graph boundaries.
4. **Tool Success ≠ Task Success**: A tool exiting with code 0 does not imply the stage or objective is complete.
5. **Test Pass ≠ Fix Verification**: Passing a test suite does not certify a fix without authoritative engine verification.
6. **Verification Required for Success**: No mission can be declared successful without authoritative `VERIFIED` evidence.
7. **Workspace Isolation Mandatory**: All filesystem operations are bound to canonical workspace roots, blocking traversal, symlink escapes, and secret file access.
8. **Dangerous Writes Require Approval**: High-risk operations (file writes, patch applications) route through ORION's `ApprovalService`.
9. **No Arbitrary Shell Invocation**: No raw shell access (`shell=True`, `cmd.exe`, `bash -c`); all execution uses sanitized, controlled subprocess wrappers.
10. **Evidence Must Be Truthful**: `CLAIMED` agent hypotheses are never converted into `VERIFIED` facts without cryptographic and authoritative validation.

---

## 3. The 7-Stage Deterministic SWE Task Graph

```text
┌─────────────────────────┐
│ 1. INSPECT_REPOSITORY   │ Read-only scanning, directory mapping, file reads
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. ANALYZE_FAILURE      │ Reproduce failure via test runner, capture stack trace
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. FORMULATE_FIX        │ Structured reasoning, ProposedFixPlan formulation
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. IMPLEMENT_CHANGE     │ Controlled write/diff with human approval & hash locking
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. RUN_TESTS            │ Isolated subprocess test execution (shell=False)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 6. VERIFY               │ Authoritative VerificationEngine evaluation
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 7. GENERATE_REPORT      │ EvidenceLedger compilation & SWEEvaluator certification
└─────────────────────────┘
```

| Stage | Permitted Tools | Risk Level | Mutates State |
| :--- | :--- | :--- | :--- |
| `INSPECT_REPOSITORY` | `list_files`, `read_file`, `search_files` | Low | No |
| `ANALYZE_FAILURE` | `read_file`, `search_files`, `run_tests` | Low | No |
| `FORMULATE_FIX` | None (Reasoning & Formulation Plan only) | None | No |
| `IMPLEMENT_CHANGE` | `write_file`, `apply_change`, `diff`, `read_file` | High (Approval Required) | Yes |
| `RUN_TESTS` | `run_tests`, `run_lint`, `run_typecheck` | Medium | No |
| `VERIFY` | `VerificationEngine` invocation | Authoritative | No |
| `GENERATE_REPORT` | Evidence ledger compilation & export | None | No |

---

## 4. Evidence & Evaluation Hierarchy

ORION implements a three-tiered epistemology:

```text
CLAIMED
  ▲ Agent hypothesis, plan, reasoning, or unverified assertion.
  │
OBSERVED
  ▲ Concrete output from a controlled tool, subprocess stdout, or diff.
  │
VERIFIED
  Authoritative result certified by VerificationEngine against formal criteria.
```

### Controlled Taxonomy (11 Categories)
* `REPOSITORY_STATE`: File listings, directory topology, branch states.
* `FILE_OBSERVATION`: Bounded file contents read from disk.
* `DIAGNOSTIC_RESULT`: Error patterns, ripgrep match counts, parser logs.
* `PROPOSED_CHANGE`: Formal `ProposedFixPlan` dataclass instances.
* `FILE_CHANGE`: Cryptographically hashed file writes, bytes written.
* `COMMAND_RESULT`: Raw subprocess outputs, exit codes, runtimes.
* `TEST_RESULT`: Test runner exit codes, passed/failed counters, tracebacks.
* `DIFF_RESULT`: Unified diff chunks, lines added, lines removed.
* `VERIFICATION_RESULT`: Authoritative verdicts, passing rule lists.
* `RECOVERY_EVENT`: Failure records, recovery strategies, retry actions.
* `MISSION_OUTCOME`: Final evaluation verdict (`PASS`, `FAIL`, `INCONCLUSIVE`).

### Deterministic Evaluator (`SWEEvaluator`)
Evaluates 6 objective criteria without subjective scoring or fabricated metrics:
1. `workflow_completed`: All 7 stages sequentially traversed and completed.
2. `test_passed`: Target test execution returned exit code 0.
3. `verification_passed`: VerificationEngine certified the requirements.
4. `evidence_complete`: Ledger contains evidence for all mandatory categories.
5. `changes_traceable`: Every modified file has associated unified diffs and hashes.
6. `recovery_transparent`: Any failure and recovery cycle is fully documented.

---

## 5. System Architecture

```text
src/orion/
├── main.py                     # CLI entrypoint & server launcher
├── api/                        # Product REST API & DTO boundaries
│   ├── dto.py                  # Isolated Data Transfer Objects
│   ├── server.py               # Native standard-library HTTP server
│   └── service.py              # Mission service orchestrating SWE core
├── ui/                         # Mission Command Center UI
│   └── static/
│       ├── index.html          # Obsidian cinematic command interface
│       ├── app.css             # Glassmorphism & cybernetic tokens
│       └── app.js              # Real-time telemetry, stepper, tabs
└── core/
    ├── agents/                 # Capability-based agent workforce
    ├── planning/               # Task graph, Plan, PlanStep, PlanValidator
    ├── tools/                  # Controlled tools, registry, permissions
    │   └── repository/         # Bounded repository tools (read/write/test/diff)
    ├── workspace/              # Workspace isolation & canonical containment
    ├── verification/           # Authoritative VerificationEngine
    ├── recovery/               # RecoveryCoordinator, Failure, Strategy
    ├── security/               # ApprovalService, audit, secret isolation
    ├── observability/          # TelemetryContext, ExecutionIdentity
    └── swe/                    # Flagship SWE task graph, coordinator, evidence
```

---

## 6. Quick Start & Installation

### Requirements
* Python 3.12+ (Standard library only; zero third-party runtime dependencies)
* Git 2.30+

### Local Setup
```bash
# Clone the repository
git clone https://github.com/orion-ai/orion.git
cd ORION

# Setup virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Verify environment readiness
python scripts/validate_environment.py
```

### Launch the Mission Command Center
```bash
# Start server on default port 8000
python -m orion --host 127.0.0.1 --port 8000 --workspace .
```

Open your browser to:
* **Mission Command Center UI**: `http://127.0.0.1:8000/`
* **API Health Check**: `http://127.0.0.1:8000/api/v1/health`

---

## 7. Production Deployment

### Docker Deployment
```bash
# Build and run using Docker Compose
docker compose up -d

# Verify container health
docker compose ps
curl http://localhost:8000/api/v1/health
```

### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `ORION_HOST` | Host interface to bind HTTP server | `127.0.0.1` (`0.0.0.0` in Docker) |
| `ORION_PORT` | Port number for REST API & UI | `8000` |
| `ORION_WORKSPACE` | Default repository workspace root | `.` |

---

## 8. Product REST API Reference

All requests and responses use strict JSON DTOs:

* `GET /api/v1/health`: System health, uptime, active missions count.
* `POST /api/v1/missions`: Create a new mission (`objective`, `workspace_path`).
* `GET /api/v1/missions`: List active missions with summary statistics.
* `GET /api/v1/missions/{id}`: Detailed mission state and progress.
* `POST /api/v1/missions/{id}/advance`: Advance workflow to designated stage.
* `POST /api/v1/missions/{id}/tool`: Execute a controlled tool within active stage.
* `POST /api/v1/missions/{id}/complete-stage`: Mark current stage complete.
* `GET /api/v1/missions/{id}/timeline`: Retrieve timestamped execution events.
* `GET /api/v1/missions/{id}/evidence`: Query evidence ledger (`level`, `category`).
* `GET /api/v1/missions/{id}/verification`: Retrieve verification records.
* `GET /api/v1/missions/{id}/recovery`: Retrieve recovery decisions and actions.
* `GET /api/v1/missions/{id}/evaluation`: Query deterministic criteria evaluation.
* `GET /api/v1/missions/{id}/report`: Export final certified engineering report.

---

## 9. Testing & Benchmarking

### Full Regression Suite
```bash
.\.venv\Scripts\python.exe -m pytest -q
# Result: 1207 passed, 1 skipped (Windows symlink dev-mode privilege)
```

### Benchmark Suite
```bash
.\.venv\Scripts\python.exe -m pytest tests/benchmarks/ -v
```
Deterministic benchmarks include:
1. `test_benchmark_bug_diagnosis_and_code_repair`: Off-by-one algorithmic repair.
2. `test_benchmark_test_repair`: Test synchronization and assertion updates.
3. `test_benchmark_security_boundary_enforcement`: Sandbox escape rejection.
4. `test_benchmark_unbounded_evidence_suppression`: Memory explosion defense.

### Security Validation Suite
```bash
.\.venv\Scripts\python.exe -m pytest tests/unit/security/test_swe_security_suite.py -v
```

---

## 10. Verification vs. Recovery

When an initial change fails verification:
```text
Attempt 1 (Faulty Fix)
    ↓
Verification Fails (VerificationEngine)
    ↓
VerificationFailureAdapter converts result to Failure
    ↓
RecoveryCoordinator initiates retry strategy
    ↓
Attempt 2 (Correct Fix Applied)
    ↓
Verification Passes (VerificationEngine)
    ↓
Evidence Ledger preserves BOTH attempts:
    - Attempt 1: Failed
    - Recovery Event: Logged with strategy & action
    - Attempt 2: Verified Success
```
ORION guarantees full diagnostic transparency: failed attempts are never silently erased or overwritten.

---

## 11. Controlled Cognitive SWE Loop & Patch Synthesis (Phases 3 & 4)

ORION supports controlled model-assisted failure analysis, fix formulation, and bounded patch synthesis within deterministic security, approval, execution, recovery, and verification boundaries. The model acts strictly as an untrusted reasoning and proposal component; ORION retains authoritative control at all times.

### Architectural Flow: The Model Proposes, ORION Validates, Approval Authorizes

```text
             ┌──────────────────────────────┐
             │       SWE Workflow           │
             │   deterministic authority    │
             └──────────────┬───────────────┘
                            │
                            ▼
                 ContextAssembler (Phase 2)
              (Relativized, fenced, bounded)
                            │
                            ▼
                     ModelRuntime
                            │
                            ▼
                     ModelGateway
                            │
                            ▼
                 BaseModelProvider (LLM)
                            │
                            ▼
                UNTRUSTED MODEL PROPOSAL
              (FailureAnalysis / Fix / Patch)
                            │
                            ▼
              Proposal & Patch Validators
         (Schema, types, paths, safety regex)
                            │
                            ▼
            Deterministic Validation Layer
      ┌─────────────────────┼─────────────────────┐
      ▼                     ▼                     ▼
Syntax Validation     Diff Inspection       Hash Locking
 (Python AST)         (Unified Diffs)     (SHA-256 Check)
      └─────────────────────┬─────────────────────┘
                            │
                            ▼
                 ApprovalService (Phase 4)
             (Human & Policy Gating Boundary)
                            │
                            ▼
              READY FOR CONTROLLED EXECUTION
                   (Deferred to Phase 5)
```

### Cognitive Stages Supported
1. **`ANALYZE_FAILURE` (Model-Assisted Diagnosis)**:
   - Evaluates test execution output, stack traces, and repository context via `SWECognitiveService`.
   - Validates response into a structured `FailureAnalysisProposal` (root cause, failure classification, affected files, proposed action).
   - Records the proposal into the `EvidenceLedger` strictly as `EvidenceLevel.CLAIMED`.
2. **`FORMULATE_FIX` (Model-Assisted Plan Formulation)**:
   - Takes validated failure analysis and relevant file contents through `ContextAssembler`.
   - Validates response into a structured `FixProposal` (change intent, affected files, declarative modifications, validation plan).
   - Bridges to `ProposedFixPlan` for deterministic execution approval, keeping all proposed modifications non-authoritative.
3. **`PatchSynthesizer` (Bounded Patch Synthesis — Phase 4)**:
   - Synthesizes concrete, reviewable code modifications from validated fix proposals via `PatchSynthesizer`.
   - Structures changes into explicit conservative operations (`CREATE_FILE`, `MODIFY_FILE`, `DELETE_FILE`).
   - Generates deterministic unified diffs via `PatchDiffGenerator` for pre-application inspection.
   - Validates language syntax deterministically via `PatchSyntaxValidator` (Python AST verification).
   - Verifies optimistic file hash locks via `StalePatchError` to detect concurrent file modifications.
   - Submits structured proposals to `ApprovalService` via `PatchApprovalPackage` before any modification is permitted.

### Proposal Trust Model & Epistemology
- **`CLAIMED`**: All model hypotheses, diagnoses, fix plans, and synthesized patch proposals are classified strictly as `CLAIMED`.
- **`OBSERVED`**: Real test execution outputs, subprocess exit codes, AST syntax validation results, and computed unified diffs recorded by controlled tools.
- **`VERIFIED`**: Certified exclusively by `VerificationEngine` against formal rules. Under no circumstances can a model proposal mark an objective as verified or complete.

### Security Invariants & Boundary Enforcement
- **Workspace-Relative Paths**: All model-proposed paths are validated to ensure workspace containment. Absolute paths, UNC paths, `..` directory traversal, and protected files (e.g., credentials, keys, `.git` metadata) are strictly rejected with typed `UnsafePatchPathError`.
- **Destructive Command Blocking**: Model output containing destructive shell commands (e.g., `rm -rf`, `format`, `del /f`, piped web downloads, encoded commands) is flagged and rejected.
- **Payload & Bounded Limits (`PatchConfig`)**: Model input context is budgeted and fenced; structured output responses are bounded (max 64 KB payload, max 10 files, max 2,000 changed lines, max 512 KB per file modification).
- **System Prompt Separation**: Repository contents and execution logs are untrusted data placed inside fenced boundaries; they cannot modify the trusted system instructions or ORION policy.
- **Zero Autonomous Execution**: The model layer cannot directly execute tools, spawn subprocesses, modify files, or bypass the `ApprovalService`.

### Deterministic Fallback
Model failure must never halt or corrupt the deterministic SWE workflow. If the provider experiences timeouts, authentication failures, rate limits, connection errors, or produces malformed JSON, ORION automatically falls back to deterministic rule-based analysis, fix plans, and manual-review patch proposals, preserving error details in telemetry without leaking secrets.

### Current Limitations
- **Bounded Patch Proposals Only**: Phase 4 generates, validates, diffs, and approval-gates patch proposals; it does NOT directly apply modifications to disk or execute tools. Phase 5 handles controlled change implementation and verification.
- **No Autonomous Tool-Calling Loop**: Autonomous open-ended tool loops (`while model_requests_tools:`) are intentionally not implemented.
- **Hypothesis Status**: Model reasoning is treated as untrusted suggestions, not verified facts.
- **Defense-in-Depth**: Prompt injection defense mitigates context manipulation through fencing and bounded inspection, but does not claim mathematical impossibility of injection.

### Inference Configuration
| Variable | Description | Default |
| :--- | :--- | :--- |
| `ORION_MODEL_PROVIDER` | Active provider (`mock`, `alternate`, `openai`) | `mock` |
| `ORION_MODEL_NAME` | Model identifier | `gpt-4o` |
| `ORION_MODEL_BASE_URL` | Endpoint base URL | `https://api.openai.com/v1` |
| `ORION_MODEL_API_KEY` | Provider API key (never logged or exposed) | None |
| `ORION_MODEL_TIMEOUT` | Request timeout in seconds | `30.0` |
| `ORION_MODEL_TEMPERATURE` | Sampling temperature (0.0 to 2.0) | `0.0` |
| `ORION_MODEL_MAX_TOKENS` | Maximum token bound | Optional |

> [!NOTE]
> All automated tests execute deterministically against test doubles or in-memory transport adapters without external network access. Credentials are never written to disk, evidence, or responses.

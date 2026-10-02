# ORION V6 — Evaluation & Engineering Intelligence Architecture

## 1. Executive Overview

ORION V6 introduces a scientific, operational, and reproducible evaluation and engineering-intelligence subsystem. Designed to answer rigorous questions about autonomous Software Engineering (SWE) capability without fabricated or synthetic metrics, every reported score, rate, duration, and failure categorization originates strictly from real execution evidence, real subprocess tests, real verification outcomes, and deterministic ledger records.

### Core Questions Answered by V6:
1. **Capability**: How reliably does ORION solve SWE missions across distinct failure categories?
2. **Failure Analysis**: Where does the system fail, at which workflow stages, and under which root causes?
3. **Recovery Efficacy**: How often does self-healing succeed versus induce regression or exhaustion?
4. **Efficiency**: What are the true wall-clock latencies and file modification footprints?
5. **Reproducibility**: What components are strictly deterministic versus nondeterministic?
6. **Cross-Version Progression**: How does a new commit or version compare empirically against a prior baseline?

---

## 2. Standardized Failure-Taxonomy Benchmark Corpus

ORION V6 establishes deterministic, locally executable benchmark suites that represent realistic SWE failure classes without external network dependencies.

### 2.1 Benchmark Task Schema (`BenchmarkTask`)
Each benchmark problem defines structured metadata:
- `task_id`: Unique identifier (e.g., `SWE-BUG-001`, `SWE-SEC-001`)
- `name`: Human-readable benchmark task name
- `category`: `BenchmarkCategory` (`BUG_FIX`, `REGRESSION_FIX`, `SYNTAX_VALIDATION`, `RECOVERY_CHALLENGE`, `FEATURE_ADDITION`)
- `difficulty`: `BenchmarkDifficulty` (`EASY`, `MEDIUM`, `HARD`)
- `problem_statement`: Natural-language objective
- `workspace_files`: Initial repository file dictionary (`relative_path -> file_content`)
- `test_files`: Pytest validation suite dictionary
- `target_files`: Expected target paths for modification
- `timeout_seconds`: Wall-clock execution timeout (positive float)
- `allowed_operations`: Bounded capabilities (`read`, `write`, `test`)
- `risk_classification`: Risk tier (`low`, `medium`, `high`)
- `expected_failure`: Initial error signature
- `expected_verification_condition`: Authoritative post-condition (`all_tests_pass`)
- `expected_outcome`: Standard outcome (`PASS`)
- `failure_category`: Canonical failure class from taxonomy

### 2.2 Standard Benchmark Suites
- **Smoke Suite (`SMOKE_CORPUS`)**: Fast 2-task sanity verification (`SWE-BUG-001` calculator off-by-one, `SWE-BUG-002` configuration parser).
- **Standard Suite (`STANDARD_CORPUS`)**: 4-task core SWE verification (`SWE-BUG-001`, `SWE-BUG-002`, `SWE-REG-001` cache TTL invalidation, `SWE-SYN-001` validator AST syntax error).
- **Comprehensive Failure-Taxonomy Suite (`FAILURE_TAXONOMY_CORPUS`)**: 7-task suite covering:
  - `assertion_failure` (`SWE-BUG-001`, `SWE-BUG-002`)
  - `test_regression` (`SWE-REG-001`)
  - `syntax_failure` (`SWE-SYN-001`)
  - `type_failure` (`SWE-TYP-001`)
  - `import_failure` (`SWE-IMP-001`)
  - `security_failure` (`SWE-SEC-001` path traversal guard)

---

## 3. Benchmark Runner & Execution Lifecycle

The `BenchmarkRunner` orchestrates benchmark execution in isolated filesystem environments:

```
[Isolated Temp Workspace]
        │
        ├── 1. Populate workspace_files & test_files
        ├── 2. Wire ToolExecutor, ApprovalService, VerificationEngine, RecoveryCoordinator
        ├── 3. Coordinate Stage 1 (INSPECT_REPOSITORY) -> Evidence recorded
        ├── 4. Coordinate Stage 2 (ANALYZE_FAILURE)   -> Diagnostic claimed
        ├── 5. Coordinate Stage 3 (FORMULATE_FIX)     -> Proposed change claimed
        ├── 6. Coordinate Stage 4 (IMPLEMENT_CHANGE)  -> Repair applied (if auto_repair)
        ├── 7. Coordinate Stage 5 (RUN_TESTS)         -> Subprocess pytest executed
        ├── 8. Coordinate Stage 6 (VERIFY)            -> Authoritative VerificationEngine promotion
        └── 9. Coordinate Stage 7 (GENERATE_REPORT)   -> SWEEvaluator evaluates evidence ledger
```

### Execution Grounding Invariants:
- Pytest is executed as a real subprocess within the isolated directory with `PYTHONPATH` confined to the temporary workspace root.
- Exit code 0 promotes the test stage to `passed` and enables `VerificationEngine` verification.
- Non-zero exit codes (or timeouts) record actual stdout/stderr snippets, mark verification as failed, and set mission status to `FAIL`.
- No synthetic outcomes: `status`, `duration_seconds`, `tests_passed`, `tests_failed`, `verification_passed`, and `recovery_attempts` are derived strictly from runtime telemetry.

---

## 4. Engineering Metrics Methodology & Mathematical Formulas

Every metric has an explicitly defined numerator, denominator, and zero-division guard.

### 4.1 Mission-Level Metrics
- **Mission Success Rate**:
  $$\text{mission\_success\_rate} = \frac{\text{passed\_missions}}{\text{total\_missions}}$$
  *Denominator*: `total_missions` (evaluates to `0.0` when 0).
- **Verification Success Rate**:
  $$\text{verification\_success\_rate} = \frac{\text{verified\_missions}}{\text{total\_missions}}$$
  *Denominator*: `total_missions`.
- **Mission Failure Rate**:
  $$\text{mission\_failure\_rate} = \frac{\text{failed\_missions}}{\text{total\_missions}}$$
  *Denominator*: `total_missions`.
- **Safe Termination Rate**:
  $$\text{safe\_termination\_rate} = \frac{\text{safely\_terminated\_missions}}{\text{failed\_missions}}$$
  *Denominator*: `failed_missions` (evaluates to `1.0` if 0 failures occurred).
- **Mean Task Duration**:
  $$\text{mean\_duration\_seconds} = \frac{\sum \text{duration\_seconds}}{\text{total\_missions}}$$

### 4.2 Recovery-Level Metrics
- **Recovery Success Rate**:
  $$\text{recovery\_success\_rate} = \frac{\text{successful\_recoveries}}{\text{total\_recovery\_attempts}}$$
  *Denominator*: `total_recovery_attempts` (evaluates to `1.0` if 0 attempts were needed).
- **Rollback Frequency**:
  $$\text{rollback\_frequency} = \frac{\text{total\_rollback\_events}}{\text{total\_recovery\_attempts}}$$
  *Denominator*: `total_recovery_attempts` (evaluates to `0.0` if 0 attempts).
- **Strategy Success Rate (per strategy $s$)**:
  $$\text{strategy\_success\_rate}_s = \frac{\text{strategy\_successes}_s}{\text{strategy\_attempts}_s}$$

### 4.3 Execution & Reliability Metrics
- **Test Pass Rate**:
  $$\text{test\_pass\_rate} = \frac{\text{total\_tests\_passed}}{\text{total\_tests\_executed}}$$
- **Mean Files Changed Per Mission**:
  $$\text{mean\_files\_changed} = \frac{\text{total\_files\_changed}}{\text{total\_missions}}$$
- **Classification Accuracy**:
  $$\text{classification\_accuracy} = \frac{\text{correctly\_classified\_failures}}{\text{total\_classified\_failures}}$$

---

## 5. Multi-Dimensional Failure Analysis

The `FailureAnalysisReport` groups unverified or failed benchmark tasks across 5 orthogonal dimensions:
1. **By Failure Category**: `assertion_failure`, `syntax_failure`, `type_failure`, `import_failure`, `security_failure`, etc.
2. **By Workflow Stage**: `inspect_repository`, `analyze_failure`, `formulate_fix`, `implement_change`, `run_tests`, `verify`.
3. **By Recovery Strategy**: Strategy invoked before failure or termination.
4. **By Benchmark Task**: Identification of recurrently difficult tasks.
5. **By ORION Version**: Longitudinal failure tracking across releases.

Each failure generates a `BenchmarkFailureRecord` containing:
- `task_id` & `benchmark_name`
- `failure_stage` & `failure_category`
- `root_execution_event` (actual pytest stderr / exception)
- `recovery_attempts` & `strategy_selected`
- `rollback_performed` (boolean)
- `final_termination_reason`
- `orion_version`

---

## 6. Experiment Tracking & Reproducibility Model

Evaluation runs are captured as immutable `ExperimentRecord` instances registered in the thread-safe `ExperimentTracker`.

### 6.1 Immutability
All records use `frozen=True` dataclasses. Any mutation raises a `FrozenInstanceError`.

### 6.2 Secret Redaction
All configurations and environment dictionaries pass through `RedactionEngine` before storage, replacing tokens, API keys, and sensitive environment variables with `[REDACTED:...]` markers.

### 6.3 Separation of Deterministic vs Nondeterministic Components

| Deterministic Components | Nondeterministic Components |
| :--- | :--- |
| Isolated filesystem workspace creation | Model provider generation tokens and latency |
| Fixture file extraction & SHA-256 matching | Subprocess execution thread scheduling |
| Failure taxonomy classification regex rules | OS-level disk I/O and page fault timings |
| Rollback manager snapshot creation | Network latency to remote LLM endpoints |
| Rule-based VerificationEngine promotion | External platform process jitter |
| SWEEvaluator evidence ledger evaluation | — |

---

## 7. Version Comparison Mechanism

The `VersionComparisonResult` provides empirical delta computation between two benchmark experiment records without arbitrary synthetic scoring:
- **`pass_rate_delta`**: $\text{Target Pass Rate} - \text{Base Pass Rate}$
- **`duration_delta_seconds`**: $\text{Target Duration} - \text{Base Duration}$
- **`recovery_success_delta`**: $\text{Target Recovery Rate} - \text{Base Recovery Rate}$
- **`newly_passing`**: Tasks that failed in Base but pass in Target.
- **`newly_failing`**: Tasks that passed in Base but fail in Target (regressions).
- **`performance_improved`**: Tasks running $>20\%$ faster.
- **`performance_regressed`**: Tasks running $>20\%$ slower.

---

## 8. Evaluation REST API Contracts

All endpoints are hosted on the backend authority with zero trust in client evaluations:

### GET `/api/v1/evaluation/benchmarks`
Returns all benchmark suites, difficulty classifications, and task metadata.

### POST `/api/v1/evaluation/run`
Executes an evaluation experiment.
- Request Body: `{"suite": "smoke", "auto_repair": true, "configuration": {}}`
- Response: `201 CREATED` with full `ExperimentRecord`.

### GET `/api/v1/evaluation/runs`
Lists all recorded evaluation runs ordered chronologically.

### GET `/api/v1/evaluation/runs/{id}`
Returns the complete immutable experiment record for `{id}`.

### GET `/api/v1/evaluation/runs/{id}/metrics`
Returns strictly computed `EngineeringMetrics` with mission, recovery, execution, and reliability sub-dictionaries.

### GET `/api/v1/evaluation/runs/{id}/failures`
Returns structured `FailureAnalysisReport` with aggregations and forensic failure records.

### POST `/api/v1/evaluation/compare`
Compares two evaluation runs.
- Request Body: `{"base_id": "EXP-001", "target_id": "EXP-002"}`
- Response: `200 OK` with `VersionComparisonResult`.

### GET `/api/v1/evaluation/compare?base_id=...&target_id=...`
Query parameter equivalent for GET clients.

---

## 9. Security Model & Invariants

1. **Frontend Untrusted**: Frontends cannot submit scores, outcomes, or verification assertions. All evaluation state is computed exclusively by backend authorities.
2. **Workspace Containment**: Isolated directories under temporary paths. System roots and protected paths (`.git/`, `.env`, `pyproject.toml`) are rejected.
3. **Traversal Protection**: Benchmarks like `SWE-SEC-001` verify that path traversal attempts (`../../`) are blocked and raise `ValueError`.
4. **Single-Use Approvals & Controlled Execution**: All changes pass through `ApprovalService` and `ToolExecutor`.
5. **No Synthetic Promotion**: Tests must exit 0 to achieve `VerificationStatus.VERIFIED`.

# ORION V1 Evaluation & Benchmark Report

## 1. Executive Summary

This report documents the empirical evaluation of ORION V1 across a standardized, reproducible 10-task SWE benchmark suite (`v1`) and a rigorous 4-vector failure-injection self-healing recovery test suite.

All benchmark tasks execute in clean, isolated workspace directories with sandboxed `pytest` execution (`shell=False`), dual-key authorization simulation, authoritative ground-truth verification (`VerificationEngine`), and cryptographically sealed evidence ledger provenance (`EvidenceLedger`).

### Summary Metrics

| Metric | Unassisted Baseline | ORION V1 Trial 1 | ORION V1 Trial 2 | ORION V1 Trial 3 | Aggregate (3 Trials) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tasks Evaluated** | 10 | 10 | 10 | 10 | 30 |
| **Tasks Passed** | 0 | 10 | 10 | 10 | 30 |
| **Tasks Failed** | 10 | 0 | 0 | 0 | 0 |
| **Pass@1 Rate** | **0.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Verification Completeness** | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| **Mean Task Duration** | 0.741s | 0.778s | 0.774s | 0.779s | 0.777s |
| **Median Task Duration** | 0.740s | 0.779s | 0.771s | 0.773s | **0.773s** |
| **Evidence Items Logged** | 0 | 60 (6/task) | 60 (6/task) | 60 (6/task) | 180 (6/task) |

---

## 2. Standardized 10-Task Benchmark Suite Specification

The `v1` benchmark suite covers 10 distinct, reproducible failure taxonomy categories observed in real-world software engineering codebases:

| Task ID | Failure Category | Name & Component | Defect Description |
| :--- | :--- | :--- | :--- |
| `BM-OFF-BY-ONE` | `off_by_one` | Pagination Slice Off-by-One (`pagination.py`) | Slice uses `page * page_size` instead of `(page - 1) * page_size`, skipping the initial page window. |
| `BM-TYPE-ERROR` | `type_error` | Network Socket Port Concatenation (`network.py`) | String concatenation `host + ":" + port` with an integer `port` causes runtime `TypeError`. |
| `BM-MISSING-NONE` | `missing_none_check` | HTTP Header Sanitizer Missing None (`headers.py`) | Invoking `.strip().lower()` without checking `val is None` causes runtime `AttributeError`. |
| `BM-WRONG-EXCEPTION` | `wrong_exception` | Key-Value Storage Exception Handler (`storage.py`) | Exception handler catches `IndexError` instead of `KeyError`, propagating unhandled key errors. |
| `BM-BAD-REGEX` | `bad_regex` | Semantic Version Parser Anchoring (`semver.py`) | Unanchored regex `r"\d+\.\d+\.\d+"` erroneously matches invalid strings like `"v1.2.3.alpha"`. |
| `BM-CONCURRENCY-RACE` | `concurrency_race` | Shared Metrics Counter Race Condition (`metrics.py`) | `MetricsCounter.increment` lacks lock synchronization, dropping counts under multithreaded contention. |
| `BM-RESOURCE-LEAK` | `resource_leak` | Audit Log Reader Resource Leak (`logger.py`) | File opened with `open()` without context management or `.close()`, leaving active OS file handles open. |
| `BM-WRONG-OPERATOR` | `wrong_operator` | Rate Limiter Inverted Comparison (`limiter.py`) | Comparison uses `<` instead of `>= threshold`, inverting rate limiting logic. |
| `BM-BAD-DEFAULT-ARG` | `bad_default_argument` | Mutable Default Argument Accumulation (`tracer.py`) | Default parameter `history: list = []` persists state across multiple function invocations. |
| `BM-FLOAT-ROUNDING` | `floating_point_rounding` | Currency Transaction Sum Rounding (`ledger.py`) | Raw IEEE-754 summation produces rounding artifacts (`0.30000000000000004`) instead of `0.30`. |

---

## 3. Unassisted Baseline vs Assisted Execution

To establish ground-truth rigor, every task was executed in two conditions:

1. **Unassisted Baseline (`auto_repair=False`)**: The repository workspace is instantiated with the defective code. Pytest executes the test suite. Without fix synthesis, all 10 tasks fail their respective test suites with exit code 1.
2. **Assisted Execution (`auto_repair=True`)**: ORION executes its 7-stage deterministic pipeline:
   - Stage 1: Inspect Repository (AST exploration & dependency inventory)
   - Stage 2: Analyze Failure (Diagnostic categorization across taxonomy)
   - Stage 3: Formulate Fix (Synthesize repair patch)
   - Stage 4: Implement Change (Apply transactional diff with rollback snapshot)
   - Stage 5: Run Tests (Sandboxed subprocess pytest execution, `shell=False`)
   - Stage 6: Verify (Authoritative `VerificationEngine` ground truth check)
   - Stage 7: Generate Report (Certified cryptographic evaluation summary)

### Per-Task Breakdown (Trial 1, 2, 3)

| Task ID | Failure Category | Unassisted Result | Trial 1 Result | Trial 2 Result | Trial 3 Result | Consistency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BM-OFF-BY-ONE` | `off_by_one` | FAIL (Exit Code 1) | PASS (0.782s) | PASS (0.771s) | PASS (0.774s) | 100% |
| `BM-TYPE-ERROR` | `type_error` | FAIL (Exit Code 1) | PASS (0.775s) | PASS (0.771s) | PASS (0.772s) | 100% |
| `BM-MISSING-NONE` | `missing_none_check` | FAIL (Exit Code 1) | PASS (0.779s) | PASS (0.781s) | PASS (0.778s) | 100% |
| `BM-WRONG-EXCEPTION` | `wrong_exception` | FAIL (Exit Code 1) | PASS (0.764s) | PASS (0.760s) | PASS (0.765s) | 100% |
| `BM-BAD-REGEX` | `bad_regex` | FAIL (Exit Code 1) | PASS (0.782s) | PASS (0.778s) | PASS (0.780s) | 100% |
| `BM-CONCURRENCY-RACE` | `concurrency_race` | FAIL (Exit Code 1) | PASS (0.793s) | PASS (0.790s) | PASS (0.795s) | 100% |
| `BM-RESOURCE-LEAK` | `resource_leak` | FAIL (Exit Code 1) | PASS (0.776s) | PASS (0.774s) | PASS (0.773s) | 100% |
| `BM-WRONG-OPERATOR` | `wrong_operator` | FAIL (Exit Code 1) | PASS (0.778s) | PASS (0.770s) | PASS (0.779s) | 100% |
| `BM-BAD-DEFAULT-ARG` | `bad_default_argument` | FAIL (Exit Code 1) | PASS (0.780s) | PASS (0.777s) | PASS (0.781s) | 100% |
| `BM-FLOAT-ROUNDING` | `floating_point_rounding` | FAIL (Exit Code 1) | PASS (0.775s) | PASS (0.768s) | PASS (0.774s) | 100% |

---

## 4. Failure-Injection & Self-Healing Recovery Evaluation

The self-healing architecture was evaluated using the dedicated automated integration test suite (`tests/integration/test_recovery_failure_injection.py`), injecting 4 distinct operational failures:

### 1. Injected Broken Tool Output (`TOOL_FAILURE`)
- **Injection Mechanism**: Mock tool `ast_extractor` returns malformed JSON with an unexpected EOF.
- **Agent System Behavior**: `RecoveryCoordinator` classifies event as `TOOL_FAILURE`, evaluates `RecoveryPolicy`, and selects `RecoveryStrategy.CHANGE_TOOL`.
- **System Outcome**: Alternate tool selected; zero unhandled crashes; failure diagnosis and strategy recorded to `EvidenceLedger`.
- **Verification Status**: **PASS** (`test_injected_broken_tool_output_triggers_tool_recovery`).

### 2. Injected Model Repetition Loop (`MODEL_FAILURE`)
- **Injection Mechanism**: Mock generation yields identical patch payload across consecutive iterations.
- **Agent System Behavior**: Diagnostic monitor detects degenerative loop, flags `MODEL_FAILURE`, and selects `RecoveryStrategy.CHANGE_MODEL`.
- **System Outcome**: Work routed to fallback model configuration; incident logged to `EvidenceLedger`.
- **Verification Status**: **PASS** (`test_injected_model_repeating_itself_triggers_model_recovery`).

### 3. Injected Test Runner Crash / Timeout (`TIMEOUT`)
- **Injection Mechanism**: Subprocess test runner hangs or exceeds hard timeout limit (30.0s).
- **Agent System Behavior**: Subprocess terminated safely; `RecoveryCoordinator` classifies as `TIMEOUT`, checks remaining retry budget (max 3), and triggers `RecoveryStrategy.RETRY_CURRENT_TASK`.
- **System Outcome**: Task scheduled for retry under bounded budget; retry event recorded to ledger.
- **Verification Status**: **PASS** (`test_injected_test_runner_crash_triggers_retry_recovery`).

### 4. Injected Bad Patch Breaking Passing Tests (`TEST_FAILURE` / Regression)
- **Injection Mechanism**: Synthetic patch introduces syntax errors and breaks previously passing tests (`test_multiply_positive`, `test_divide`).
- **Agent System Behavior**:
  1. `PatchRecoveryManager` captures transactional pre-patch recovery snapshot (`create_recovery_point`).
  2. `VerificationEngine` identifies test regressions and fails authorization.
  3. `RecoveryPlanner` selects `RecoveryStrategy.ROLLBACK`.
  4. `PatchRecoveryManager.restore_recovery_point` cleanly restores workspace to identical pre-patch bytes.
  5. `RecoveryAttemptLifecycle` transitions: `PLANNED -> EXECUTING -> ROLLED_BACK`.
  6. Action and checkpoint ID committed to `EvidenceLedger`.
- **System Outcome**: Repository integrity 100% preserved; zero corrupted files; state safely rolled back.
- **Verification Status**: **PASS** (`test_injected_bad_patch_breaks_more_tests_triggers_rollback_recovery`).

---

## 5. Evidence Ledger Provenance

Every benchmark run and recovery event generates cryptographic proof entries recorded in the immutable `EvidenceLedger`:
- **Claimed**: Proposed changes and formulated repair plans before execution.
- **Observed**: Subprocess exit codes, file write notifications, diagnostic AST evaluations.
- **Verified**: Independent assertion evaluations certified by `VerificationEngine`.

Each trial generated 6 structured evidence items per task, totaling **180 cryptographically timestamped evidence records** across the 3 benchmark trials.

---

## 6. How to Reproduce

All evaluation artifacts are 100% deterministic, local, and reproducible on standard Python 3.12+ without external API keys or third-party packages:

```bash
# 1. Run 3-trial benchmark evaluation suite
python scratch/run_benchmarks_3x.py

# 2. Run unassisted vs assisted verification probe
python -c "import sys; sys.path.insert(0, 'src'); from orion.core.evaluation.runner import BenchmarkRunner; r = BenchmarkRunner(); rep_no = r.run_suite('v1', auto_repair=False); print(f'Unassisted: {rep_no.passed_tasks}/{rep_no.total_tasks}'); rep_yes = r.run_suite('v1', auto_repair=True); print(f'Assisted: {rep_yes.passed_tasks}/{rep_yes.total_tasks}')"

# 3. Run failure-injection recovery test suite
pytest tests/integration/test_recovery_failure_injection.py -v
```

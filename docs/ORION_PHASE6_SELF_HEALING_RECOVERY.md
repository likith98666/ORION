# ORION V1.2 — Phase 6: Bounded Self-Healing Recovery Subsystem

## 1. Objective

Phase 6 implements a bounded, evidence-driven, security-preserving self-healing recovery subsystem for ORION's Software Engineering (SWE) workforce. 

In automated workflows, when an operation fails during controlled execution, testing, or authoritative verification, the system must not crash blindly, nor may it enter an unrestricted autonomous modification loop. Instead, Phase 6 provides a deterministic recovery loop that:
1. Deterministically classifies structured execution and test failures.
2. Selects conservative, policy-governed recovery strategies from a registered set.
3. Enforces an auditable, non-resettable budget across execution time, attempts, and disk mutations.
4. Executes rollbacks to verified pre-apply snapshots using Phase 5's `PatchRecoveryManager`.
5. Requires human operator approval via `ApprovalService` for any risky mutation or regeneration.
6. Re-executes tests under `ControlledExecutionAuthority` and demands verification from `VerificationEngine` as the sole authority for `VERIFIED` evidence.
7. Explicitly halts and terminates whenever budget is exhausted, policy rules are violated, or unrecoverable conditions are reached.

---

## 2. Architecture

The Phase 6 recovery subsystem is built directly upon the foundation established in Phases 1 through 5, preserving all trust boundaries and isolation guarantees. It does not introduce a parallel SWE stack or autonomous backdoors.

```
USER TASK
   │
   ▼
[ SWE Workflow: PLAN ➔ EXECUTE ➔ PATCH ➔ CONTROLLED TEST ➔ VERIFY ]
                                                              │
                                                        FAIL / ERROR
                                                              │
                                                              ▼
                                                   [ FailureClassifier ]
                                               (Deterministic 10 Categories)
                                                              │
                                                              ▼
                                                     [ RecoveryBudget ]
                                                  (Enforces Hard Bounds)
                                                              │
                                                              ▼
                                                     [ RecoveryPlanner ]
                                              (Applies Deterministic Policy)
                                                              │
                                                              ▼
                                                 [ Approval Verification ]
                                               (ApprovalService Governance)
                                                              │
                                                              ▼
                                              [ Strategy Execution Handler ]
                         ┌────────────────────┬───────────────┴───────────────┬────────────────────┐
                         │                    │                               │                    │
                         ▼                    ▼                               ▼                    ▼
                    RETRY_TEST      REFRESH_WORKSPACE_STATE           ROLLBACK            REGENERATE / MODIFY
                    (Rerun in         (Release locks,            (Restore pre-apply       (Bounded Synthesis via
                     sandbox)          sync disk state)              snapshot)            PatchApplicationAuth)
                         │                    │                               │                    │
                         └────────────────────┴───────────────┬───────────────┴────────────────────┘
                                                              │
                                                              ▼
                                                [ Controlled Re-Testing ]
                                              (ControlledExecutionAuthority)
                                                              │
                                                              ▼
                                                [ Authoritative Verification ]
                                                   (VerificationEngine)
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            │                                   │
                                            ▼                                   ▼
                                       [ VERIFIED ]                         [ FAILED ]
                                     (SUCCESS Report)             (Next Bounded Attempt or TERMINATE)
```

### Module Organization (`src/orion/core/swe/recovery/`)
- `classification.py`: Authoritative 10-category failure classifier mapping structured exceptions, exit codes, and verification outcomes.
- `strategies.py`: Registry and definitions for the 7 conservative recovery strategies.
- `budget.py`: Immutable, auditable budget tracking attempts, regenerations, test retries, model switches, execution seconds, and depth.
- `contracts.py`: Dataclasses and enums: `RecoveryAttemptState`, `RecoveryPlan`, `RollbackRecord`, `RecoveryAttempt`, `RecoveryAuditReport`.
- `policy.py`: Deterministic recovery policy enforcing strategy admissibility and preventing model overrides.
- `attempt.py`: Finite state machine enforcing legal lifecycle transitions with audit timestamps.
- `planner.py`: Policy-governed recovery planner synthesizing validated `RecoveryPlan` objects.
- `coordinator.py`: `SWERecoveryCoordinator` driving the bounded recovery cycle and emitting evidence into `EvidenceLedger`.
- `errors.py`: Typed error hierarchy (`Phase6RecoveryError`, `BudgetExhaustedError`, `RecoveryDepthExceededError`, `RecoveryPolicyViolationError`, etc.).

---

## 3. Failure Taxonomy

Authoritative failure classification is deterministic and cannot be overridden by model claims. The LLM may provide a `CLAIMED` diagnosis, but the deterministic classifier remains authoritative.

| Category | Description | Root Cause Evidence | Recoverable |
| :--- | :--- | :--- | :--- |
| `TEST_FAILURE` | Pytest subprocess exited non-zero or assertions failed. | Subprocess exit code, failed assertion strings in stdout/stderr. | Yes (Bounded) |
| `PATCH_APPLICATION_FAILURE` | Syntax error, missing target file, or disk write error during patch application. | File missing error, AST syntax error, or applier exception. | Yes (Rollback + Regen) |
| `STALE_STATE` | Concurrent workspace lock collision or pre-apply hash divergence. | Lock holder ID, stale SHA-256 hash detection. | Yes (Refresh / Rollback) |
| `VERIFICATION_FAILURE` | Output rejected by `VerificationEngine` (missing requirements/specifications). | Verification reason, unsatisfied requirements list. | Yes (Modify / Regen) |
| `TIMEOUT` | Subprocess execution exceeded hard bounded timeout. | Elapsed runtime > `bounded_timeout`, `TimeoutExpired`. | Yes (Retry / Modify) |
| `ENVIRONMENT_FAILURE` | Operating system permission error or missing binary. | `PermissionError`, missing tool binary. | Bounded (1 attempt max) |
| `DEPENDENCY_FAILURE` | Missing Python package or module in runtime environment. | `ModuleNotFoundError`, `ImportError`. | No (Operator required) |
| `WORKSPACE_INTEGRITY_FAILURE` | Post-apply SHA-256 mismatch, directory traversal attempt, or protected file mutation. | Hash divergence, path escape exception, protected path. | No (Terminates immediately) |
| `APPROVAL_FAILURE` | Required approval denied or revoked by human operator. | `ApprovalStatus.DENIED`, revoked request ID. | No (Terminates immediately) |
| `UNKNOWN_FAILURE` | Unclassified exception outside known invariants. | Unmapped exception details. | No (Terminates safely) |

---

## 4. Recovery Strategy Registry

Only strategies explicitly registered in `RecoveryStrategyRegistry` may be selected. Arbitrary strategies invented by LLM proposals are rejected.

| Strategy ID | Supported Failure Categories | Prerequisites | Risk Level | Approval Required | Handler Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RETRY_TEST` | `TEST_FAILURE`, `TIMEOUT` | Budget available, test target defined | LOW | No | Re-executes tests under `ControlledExecutionAuthority`. |
| `REFRESH_WORKSPACE_STATE` | `STALE_STATE`, `ENVIRONMENT_FAILURE` | Valid workspace root | LOW | No | Releases stale locks, inspects file tree readability. |
| `REGENERATE_PATCH` | `TEST_FAILURE`, `PATCH_APPLICATION_FAILURE`, `VERIFICATION_FAILURE` | Active cognitive service, workspace | HIGH | Yes | Synthesizes new patch proposal from first principles. |
| `MODIFY_PATCH` | `TEST_FAILURE`, `VERIFICATION_FAILURE`, `TIMEOUT` | Prior patch proposal available | HIGH | Yes | Synthesizes targeted delta to existing patch. |
| `ROLLBACK` | `PATCH_APPLICATION_FAILURE`, `STALE_STATE` | Active `PatchRecoveryPoint` snapshot | HIGH | Yes | Reverts workspace to pre-apply file hashes. |
| `CHANGE_MODEL` | `VERIFICATION_FAILURE`, `TEST_FAILURE` | Alternate registered provider available | HIGH | Yes | Reconfigures cognitive service with alternate model. |
| `TERMINATE` | All Categories | Always available | LOW | No | Halts recovery, records audit trail, marks failure. |

---

## 5. Recovery Budget Model

Recovery loops are strictly bounded by `RecoveryBudget`. Budgets are monotonic: attempts consume budget, and budget is never reset during execution.

### Default Conservative Constraints
- `max_total_attempts`: 3 attempts maximum
- `max_patch_regenerations`: 2 regenerations maximum
- `max_model_changes`: 1 model switch maximum
- `max_test_retries`: 2 test retries maximum
- `max_execution_seconds`: 300.0 seconds maximum
- `max_affected_files_total`: 10 unique files maximum
- `max_recovery_depth`: 3 nested iterations maximum

When any budget metric reaches zero, the coordinator immediately transitions to `TERMINATED`.

---

## 6. Recovery State Machine & Lifecycle

Each recovery iteration is captured as an auditable `RecoveryAttempt` with explicit state transitions:

```
                  ┌──────────────┐
                  │   PLANNED    │
                  └──────┬───────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
    ┌──────────────┐            ┌──────────────┐
    │  AUTHORIZED  │            │  EXECUTING   │
    └──────┬───────┘            └──────┬───────┘
           │                           │
           └─────────────┬─────────────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  RETESTING   │  │ ROLLED_BACK  │  │  TERMINATED  │
└──────┬───────┘  └──────────────┘  └──────────────┘
       │
       ▼
┌──────────────┐
│  VERIFYING   │
└──────┬───────┘
       │
       ├─────────────────────────┐
       ▼                         ▼
┌──────────────┐          ┌──────────────┐
│  SUCCEEDED   │          │    FAILED    │
└──────────────┘          └──────────────┘
```

Any invalid transition (such as jumping directly from `PLANNED` to `SUCCEEDED` or bypassing `AUTHORIZED` for high-risk operations) raises `InvalidRecoveryTransitionError`.

---

## 7. Security Boundaries & Invariants

Phase 6 strictly preserves all Phase 1–5 security guarantees:
1. **No Arbitrary Shell Execution**: Controlled tests are executed via `sys.executable -m pytest` with direct arguments, never through shell interpreters (`shell=False`).
2. **No Direct Filesystem Mutation**: The recovery planner and model reasoning have zero filesystem write authority. All disk mutations must proceed through `PatchValidator` and `PatchApplicationAuthority`.
3. **Workspace Containment**: Any attempt to write outside the workspace repository root (e.g., path traversal sequences like `../`) is blocked with `WorkspaceError` / `PatchApplicationError`.
4. **Mandatory Human-in-the-Loop Approval**: High-risk operations (`REGENERATE_PATCH`, `MODIFY_PATCH`, `ROLLBACK`, `CHANGE_MODEL`) require explicit approval from `ApprovalService`. Forged or unapproved requests are rejected with `UnapprovedPatchError`.
5. **No Infinite Autonomous Loops**: Maximum depth of 3 and hard budget ceilings prevent runaway loops.
6. **No Self-Authorization**: The agent cannot approve its own high-risk actions.

---

## 8. Provenance & Evidence Model

Every recovery iteration produces tamper-evident records stored in `EvidenceLedger`:
- `DIAGNOSTIC_RESULT`: Authoritative failure classification, root causes, and discrepancies.
- `PROPOSED_CHANGE`: Structured `RecoveryPlan` with rationale, strategy, and remaining budget.
- `RECOVERY_EVENT`: Execution record capturing strategy outcomes, elapsed time, and state transitions.
- `TEST_RESULT`: Subprocess exit code, stdout, stderr, and duration.
- `VERIFICATION_RESULT`: Authoritative verdict produced solely by `VerificationEngine`.

### Epistemic Hierarchy
- **`CLAIMED`**: LLM diagnoses, proposed fixes, confidence scores.
- **`OBSERVED`**: Real test execution results, tool return codes, disk hashes.
- **`VERIFIED`**: Authoritative verdicts promoted strictly by `VerificationEngine`.

---

## 9. Rollback Architecture

Rollbacks reuse Phase 5's `PatchRecoveryManager`:
1. Before any patch application, `create_recovery_point` captures SHA-256 hashes and contents of all target files.
2. If recovery strategy `ROLLBACK` is triggered, `restore_recovery_point` restores the exact pre-mutation contents and removes newly created files.
3. Post-rollback hashes are computed and verified against pre-state hashes.
4. An immutable `RollbackRecord` is produced documenting restored files, hashes, timestamp, and status.
5. If rollback fails, the attempt transitions to `FAILED` and raises `RollbackExecutionError`.

---

## 10. Model Change Protocol

When repeated verification failures occur under a model, the policy permits `CHANGE_MODEL`:
- Can only select from pre-registered providers in `ModelProviderRegistry`.
- Cannot accept arbitrary model names or API keys from untrusted model outputs.
- Bounded to a maximum of 1 model change per mission budget.
- Creates a new `SWECognitiveService` instance bound to the alternate provider.

---

## 11. Test Matrix

The Phase 6 test suite (`tests/unit/core/swe/test_self_healing_recovery.py`) provides 100% coverage across 26 distinct scenarios:

| # | Test Scenario | Verified Behavior |
| :--- | :--- | :--- |
| 1 | `test_01_failure_classification_categories` | Validates deterministic classification across all failure categories. |
| 2 | `test_02_deterministic_classification_overrules_model_claim` | Confirms deterministic evidence overrules conflicting LLM claims. |
| 3 | `test_03_valid_recovery_strategy_selection` | Verifies policy maps classifications to correct strategies. |
| 4 | `test_04_invalid_strategy_rejection` | Prohibits illegal strategy assignments for unrecoverable failures. |
| 5 | `test_05_budget_consumption` | Validates audit tracking and monotonic budget consumption. |
| 6 | `test_06_budget_exhaustion` | Confirms loop termination when budget attempts are exhausted. |
| 7 | `test_07_maximum_recovery_depth` | Enforces hard ceiling on recursive recovery depth. |
| 8 | `test_08_retry_test_recovery` | Real execution retry verifies transient test recovery and success. |
| 9 | `test_09_patch_regeneration_recovery` | Executes patch regeneration cycle via cognitive service. |
| 10 | `test_10_model_change_recovery` | Switches cognitive provider to registered alternate model. |
| 11 | `test_11_rollback_recovery` | Restores corrupted file to clean pre-apply snapshot. |
| 12 | `test_12_rollback_failure_handling` | Safely handles missing recovery points without crashing. |
| 13 | `test_13_stale_workspace_recovery` | Resolves stale lock collision and resynchronizes workspace state. |
| 14 | `test_14_verification_failure_recovery` | Handles `VerificationEngine` rejection through bounded repair. |
| 15 | `test_15_repeated_failure_termination` | Escalates strategy on repeated failures and halts at terminal bound. |
| 16 | `test_16_approval_required_recovery` | Validates approval requirements for high-risk strategies. |
| 17 | `test_17_approval_rejection_termination` | Immediately terminates recovery when operator denies approval. |
| 18 | `test_18_arbitrary_strategy_rejection` | Rejects unregistered autonomous strategy identifiers. |
| 19 | `test_19_model_attempting_unauthorized_recovery` | Prevents untrusted candidate strategy from bypassing policy. |
| 20 | `test_20_filesystem_boundary_enforcement` | Blocks path traversal attempts outside workspace root. |
| 21 | `test_21_evidence_generation` | Confirms structured evidence records produced in `EvidenceLedger`. |
| 22 | `test_22_lifecycle_transition_validation` | Enforces state machine transitions and rejects illegal skips. |
| 23 | `test_23_recovery_provenance_audit_trail` | Generates comprehensive JSON-serializable `RecoveryAuditReport`. |
| 24 | `test_24_successful_self_healing_e2e` | End-to-end: failure ➔ diagnose ➔ patch ➔ verify ➔ `SUCCEEDED`. |
| 25 | `test_25_unsuccessful_bounded_recovery_e2e` | End-to-end: integrity failure ➔ deterministic `TERMINATED`. |
| 26 | `test_26_recovery_budget_exhaustion_e2e` | End-to-end: persistent failure ➔ budget exhausted ➔ bounded halt. |

---

## 12. Quality Gate Verification

Prior to release, all quality gates were executed and verified clean:

```bash
# 1. Phase 6 Dedicated Suite (26 tests)
.\.venv\Scripts\python.exe -m pytest tests/unit/core/swe/test_self_healing_recovery.py -v
# Result: 26 passed in 15.21s

# 2. SWE Subsystem Suite (178 tests: 152 Phase 1-5 + 26 Phase 6)
.\.venv\Scripts\python.exe -m pytest tests/unit/core/swe/ -q
# Result: 178 passed in 28.22s

# 3. Full Repository Suite (1,264 tests: 1,237 baseline + 26 Phase 6 + 1 skip)
.\.venv\Scripts\python.exe -m pytest -q
# Result: 1263 passed, 1 skipped in 45.79s

# 4. Strict Type Safety Check
.\.venv\Scripts\python.exe -m mypy src/orion/core/swe/
# Result: Success: no issues found in 39 source files

# 5. Ruff Linter & Formatter Check
.\.venv\Scripts\python.exe -m ruff check src/orion/core/swe/recovery/ src/orion/core/swe/__init__.py src/orion/core/swe/execution/applier.py src/orion/core/swe/execution/recovery.py tests/unit/core/swe/test_self_healing_recovery.py
# Result: All checks passed!

# 6. Git Diff Whitespace / Check
git diff --check
# Result: Clean (exit code 0)
```

---

## 13. Scope Boundaries & What Phase 6 Does NOT Implement

To preserve system simplicity and security integrity, Phase 6 explicitly does **NOT** implement:
- **Raft or Distributed Consensus**: ORION operates as a single-node deterministic workforce; distributed consensus algorithms are outside scope.
- **WebAssembly (WASM)**: Sandboxing is achieved through workspace isolation and subprocess control.
- **Kubernetes / Container Orchestration**: Workspaces are isolated via filesystem containment; no container orchestration daemon is introduced.
- **Unrestricted Autonomous Modification Loops**: All repair cycles are strictly bounded by hard budget limits.
- **Infinite Recovery**: When budget or strategy limits are reached, the system terminates deterministically.
- **Autonomous Approval Bypass**: No agent or heuristic may bypass human operator approval for high-risk operations.
- **Frontend / UI Implementation**: Only clean backend contracts and telemetry representations are exposed for future UI integration.

---

## 14. Future V2 Directions

Future enhancements beyond V1.2 may consider:
1. **Adaptive Failure Clustering**: Historical cross-task clustering of flaky test cases to adjust retry policies dynamically.
2. **Multi-Model Consensus Proposing**: Gathering candidate fix proposals from multiple models before submitting to `PatchValidator`.
3. **Interactive Human Approval UI**: Web-based visual diff review dashboard consuming `RecoveryAuditReport` metadata.

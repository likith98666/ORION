# ORION V1.1 — PHASE 5: CONTROLLED PATCH APPLICATION + EXECUTION + VERIFICATION

## 1. Architectural Context & Security Perimeter

ORION V1.1 Phase 5 establishes the authoritative execution bridge in the Autonomous Software Engineering (SWE) lifecycle. While Phases 1–4 enabled real model integration, prompt injection sanitization, failure diagnosis, and bounded patch synthesis, Phase 5 provides the deterministic execution boundary that guarantees models cannot modify files or execute code arbitrarily.

```text
MODEL (Untrusted LLM Output)
         │
         ▼
[CLAIMED] PatchProposal
         │
         ▼
PatchValidator (Syntax & Safety Check)
         │
         ▼
ApprovalService (High-Risk Governance Gate)
         │
         ▼ (Human/Security Authorized)
[AUTHORIZED] PatchApprovalPackage
         │
         ▼
PatchApplicationAuthority (WorkspaceLock + Snapshot + Atomic Apply)
         │
         ▼
[OBSERVED] AppliedOperationRecord & File Changes
         │
         ▼
ControlledExecutionAuthority (Restricted pytest Subprocess)
         │
         ▼
[OBSERVED] ControlledTestResult
         │
         ▼
VerificationEngine / PatchVerificationAuthority
         │
         ▼
[VERIFIED] Authoritative Success  OR  [OBSERVED] Failure -> RecoveryCoordinator
```

### Core Security Guarantees
1. **Unilateral Model Prohibitions**: Model proposals cannot write directly to disk or invoke subprocesses.
2. **Strict Approval Gating**: Patches cannot be applied without an `APPROVED` status from `ApprovalService`.
3. **Execution ID Context Binding**: Approvals are cryptographically and deterministically bound to specific agents, executions, and proposal hashes.
4. **Workspace Confinement**: Modifying files or running commands outside the workspace root is structurally impossible.
5. **No Model Self-Verification**: The model cannot mark its own patches as `VERIFIED`. Only the deterministic `VerificationEngine` promotes evidence from `OBSERVED` to `VERIFIED`.

---

## 2. PatchExecutionState State Machine & Valid Transitions

Patch execution is managed by a strict 13-state deterministic lifecycle machine (`PatchExecutionLifecycle`) with validated immutable transitions:

```text
       PROPOSED
          │
          ▼
      VALIDATED
          │
          ▼
   PENDING_APPROVAL
          │
          ▼
      AUTHORIZED
          │
          ▼
       APPLYING ──────────────┐ (Failure)
          │                   ▼
          │           PARTIALLY_APPLIED
          │                   │
          │                   ▼
          │               RECOVERING
          │              /          \
          ▼             ▼            ▼
       APPLIED      RECOVERED   RECOVERY_FAILED
          │
          ▼
      EXECUTING
       /     \
      ▼       ▼
  VERIFIED  FAILED
```

### Deterministic State Definitions
| State | Type | Description |
|---|---|---|
| `PROPOSED` | Initial | Raw patch proposal received from synthesizer |
| `VALIDATED` | Transient | Structural, path, and syntax validation passed |
| `PENDING_APPROVAL` | Hold | Approval request submitted to `ApprovalService` |
| `AUTHORIZED` | Gated | Approved by authoritative governance entity |
| `APPLYING` | Active | Workspace lock held, snapshot created, operations executing |
| `PARTIALLY_APPLIED` | Error | Mid-patch failure detected before completion |
| `RECOVERING` | Active | Rollback snapshot restoration in progress |
| `RECOVERED` | Terminal | Workspace cleanly restored to pre-apply snapshot |
| `RECOVERY_FAILED` | Terminal | Critical failure during snapshot rollback |
| `APPLIED` | Active | All file mutations applied and post-apply integrity verified |
| `EXECUTING` | Active | Controlled test execution running in workspace |
| `VERIFIED` | Terminal | Output verified by `VerificationEngine` with test exit code 0 |
| `FAILED` | Terminal | Tests failed, timed out, or requirements unfulfilled |

---

## 3. Pre-Apply Validation Authority & Invariant Enforcement

Before any mutation is permitted on the filesystem, `PatchApplicationAuthority.verify_approval_integrity()` performs non-bypassable pre-checks:

1. **Type & State Validation**: Verifies `package` is an instance of `PatchApprovalPackage` and `is_approved` is `True`.
2. **Authoritative Ledger Query**: Queries `ApprovalService.get_request(package.request_id)` directly from the repository. Denied or missing requests raise `RevokedApprovalError` or `UnapprovedPatchError`.
3. **Expiration (Stale Check)**: Confirms `now() <= stored_request.expires_at`. Expired approvals raise `StaleApprovalError`.
4. **Agent Binding Check**: Asserts `stored_request.agent_id == package.agent_id`. Mismatches raise `ApprovalIntegrityError`.
5. **Execution Context Binding**: Asserts `stored_request.execution_id == execution_id`. Mismatches raise `ApprovalIntegrityError`.
6. **Proposal Integrity**: Recomputes SHA-256 hash of the proposal's normalized content against the approved hash to detect tampering after approval.

---

## 4. Path Sanitization, Workspace Containment, and Protected Files

Every file path within patch operations is evaluated by `_sanitize_and_validate_path()`:

1. **Resolution & Normalization**: Strips leading slashes, resolves relative components against `workspace.repository_root`, and verifies the resolved path begins with the repository root.
2. **Path Traversal Defense**: Rejects `..`, embedded null bytes (`\0`), and drive escape sequences on Windows (`C:..`).
3. **Protected File Blocklist**: Rejects any operation targeting:
   - Secret/environment files: `.env`, `.env.*`, `credentials.json`, `secrets.yaml`
   - Version control metadata: `.git`, `.git/**`
   - Key and certificate files: `id_rsa`, `*.pem`, `*.key`, `*.crt`

---

## 5. Optimistic Pre-Check Pipeline

To maintain atomicity and avoid partial mutations, `PatchApplicationAuthority` executes an optimistic dry-run across all operations before disk writes:

```text
For each operation:
  ├── CREATE_FILE: Check target does not already exist
  ├── MODIFY_FILE: Check target exists and SHA-256 matches expected_hash
  └── DELETE_FILE: Check target exists and SHA-256 matches expected_hash
```

If any operation fails pre-check, the entire application aborts immediately with `PatchExecutionState.FAILED` and disk remains untouched.

---

## 6. Workspace Locking & Concurrency Control

Concurrent patch applications on the same workspace are prevented via `WorkspaceLockManager`:

- **Per-Workspace Mutual Exclusion**: Locks are keyed by `workspace.workspace_id`.
- **Reentrant Execution**: The same `execution_id` can re-enter safely (e.g., nested sub-stages).
- **Collision Protection**: If another execution attempts application on a locked workspace, `WorkspaceLockedError` is raised immediately.
- **Context Management**: RAII-style `with lock_mgr.acquire_context(workspace_id, execution_id):` guarantees release on normal exit or exception.

---

## 7. Pre-Apply Snapshot Architecture & Hash Guarantees

Before writing, `PatchRecoveryManager` captures a `PatchRecoveryPoint`:

- **Affected File Snapshots**: For every file targeted by `MODIFY_FILE` or `DELETE_FILE`, records:
  - `path`: Normalized relative path
  - `content`: Complete UTF-8 text
  - `sha256`: Hexadecimal SHA-256 hash
  - `exists`: `True`
- **Creation Tracking**: For `CREATE_FILE`, records `exists: False`.
- **Snapshot Immutability**: Encapsulated in frozen dataclasses (`FileSnapshot`, `PatchRecoveryPoint`).

---

## 8. Atomic Patch Application Algorithm

```python
with lock_manager.acquire(workspace_id, execution_id):
    # 1. Verify approval integrity & expiration
    # 2. Pre-validate and sanitize all paths
    # 3. Optimistic pre-checks (hash matching, existence)
    # 4. Create Pre-Apply Recovery Snapshot
    # 5. Apply mutations sequentially:
    try:
        for op in operations:
            if op.CREATE_FILE: target.write_text(op.new_content)
            elif op.MODIFY_FILE: target.write_text(op.new_content)
            elif op.DELETE_FILE: target.unlink()
            record_operation(op)
    except Exception as exc:
        restore_snapshot(recovery_point)
        transition_to(RECOVERED)
        raise
```

---

## 9. Deterministic Rollback & Recovery Mechanism

If a mid-patch error occurs (e.g. disk quota, permission fault):
1. State transitions to `PARTIALLY_APPLIED`, then `RECOVERING`.
2. `PatchRecoveryManager.restore_recovery_point()` iterates through the snapshot dictionary:
   - For `exists=True`: Restores original content and verifies SHA-256 hash.
   - For `exists=False`: Deletes any newly created file that was partially written.
3. State transitions to `RECOVERED` if clean, or `RECOVERY_FAILED` if unrecoverable.
4. An `OBSERVED` `EvidenceCategory.RECOVERY_EVENT` entry is permanently appended to the `EvidenceLedger`.

---

## 10. Post-Apply Integrity Verification

Immediately following physical application, `verify_post_apply_integrity()` inspects the filesystem:

1. **Existence Verification**: Verifies `CREATE_FILE` and `MODIFY_FILE` paths exist on disk; verifies `DELETE_FILE` paths do not exist.
2. **Syntax Compilation Check**: Validates that all modified `.py` files parse cleanly under Python's `ast.parse()`.
3. **Hash Mismatch Handling**: If post-apply disk state differs from expected contents, automatic rollback is triggered.

---

## 11. Controlled Test Execution & Subprocess Isolation

`ControlledExecutionAuthority` governs execution of verification tests:

- **Allowlisted Binary**: Only allows `pytest` (using the active virtualenv Python executable).
- **Workspace Confinement**: `cwd` is pinned strictly to `workspace.repository_root`.
- **`shell=False`**: Process creation uses explicit argument vectors `[sys.executable, "-m", "pytest", ...]` to eliminate shell injection risks.
- **Environment Sanitization**: Strips dangerous process variables (`LD_PRELOAD`, `PYTHONPATH`, shell overrides) while retaining essential system paths.
- **Timeout Bounding**: Enforces deterministic timeouts (`subprocess.TimeoutExpired`), terminating stalled test processes and reporting status `'timeout'`.

---

## 12. VerificationEngine Integration & Evidence Level Promotion

Phase 5 enforces ORION's fundamental epistemic rule:
> **Models produce CLAIMED evidence. Tool runs produce OBSERVED evidence. Only VerificationEngine creates VERIFIED evidence.**

When `PatchVerificationAuthority.verify_execution()` evaluates an SWE run:
1. Validates `application_result.status == PatchExecutionState.APPLIED`.
2. Validates `test_result.passed == True` and `test_result.exit_code == 0`.
3. Evaluates test output against expected requirement specifications via `VerificationEngine.verify_output()`.
4. On success: Records `EvidenceLevel.VERIFIED` under `EvidenceCategory.VERIFICATION_RESULT` and transitions to `PatchExecutionState.VERIFIED`.
5. On failure: Records `EvidenceLevel.OBSERVED` failure, transitions to `PatchExecutionState.FAILED`, and constructs a structured `Failure` object for `RecoveryCoordinator`.

---

## 13. Structured Failure Recovery Outcome Architecture

When execution or verification fails:
- Constructs `Failure(failure_type=FailureType.VERIFICATION_FAILURE | TIMEOUT, message=...)`.
- Returns `Phase5ExecutionOutcome` containing full diagnostic context (`application_result`, `integrity_result`, `test_result`, `verification_result`).
- Supplies structured diagnostics to `RecoveryCoordinator` so Phase 6+ recovery loops have deterministic causal evidence.

---

## 14. Trust Boundary Breakdown & Security Architecture

| Actor / Component | Trust Level | Capabilities | Restrictions |
|---|---|---|---|
| **LLM Provider / Synthesizer** | UNTRUSTED | Emits structured JSON fix proposal | Cannot modify files or run commands |
| **PatchValidator** | DETERMINISTIC | Validates schema, syntax, path sanity | Cannot apply changes |
| **ApprovalService** | GOVERNANCE | Grants cryptographic authorization | Cannot execute patches directly |
| **PatchApplicationAuthority** | AUTHORITATIVE | Applies mutations with snapshot & lock | Only accepts valid `APPROVED` packages |
| **ControlledExecutionAuthority** | ISOLATED | Executes allowlisted pytest subprocess | Confined to workspace, `shell=False` |
| **VerificationEngine** | AUTHORITATIVE | Verifies output & creates `VERIFIED` evidence | Independent of model claims |

---

## 15. End-to-End SWE Workflow Integration

Phase 5 completes the 7-stage deterministic workflow in `SWEWorkflowCoordinator`:

1. `INSPECT_REPOSITORY`: Enumerate and inspect code repository.
2. `ANALYZE_FAILURE`: Diagnoses failing tests within context boundaries.
3. `FORMULATE_FIX` & `SYNTHESIZE_PATCH`: Formulates fix and synthesizes patch proposal.
4. `REQUEST_PATCH_APPROVAL`: Submits proposal to `ApprovalService`.
5. `IMPLEMENT_CHANGE`: `coordinator.apply_approved_patch()` applies patch atomically.
6. `RUN_TESTS`: `coordinator.run_controlled_tests()` executes isolated test suite.
7. `VERIFY`: `coordinator.verify_patch_execution()` certifies fix with `VerificationEngine`.
8. `GENERATE_REPORT`: Deterministically produces `SWEReport` with status `verified_success`.

---

## 16. Test Matrix & Verification Evidence

All 30 deterministic test scenarios pass with zero regressions:

| Test Case | Objective | Result |
|---|---|---|
| `test_valid_approved_patch_application` | Valid approved patch applies cleanly & logs evidence | PASSED |
| `test_unapproved_patch_rejected` | Unapproved patch (PENDING) is rejected | PASSED |
| `test_revoked_approval_rejected` | Denied/revoked approval is rejected | PASSED |
| `test_stale_approval_rejected` | Expired approval is rejected | PASSED |
| `test_modified_after_approval_patch_rejected` | Tampered patch package is rejected | PASSED |
| `test_wrong_workspace_rejected` | Path escaping workspace boundary is rejected | PASSED |
| `test_path_traversal_rejected` | Path traversal sequence (`..`) is rejected | PASSED |
| `test_protected_file_rejected[.env]` | Protected `.env` write is rejected | PASSED |
| `test_protected_file_rejected[.env.production]` | Protected `.env.production` write is rejected | PASSED |
| `test_protected_file_rejected[credentials.json]` | Protected credentials write is rejected | PASSED |
| `test_protected_file_rejected[.git/config]` | Protected git config write is rejected | PASSED |
| `test_protected_file_rejected[id_rsa]` | Protected SSH key write is rejected | PASSED |
| `test_protected_file_rejected[cert.pem]` | Protected certificate write is rejected | PASSED |
| `test_protected_file_rejected[secret.key]` | Protected key write is rejected | PASSED |
| `test_concurrent_application_rejected_and_serialized` | Workspace lock prevents concurrent application | PASSED |
| `test_successful_create_file` | CREATE_FILE writes file and verifies hash | PASSED |
| `test_successful_modify_file` | MODIFY_FILE updates file and verifies hash | PASSED |
| `test_successful_delete_file` | DELETE_FILE cleanly removes file | PASSED |
| `test_application_failure_handling` | Pre-check failure fails cleanly without crash | PASSED |
| `test_partial_application_and_rollback` | Mid-patch failure triggers rollback to snapshot | PASSED |
| `test_unexpected_filesystem_modification_hash_mismatch` | Stale expected hash is rejected | PASSED |
| `test_test_timeout_handling` | Test timeout terminates process & sets status | PASSED |
| `test_non_zero_test_exit_code` | Failing tests report non-zero exit code | PASSED |
| `test_successful_verification` | VerificationEngine issues VERIFIED evidence | PASSED |
| `test_failed_verification` | Verification failure does not promote to VERIFIED | PASSED |
| `test_model_attempting_unauthorized_execution` | Raw model proposal cannot bypass approval | PASSED |
| `test_arbitrary_shell_command_rejection` | Arbitrary commands/traversal in runner rejected | PASSED |
| `test_workspace_escape_rejection` | Runner rejects targets outside workspace | PASSED |
| `test_phase5_state_machine_transitions` | Full state machine transitions and invalid states | PASSED |
| `test_end_to_end_phase5_swe_workflow` | Complete end-to-end SWE mission verified | PASSED |

### Regression Baseline Confirmation
- **Baseline**: 1,207 passed, 1 skipped
- **Phase 5 Added**: 30 passed
- **Total Regression**: 1,237 passed, 1 skipped, 0 failed
- **Linter & Type Status**: `ruff` clean, `mypy` clean, `git diff --check` clean.

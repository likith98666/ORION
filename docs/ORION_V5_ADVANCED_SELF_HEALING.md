# ORION V5 — Advanced Self-Healing

## Overview

ORION V5 elevates automated error mitigation from heuristic retry loops into an **Autonomous, Adaptive, and Strictly Bounded Self-Healing Architecture**. It equips ORION to systematically diagnose runtime errors, predict recovery blast radiuses before disk mutation, track historical strategy efficacy, execute surgical partial or full rollbacks, and adaptively select the optimal recovery path.

---

## 1. Architectural Components

### 1.1 13-Class Failure Taxonomy (`orion.core.recovery.advanced.taxonomy.FailureCategory`)
* **`SYNTAX_FAILURE`**: AST parsing and syntax errors with automated file and line extraction.
* **`ASSERTION_FAILURE`**: Test assertions and expectation mismatches.
* **`TYPE_FAILURE`**: Static type violations, mypy diagnostics, and incompatible types.
* **`IMPORT_FAILURE`**: Unresolved module references and missing imports.
* **`DEPENDENCY_FAILURE`**: Missing distributions, package version conflicts, and pip errors.
* **`ENVIRONMENT_FAILURE`**: Operating system or environment prerequisite discrepancies.
* **`TIMEOUT`**: Execution duration exceeding allocated budgets.
* **`RESOURCE_FAILURE`**: Memory exhaustion, file descriptor leaks, or disk space exhaustion.
* **`PATCH_CONFLICT`**: Unified diff application errors and hunk rejections.
* **`STALE_STATE`**: Cached artifacts or out-of-sync workspace state.
* **`SECURITY_FAILURE`**: Permission violations, unauthorized syscalls, and security boundaries.
* **`TEST_REGRESSION`**: Unintended regressions in previously passing test suites.
* **`UNKNOWN`**: Unclassified exceptions requiring conservative mitigation.

### 1.2 Deterministic Failure Classifier (`orion.core.recovery.advanced.taxonomy.FailureClassifier`)
* Scans exception tracebacks, compiler outputs, and pytest logs.
* Extracts root error messages, target file locations, and line numbers into structured `FailureDiagnosis` models.

### 1.3 Pre-Execution Recovery Simulation (`orion.core.recovery.advanced.simulation.RecoverySimulator`)
* Simulates candidate recovery operations in-memory before filesystem modifications.
* Evaluates safety against protected paths (`.git`, `pyproject.toml`, `.env`, system directories).
* Enforces timeout budget boundaries and calculates change blast radiuses.
* Flags repeated failed strategies with elevated risk scores.

### 1.4 Adaptive Recovery Memory (`orion.core.recovery.advanced.memory.AdaptiveRecoveryMemory`)
* Records execution cycle outcomes (diagnosis, strategy, success status, duration).
* Maintains historical failure context to avoid repeating failed recovery patterns.
* Computes empirical success rates and mean execution times for each strategy.

### 1.5 Intelligent Rollback Manager (`orion.core.recovery.advanced.rollback.IntelligentRollbackManager`)
* Captures immutable workspace snapshots using SHA-256 content hashes.
* Verifies workspace integrity and detects configuration drift.
* Performs full atomic rollbacks (restoring modified/deleted files and removing untracked artifacts).
* Performs surgical partial rollbacks targeted specifically at corrupted files.

### 1.6 Adaptive Recovery Planner (`orion.core.recovery.advanced.planner.AdaptiveRecoveryPlanner`)
* Mappable recovery paths:
  * `RESTORE_SNAPSHOT`
  * `TARGETED_PATCH_REPAIR`
  * `DEPENDENCY_REINSTALL`
  * `RETRY_WITH_BACKOFF`
  * `ISOLATE_TEST_CASE`
  * `ABORT_AND_ESCALATE`
* Escalates immediately to `ABORT_AND_ESCALATE` for security failures or budget exhaustion.
* Validates plans through simulation prior to execution.

---

## 2. API Endpoints

* `POST /api/v1/recovery/classify`: Categorizes raw stderr/stdout and returns structured diagnosis.
* `POST /api/v1/recovery/simulate`: Simulates recovery actions and returns risk assessments.
* `POST /api/v1/recovery/plan`: Formulates verified adaptive recovery plans.
* `GET /api/v1/recovery/metrics`: Returns empirical strategy success rates and execution durations.

---

## 3. Quality Verification

* **Unit & Integration Suite**: `tests/unit/recovery/test_advanced_self_healing.py` covering taxonomy classification, pre-execution simulation, historical memory tracking, atomic rollbacks, adaptive planning, and HTTP endpoints.
* **Type Safety & Style**: 100% compliant with `mypy` and `ruff`.

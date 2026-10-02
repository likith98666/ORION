# ORION Phase 9 — Evaluation & Benchmarking Architecture

## Overview

ORION Phase 9 implements an authoritative, standardized evaluation and benchmarking framework for autonomous software engineering. Built directly upon the Stage 1–8 foundations, Phase 9 provides objective, repeatable measurement of ORION's performance on real-world engineering tasks without relying on external third-party evaluation harnesses or synthetic claims.

---

## 1. Architectural Principles

1. **Deterministic & Objective**: Benchmark tasks are defined with concrete source trees, failing tests, and clear problem statements. Tasks pass only when authoritative verification passes (zero regressions, all tests passing).
2. **Strict Workspace Isolation**: Each benchmark task runs in its own temporary workspace. No task side effects can leak into adjacent tasks or the host system.
3. **Evidence-Ledger Grounded**: Metrics are not self-reported or synthetic; they are extracted from the immutable `EvidenceLedger` recorded by `SWEWorkflowCoordinator`.
4. **Certified Markdown & JSON Reporting**: Every benchmark run generates machine-readable JSON artifacts and human-readable Markdown scorecards including execution environments, Pass@1 rate, verification completeness, and recovery success rate.

---

## 2. Benchmark Corpus Taxonomy

The evaluation corpus categorizes engineering challenges into standardized categories and difficulty levels:

### Categories
* `BUG_FIX`: Discrete algorithmic or logic errors in source code.
* `REGRESSION_FIX`: Breakages introduced to previously functioning subsystems (e.g. cache TTL invalidation).
* `FEATURE_ADDITION`: Implementation of missing functionality according to a technical specification.
* `SECURITY_PATCH`: Remediation of security vulnerabilities or unsafe parameter handlings.
* `SYNTAX_ERROR`: Resolution of syntactical errors, malformed tokens, or broken module imports.

### Standard Tasks
* `SWE-BUG-001`: **Calculator Addition Offset** (Easy) — Fixing inverted arithmetic operation in calculation routine.
* `SWE-BUG-002`: **Config Parser Key Stripping** (Medium) — Fixing whitespace leakage in key-value configuration parser.
* `SWE-REG-001`: **Cache Expiration Check** (Medium) — Repairing incorrect cache invalidation comparator.
* `SWE-SYN-001`: **Module Import & Syntax Repair** (Easy) — Fixing syntax syntax error and unclosed parenthesis in string utility module.

---

## 3. Core Evaluation Components

### Data Models (`orion.core.evaluation.models`)
* `BenchmarkTask`: Immutable specification of a benchmark task including workspace files, test files, target files, and timeout bounds.
* `TaskRunResult`: Measured outcome of a single task execution (status, duration, tests passed/failed, verification outcome, recovery attempts, files changed).
* `BenchmarkReport`: Aggregate evaluation report computing `pass_at_1_rate`, `verification_completeness`, `recovery_success_rate`, and `mean_duration_seconds`.
* `get_system_environment_metadata()`: Captures OS, architecture, Python version, and execution timestamp to guarantee reproducibility.

### Execution Engine (`orion.core.evaluation.runner.BenchmarkRunner`)
* Automates full end-to-end task execution in isolated scratch workspaces.
* Drives `SWEWorkflowCoordinator` through all canonical stages (`INSPECT_REPOSITORY`, `ANALYZE_FAILURE`, `FORMULATE_FIX`, `IMPLEMENT_CHANGE`, `RUN_TESTS`, `VERIFY`, `GENERATE_REPORT`).
* Employs `VerificationEngine` and `EvidenceLedger` to ensure change traceability and verified test pass criteria.

### API Integration (`orion.api.server` & `orion.api.service`)
* `GET /api/v1/benchmarks`: Returns available suites (`standard`, `smoke`) and metadata for all corpus tasks.
* `POST /api/v1/benchmarks/run`: Executes the requested benchmark suite in a background thread or synchronous flow, saving artifacts to disk and returning certified metric payloads.

---

## 4. Verification and Quality Assurance

* **Unit & Integration Suite**: `tests/unit/evaluation/test_evaluation_benchmark.py` covering task validation, serialization, corpus integrity, environment capture, single task runner, suite execution, and API endpoints.
* **Zero Regression**: Integrated alongside all Phase 1–8 test suites without regression.

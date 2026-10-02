# ORION V4 — Advanced Multi-Agent Engineering

## Overview

ORION V4 evolves the execution model from a monolithic cognitive reasoning loop into an autonomous, specialized, and strictly bounded **Multi-Agent Engineering Workforce**. Rather than permitting a single agent prompt to inspect, edit, test, and verify without oversight, V4 divides software engineering responsibilities across dedicated roles operating under formal capability contracts, partitioned tool permissions, concurrent execution pipelines, independent multi-stage peer reviews, and evidence-driven conflict resolution.

---

## 1. Architectural Components

### 1.1 Canonical Workforce Roles & Permissions (`orion.core.agents.workforce.contracts`)
* **`ARCHITECT`**: High-level design decomposition and modular scoping (`READ_ONLY`). Allowed tools: `list_files`, `read_file`, `search_files`.
* **`INVESTIGATOR`**: Root cause analysis and fault localization (`READ_ONLY`). Allowed tools: `list_files`, `read_file`, `search_files`, `diff`.
* **`IMPLEMENTER`**: Patch engineering and code change formulation (`PROPOSE_PATCH`). Cannot modify disk directly. Allowed tools: `read_file`, `diff`.
* **`TESTER`**: Regression test authoring and controlled test execution (`EXECUTE_TESTS`). Allowed tools: `read_file`, `run_tests`.
* **`REVIEWER`**: Independent code quality, syntax, and security evaluation (`READ_ONLY`). Allowed tools: `read_file`, `diff`.
* **`SECURITY_ANALYST`**: Vulnerability detection, injection defense, and credential leak scanning (`READ_ONLY`). Allowed tools: `read_file`, `search_files`, `diff`.
* **`VERIFICATION_AUTHORITY`**: Authoritative promotion and regression oracle (`VERIFY`). Allowed tools: `read_file`, `run_tests`.

### 1.2 Workforce Contract Registry (`orion.core.agents.workforce.contracts.WorkforceContractRegistry`)
* Maintains active agent contracts with strictly bounded tool permissions and execution budgets.
* Enforces `WorkforcePermissionError` if an agent attempts any action beyond its assigned capability level.

### 1.3 Concurrent Task Orchestrator (`orion.core.agents.workforce.orchestrator.WorkforceOrchestrator`)
* Manages parallel task execution across independent roles (e.g. Investigation, Security Analysis, and Test Authoring executing concurrently).
* Provides thread safety, timeout bounding, and cooperative cancellation tokens.

### 1.4 Independent Multi-Stage Reviewer (`orion.core.agents.workforce.reviewer.IndependentReviewer`)
* Evaluates all proposals before capability token application:
  1. **Security Review**: Prohibits dangerous syscalls, raw shell executions, and credential access.
  2. **Code Quality Review**: Validates AST syntactical integrity.
  3. **Test Impact Review**: Ensures proposals include or exercise automated regression tests.
* Issues `APPROVED`, `CHANGES_REQUESTED`, or `REJECTED` verdicts.

### 1.5 Evidence-Driven Conflict Resolver (`orion.core.agents.workforce.conflict.AgentConflictResolver`)
* Arbitrates competing solutions (e.g., competing patches from multiple implementers).
* Computes composite scores combining confidence, evidence counts, and blast radius.
* Automatically routes to human review (`requires_human_approval=True`) whenever candidates are closely matched.

---

## 2. API Endpoints

* `GET /api/v1/workforce/roster`: Returns the active workforce agent contracts and permissions.
* `POST /api/v1/workforce/review`: Submits a proposed patch to the independent multi-stage reviewer.
* `POST /api/v1/workforce/resolve-conflict`: Evaluates competing agent proposals and returns an arbitration decision.

---

## 3. Quality Verification

* **Unit & Integration Suite**: `tests/unit/agents/test_workforce_engineering.py` covering tool authorization, roster management, concurrent orchestration, cancellation, security reviews, conflict arbitration, and REST endpoints.
* **Type Safety & Style**: 100% compliant with `mypy` and `ruff`.

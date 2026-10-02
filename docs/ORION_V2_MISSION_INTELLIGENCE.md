# ORION V2 — Advanced Mission Intelligence

## Overview

ORION V2 elevates the platform from an isolated task executor to an autonomous **mission-level software engineering operator**. In V2, complex objectives (e.g., *"Fix the authentication bug, add regression tests, update API documentation, and ensure integration tests pass"*) are programmatically decomposed into a strictly validated Directed Acyclic Graph (DAG) of sub-objectives, scheduled according to topological dependency readiness, bounded by explicit resource budgets, and tracked across an inspectable mission memory.

---

## 1. Architectural Components

### 1.1 Mission Task Graph (`orion.core.missions.graph.MissionTaskGraph`)
* **Mathematical Primitive**: Directed Acyclic Graph (DAG) with Kahn's algorithm cycle detection and topological sorting.
* **Task Lifecycle States**: `PENDING` -> `READY` -> `RUNNING` -> `SUCCEEDED` / `FAILED` / `BLOCKED` / `WAITING_APPROVAL` / `CANCELLED` / `VERIFIED`.
* **Cascade Invalidation**: If an upstream task fails or is cancelled, all downstream dependent tasks are automatically transitioned to `BLOCKED`.

### 1.2 Mission Planning & Validation (`orion.core.missions.planner`)
* **`PlanProposal`**: Candidate plan representation defining objectives and dependency declarations.
* **`PlanValidator`**: Deterministic gatekeeper verifying acyclicity, target existence, and resource budget positivity before any plan can be executed.
* **`MissionPlanner`**: Decomposes high-level compound objectives into structured tasks (root-cause diagnosis, fix formulation, regression test authoring, change implementation, test verification, documentation updates, and authoritative certification).

### 1.3 Scoped Mission Memory (`orion.core.missions.memory.MissionMemory`)
* **Scoping**: Strictly partitioned per `mission_id` preventing state cross-talk.
* **Bounded Capacity**: FIFO eviction when `max_entries` threshold is reached.
* **Typed Categorization**: Tracks `DECISION`, `ATTEMPT`, `FAILURE`, `PATCH`, `TEST_RESULT`, `APPROVAL`, `CONSTRAINT`, and `OBSERVATION`.
* **Audit & Lifecycle**: Supports full-text search, category filtering, explicit record deletion, and complete clearance.

### 1.4 Execution Engine (`orion.core.missions.engine.MissionExecutionEngine`)
* **Budget Guards**: Enforces maximum execution duration and attempt limits at both task and mission levels.
* **Cancellation & Resumption**: Responsive task cancellation cascading throughout the DAG.
* **Evidence Ledger Synchronization**: Records audit trails for every attempt and decision.

---

## 2. API Endpoints

* `POST /api/v1/missions/plan`: Decomposes a natural language compound objective into a validated V2 Mission Plan.
* `GET /api/v1/missions/{id}/graph`: Returns the task DAG, dependencies, ready tasks, and execution progress.
* `GET /api/v1/missions/{id}/memory`: Queries scoped, bounded memory records for an active or past mission.
* `POST /api/v1/missions/{id}/cancel`: Halts execution and transitions all active and pending tasks to `CANCELLED`.

---

## 3. Quality Certification

* **Unit & Integration Suite**: `tests/unit/mission/test_mission_intelligence.py` covering all lifecycle states, DAG operations, budget guards, memory eviction, and REST endpoints.
* **Type Safety & Style**: 100% compliant with `mypy` and `ruff`.

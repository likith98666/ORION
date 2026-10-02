# ORION V7 — Human-in-the-Loop & Collaborative Oversight

## 1. Executive Summary

ORION V7 transitions the autonomous execution substrate into a **Collaborative Oversight Architecture**. While ORION operates with high degrees of autonomy across planning, repository inspection, code synthesis, test execution, verification, and self-healing, complete autonomy without collaborative oversight can pose operational and safety risks.

The foundational principle of V7 is:
> **Maximum useful autonomy with appropriate human control.**

ORION V7 enables operators to actively steer, clarify, pause, resume, override, and provide continuous feedback on running missions without degrading deterministic verification or security boundaries.

---

## 2. Core Architectural Components

### 2.1 Interactive Clarifications (`ClarificationRequest` / `ClarificationStatus`)
When an agent or coordinator encounters ambiguous requirements, missing domain context, or conflicting objectives:
- It issues a structured `ClarificationRequest`.
- Attributes: `request_id`, `mission_id`, `task_id`, `question`, `context`, `options` (multiple choice), `default_choice`, `timeout_seconds`.
- Statuses: `PENDING`, `ANSWERED`, `TIMED_OUT`, `DEFAULT_ACCEPTED`.
- When answered by an operator, the resolution is injected as explicit steering guidance into the mission execution context.

### 2.2 Operator Interventions (`HumanIntervention` / `InterventionType`)
Provides authoritative, single-action human controls over running missions:
- **`PAUSE`**: Safely suspends execution at current stage boundaries without corrupting workspace state.
- **`RESUME`**: Unfreezes execution and resumes workflow progression.
- **`STEER`**: Injects priority constraints, hints, or instructions into the agent's prompt and planning queue.
- **`OVERRIDE_DECISION`**: Modifies an automated decision or strategy selection.
- **`FORCE_FAIL`**: Immediately terminates a runaway or undesired mission with human rationale.

### 2.3 Risk Tiers (`RiskTier`)
Classifies action blast radiuses to dictate human oversight requirements:
- **`LOW`**: Autonomous execution permitted (reading files, listing directory contents).
- **`MEDIUM`**: Asynchronous notification logged (non-critical file edits).
- **`HIGH`**: Synchronous human approval required before execution (modifying core dependencies, deleting files).
- **`CRITICAL`**: Dual-authorization or security review required (network egress, secret modifications).

### 2.4 Human Feedback Loop (`OperatorFeedback`)
Records structured post-mission or in-flight human reviews:
- `rating`: 1 to 5 numeric scale.
- `comments`: Operator assessment of execution quality.
- `corrections`: Explicit actionable guidance recorded into mission memory to refine future mission planning.

### 2.5 Central Authority (`HITLCoordinator`)
Thread-safe coordinator managing:
- Clarification registry and timeout handling.
- Intervention audit trail.
- Mission pause state sets.
- Steering queues.
- Feedback capture.

---

## 3. Collaborative Oversight REST API

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/hitl/clarifications/request` | Request human clarification on ambiguous task |
| `GET` | `/api/v1/hitl/clarifications` | Query clarifications (filtered by `mission_id`, `status`) |
| `POST` | `/api/v1/hitl/clarifications/{id}/respond` | Submit operator response to pending clarification |
| `POST` | `/api/v1/hitl/intervene` | Execute operator action (`pause`, `resume`, `steer`, `force_fail`) |
| `GET` | `/api/v1/hitl/interventions/{mission_id}` | Retrieve historical interventions for a mission |
| `POST` | `/api/v1/hitl/feedback` | Submit operator rating, comments, and corrections |
| `GET` | `/api/v1/hitl/feedback/{mission_id}` | Retrieve all feedback entries for a mission |

---

## 4. Security & Determinism Guarantees

1. **Untrusted Frontend Boundary**: Clarification answers and intervention requests pass through schema validation and cannot inject shell commands or bypass workspace containment.
2. **Deterministic Fallbacks**: Clarifications enforce bounded timeouts (`timeout_seconds`), falling back safely to `default_choice` or safe termination if an operator does not respond.
3. **Auditability**: Every human intervention is logged with an immutable UUID, operator identifier, timestamp, and rationale.

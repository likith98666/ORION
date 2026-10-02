# ORION — Autonomous AI Engineering Operating System

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1%2C395%20passed%20%7C%201%20skipped%20%7C%200%20failed-emerald.svg)]()
[![Type Checking](https://img.shields.io/badge/mypy-strict%20%7C%20234%20files%20clean-blue.svg)]()
[![Code Quality](https://img.shields.io/badge/ruff-clean-green.svg)]()
[![Runtime Dependencies](https://img.shields.io/badge/dependencies-0%20third--party%20runtime-purple.svg)]()
[![Security Invariants](https://img.shields.io/badge/security-20%2F20%20invariants%20verified-red.svg)]()
[![Release Status](https://img.shields.io/badge/release-V10%20Release%20Candidate-amber.svg)]()

> **ORION** is a coherent, secure, reproducible, production-grade **Autonomous AI Engineering Platform**. It plans, coordinates, executes, verifies, and self-heals complex technical work across real repositories through an authoritative, observable, and policy-governed multi-agent workforce.

---

## 1. Executive Summary

Unlike unconstrained chatbot loops that execute non-deterministic `while not solved` cycles, ORION operates like an industrial software engineering organization. Every engineering mission is strictly bound to deterministic task graphs, filesystem containment boundaries, dual-key human approvals, authoritative ground-truth verification, bounded recovery budgets, and an immutable forensic evidence ledger.

### End-to-End Pipeline
```text
MISSION
   ↓
UNDERSTANDING
   ↓
PLANNING (DAG)
   ↓
REPOSITORY INTELLIGENCE (AST & Blast Radius)
   ↓
MULTI-AGENT WORKFORCE (SWE, DX, VF, RC)
   ↓
PATCH GENERATION (Unified Diffs & Hash Locks)
   ↓
HUMAN OVERSIGHT (Clarification, Steering, Approval Gate)
   ↓
CONTROLLED EXECUTION (Workspace Containment)
   ↓
TESTING (Sandboxed Pytest Runner)
   ↓
VERIFICATION (Independent Ground-Truth Authority)
   ↓
SELF-HEALING (Taxonomy Diagnosis, Simulation, Bounded Recovery)
   ↓
POLICY ENFORCEMENT (Central Zero-Trust Guardrails)
   ↓
EVALUATION (Standardized Benchmarks & Engineering Metrics)
   ↓
OBSERVABILITY (Distributed Traces, Quantiles, Token Costing)
   ↓
EVIDENCE (Tiered Epistemic Ledger: Claimed / Observed / Verified)
   ↓
FINAL CERTIFIED RESULT (Cryptographic Report & Provenance Artifacts)
```

---

## 2. The 12 Observatories of the V10 Flagship Cockpit

The ORION Command Center provides a high-density, cinematic Obsidian interface unifying 12 technical observatories:

| # | Observatory | Focus & Real-Time Capabilities |
| :--- | :--- | :--- |
| **1** | **Mission Command Center** | Primary launchpad, status monitors, lifecycle state machine, and instant operator controls (Pause, Resume, Steer, Force Fail). |
| **2** | **Execution Topology** | Interactive DAG visualizer displaying task states, dependencies, specialist assignment, retries, and forensic node inspectors. |
| **3** | **Workforce Observatory** | Autonomous agent roster (SWE, Diagnostics, Verifier, Recovery Coordinator), role policies, capabilities, and conflict arbitrator. |
| **4** | **Repository Intelligence** | Static AST code-graph analyzer, cross-file symbol caller/callee mapper, change blast radius calculator, and token-bounded context optimizer. |
| **5** | **Patch Intelligence** | Structured code changes, modified files list, unified diff viewer, syntax validation, optimistic SHA-256 hash concurrency locking, and approval gating. |
| **6** | **Test & Verification** | Sandboxed pytest execution terminal, exit codes, assertion summaries, regression tracking, and formal ground-truth acceptance criteria verification. |
| **7** | **Recovery Observatory** | Self-healing failure classifier (6 formal categories), pre-flight non-destructive simulator, recovery budget gauges (attempts, runtime, patches), and rollback audit trail. |
| **8** | **Human Oversight (HITL)** | Real-time clarification queue, manual steering directive injector, pause/resume engine, operator feedback scoring (1–5 stars), and immutable intervention audit log. |
| **9** | **Policy & Security** | Authoritative security guardrails (`RULE-SEC-001`, `RULE-TOOL-001`, `RULE-BUDGET-001`, `RULE-VERIF-001`), live decision audit stream, and interactive policy evaluator simulator. |
| **10** | **Evaluation Lab** | Standardized benchmark suites (`standard`, `smoke`, `taxonomy`), automated experiment runner, metric history (Pass@1, recovery rate, latency), and differential regression comparator. |
| **11** | **Observability** | Distributed trace waterfall correlating Mission &rarr; Task &rarr; Agent &rarr; Tool/Model &rarr; Verification, latency quantiles ($P_{50}, P_{90}, P_{99}$), token costing, bottleneck detection, and autonomous system optimizations. |
| **12** | **Evidence Ledger** | Forensic append-only ledger tracking Claimed hypotheses, Observed tool outputs, and Verified ground truth with cryptographic hashes and audit provenance. |

---

## 3. The 20 Non-Negotiable Security Invariants

ORION enforces a strict, deterministic security perimeter:

1. **Frontend is untrusted:** Browser cannot mark stages or tests complete.
2. **Model output is untrusted:** Code changes require AST parse and approval before write.
3. **Repository contents are untrusted:** Prompt injection defense sanitizes all external text.
4. **Security decisions are deterministic:** Governed by `PolicyEngine`, not probabilistic models.
5. **Arbitrary shell execution forbidden:** Limited to sandboxed test execution (`shell=False`).
6. **Workspace containment mandatory:** Path traversal, UNC, symlinks, and junction escapes blocked.
7. **Protected paths remain protected:** `.git`, `.env`, keys, tokens blocked from mutation.
8. **ApprovalService is authoritative:** Dual-key approval gating for high-risk operations.
9. **Approval tokens are single-use:** Replay attacks are cryptographically rejected.
10. **Client cannot manufacture verification:** `VerificationEngine` is sole verification authority.
11. **Recovery remains bounded:** Hard caps on attempts ($\le 3$), time ($\le 120\text{s}$), and patches ($\le 2$).
12. **Secrets remain redacted:** Credentials and private keys scrubbed from output and spans.
13. **Evidence reflects actual events:** Append-only cryptographic ledger cannot be modified retroactively.
14. **Metrics reflect actual measurements:** Zero synthetic, fabricated, or randomized telemetry.
15. **Unknown unsafe states terminate safely:** Unhandled errors fail closed immediately.
16. **PolicyEngine is authoritative:** Every tool invocation evaluates central policy before execution.
17. **HITL is authoritative where human required:** Manual operator interventions override autonomous loops.
18. **Observability never leaks secrets:** All span attributes and payloads scrubbed.
19. **No fake telemetry:** Real SSE stream directly mirrors internal state machine transitions.
20. **No fake benchmark results:** Benchmark metrics reflect isolated physical subprocess execution.

---

## 4. Quickstart & Installation

### Prerequisites
- **Python 3.12** (Built 100% on standard library; zero third-party runtime dependencies)
- **Git 2.30+**

### Local Installation
```bash
# Clone the repository
git clone https://github.com/orion-ai/orion.git
cd ORION

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate       # Windows
# source .venv/bin/activate    # Linux / macOS

# Install development & testing tooling
pip install -e ".[dev]"

# Run full test suite (1,395 tests)
pytest -q

# Run strict type checking (234 source files)
mypy src

# Run code linter
ruff check .
```

### Launch the Cockpit
```bash
# Launch server bound to local workspace
python -m orion --host 127.0.0.1 --port 8000 --workspace .
```

Open your browser to:
- **Mission Command Center UI**: `http://127.0.0.1:8000/`
- **System Health Endpoint**: `http://127.0.0.1:8000/api/v1/health`
- **System Readiness Endpoint**: `http://127.0.0.1:8000/api/v1/readiness`

---

## 5. Docker Deployment

ORION includes a hardened, non-root, multi-stage production Docker container:

```bash
# Build and start container
docker compose up -d

# Verify container health
docker compose ps
curl http://localhost:8000/api/v1/health
```

### Container Security Properties
- **Non-root user:** Runs as UID/GID 1000 (`orion`).
- **Resource bounded:** Configurable memory and CPU limits.
- **Graceful shutdown:** Intercepts `SIGTERM` with clean task checkpointing.
- **Automated health check:** Queries `/api/v1/health` every 30s.

---

## 6. End-to-End Demonstration Mission

You can trigger a deterministic end-to-end mission directly via REST API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Analyze repository, formulate fix for failing tests, run controlled tests, and verify fix.",
    "workspace_path": "C:/Users/LIKITH/ORION",
    "execution_mode": "controlled"
  }'
```

Response:
```json
{
  "mission_id": "7f8b9c2a-1e3d-4c5b-9a8f-0e1d2c3b4a5f",
  "task_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "status": "initialized",
  "lifecycle_state": "RECEIVED",
  "objective": "Analyze repository, formulate fix for failing tests, run controlled tests, and verify fix."
}
```

Trigger pipeline execution:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/missions/7f8b9c2a-1e3d-4c5b-9a8f-0e1d2c3b4a5f/run
```

---

## 7. Verified Release Metrics & Quality Gates

| Quality Gate | Requirement | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Pytest Full Suite** | 100% Pass Rate | **1,395 passed, 1 skipped, 0 failed** in 89.5s | **PASS** |
| **Mypy Static Typing** | Strict, 0 Errors | **0 errors across 234 source files** | **PASS** |
| **Ruff Linter** | Clean | **All checks passed!** | **PASS** |
| **Git Diff Check** | Clean Working Tree | **0 whitespace / syntax errors** | **PASS** |
| **Standard Benchmark Pass@1** | $\ge 95\%$ | **100.0%** (4/4 passed) | **PASS** |
| **Taxonomy Benchmark Pass@1**| $\ge 95\%$ | **100.0%** (6/6 passed) | **PASS** |
| **Verification Authority Rate**| $100\%$ | **100.0%** (10/10 verified) | **PASS** |
| **Safe Termination Rate** | $100\%$ | **100.0%** (10/10 safe) | **PASS** |
| **Adversarial Security Suite** | 100% Pass Rate | **7 passed in 1.71s** | **PASS** |
| **Runtime Dependencies** | Standard Library Only | **0 third-party packages** | **PASS** |

---

## 8. Release Documentation Index

- [Architecture Specification](docs/ORION_ARCHITECTURE.md)
- [Distributed Execution Architecture Decision (ADR-001)](docs/ORION_DISTRIBUTED_EXECUTION_ARCHITECTURE_DECISION.md)
- [Final Benchmark & Evaluation Report](docs/ORION_V10_FINAL_BENCHMARK_REPORT.md)
- [API Contract Audit & Schema Specification](docs/ORION_V10_API_CONTRACT_AUDIT.md)
- [Security Audit & Adversarial Hardening Report](docs/ORION_V10_SECURITY_AUDIT.md)
- [V10 Final Release Candidate Certification](docs/ORION_V10_RELEASE_CANDIDATE.md)
- [V1–V9 Roadmap Reconciliation Audit](docs/ORION_V1_V9_ROADMAP_RECONCILIATION.md)

---

## 9. License

ORION is licensed under the MIT License. See [LICENSE](LICENSE) for details.

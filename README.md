# ORION // Autonomous AI Software Engineering Operating System

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1%2C438%20passed%20%7C%201%20skipped%20%7C%200%20failed-emerald.svg)]()
[![Type Checking](https://img.shields.io/badge/mypy-strict%20%7C%20238%20files%20clean-blue.svg)]()
[![Code Quality](https://img.shields.io/badge/ruff-clean-green.svg)]()
[![Runtime Dependencies](https://img.shields.io/badge/dependencies-0%20third--party%20runtime-purple.svg)]()
[![Security Invariants](https://img.shields.io/badge/security-20%2F20%20invariants%20verified-red.svg)]()
[![Release Status](https://img.shields.io/badge/release-v1.0.0%20GA-emerald.svg)]()

> **ORION** is an authoritative, secure, reproducible, production-grade **Autonomous Software Engineering Platform**. It coordinates specialized technical agents to plan, formulate, execute, verify, and self-heal complex code modifications across real repositories with zero third-party runtime dependencies.

---

## 1. Executive Summary

Unlike unconstrained chatbot loops that execute non-deterministic `while not solved` cycles, ORION operates like an industrial software engineering organization. Every engineering mission is strictly bound to deterministic task graphs, filesystem containment boundaries, dual-key human approvals, authoritative ground-truth verification, bounded recovery budgets, and an immutable forensic evidence ledger.

### End-to-End Pipeline
```text
MISSION DIRECTIVE
   ↓
UNDERSTANDING & AST EXPLORATION
   ↓
PLANNING (DAG Decomposer)
   ↓
REPOSITORY INTELLIGENCE (AST & Blast Radius)
   ↓
MULTI-AGENT WORKFORCE (SWE, DX, VF, RC)
   ↓
PATCH GENERATION (Unified Diffs & SHA-256 Locks)
   ↓
HUMAN OVERSIGHT (Clarification, Steering, Approval Gate)
   ↓
CONTROLLED EXECUTION (Workspace Containment)
   ↓
TESTING (Sandboxed Pytest Runner, shell=False)
   ↓
VERIFICATION (Authoritative VerificationEngine Ground Truth)
   ↓
SELF-HEALING (Taxonomy Diagnosis, Simulation, Bounded Recovery)
   ↓
POLICY ENFORCEMENT (Central Zero-Trust Guardrails)
   ↓
EVALUATION (10-Task Standardized SWE Benchmark Suite)
   ↓
OBSERVABILITY (Distributed Spans, Quantiles, Token Costing)
   ↓
EVIDENCE LEDGER (Claimed / Observed / Verified Epistemic Tiers)
   ↓
FINAL CERTIFIED RESULT (Cryptographic Report & Forensic Provenance)
```

---

## 2. Core Technical Observatories

The ORION Command Center provides a cinematic Obsidian interface unifying 12 technical observatories:

| # | Observatory | Focus & Real-Time Capabilities |
| :--- | :--- | :--- |
| **1** | **Mission Command Center** | Primary launchpad, status monitors, lifecycle state machine, and instant operator controls (Pause, Resume, Steer, Force Fail). |
| **2** | **Execution Topology** | Interactive DAG visualizer displaying task states, dependencies, specialist assignment, retries, and forensic node inspectors. |
| **3** | **Workforce Observatory** | Autonomous agent roster (SWE, Diagnostics, Verifier, Recovery Coordinator), role policies, capabilities, and conflict arbitrator. |
| **4** | **Repository Intelligence** | Static AST code-graph analyzer, cross-file symbol caller/callee mapper, change blast radius calculator, and token-bounded context optimizer. |
| **5** | **Patch Intelligence** | Structured code changes, modified files list, unified diff viewer, syntax validation, optimistic SHA-256 hash concurrency locking, and approval gating. |
| **6** | **Test & Verification** | Sandboxed pytest execution terminal, exit codes, assertion summaries, regression tracking, and formal ground-truth acceptance criteria verification. |
| **7** | **Recovery Observatory** | Self-healing failure classifier, pre-flight non-destructive simulator, recovery budget gauges (attempts, runtime, patches), and rollback audit trail. |
| **8** | **Human Oversight (HITL)** | Real-time clarification queue, manual steering directive injector, pause/resume engine, operator feedback scoring, and immutable intervention audit log. |
| **9** | **Policy & Security** | Authoritative security guardrails (`RULE-SEC-001` through `RULE-TOOL-001`), live decision audit stream, and interactive policy evaluator simulator. |
| **10** | **Evaluation Lab** | Standardized 10-task benchmark suite, automated experiment runner, metric history (Pass@1, recovery rate, latency), and differential regression comparator. |
| **11** | **Observability** | Distributed trace waterfall correlating Mission &rarr; Task &rarr; Agent &rarr; Tool/Model &rarr; Verification, latency quantiles ($P_{50}, P_{90}, P_{99}$), token costing, and bottleneck detection. |
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

# Run full test suite (1,438 tests)
pytest -q

# Run strict type checking (238 source files)
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

## 5. Verified Release Metrics & Quality Gates

| Quality Gate | Requirement | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Pytest Full Suite** | 100% Pass Rate | **1,438 passed, 1 skipped, 0 failed** in 104.65s | **PASS** |
| **Mypy Static Typing** | Strict, 0 Errors | **0 errors across 238 source files** | **PASS** |
| **Ruff Linter** | Clean | **All checks passed!** | **PASS** |
| **10-Task SWE Benchmark Pass@1** | $\ge 95\%$ | **100.0%** (30/30 across 3 trials; 0.773s median) | **PASS** |
| **Unassisted Baseline** | Ground Truth Defect | **0.0%** (0/10 passed without fix) | **PASS** |
| **Failure-Injection Recovery Suite** | 100% Pass Rate | **4/4 injected failure modes handled cleanly** | **PASS** |
| **Security Threat Model Suite** | 100% Negative Pass Rate | **8/8 threat vectors blocked** | **PASS** |
| **Verification Authority Rate** | 100% Ground Truth | **100.0%** (all runs certified by `VerificationEngine`) | **PASS** |
| **Runtime Dependencies** | Standard Library Only | **0 third-party runtime packages** | **PASS** |

---

## 6. Documentation Index

- [System Architecture](ARCHITECTURE.md)
- [Security Policy & Invariants](SECURITY.md)
- [Threat Model Specification](docs/THREAT_MODEL.md)
- [Empirical Benchmark & Evaluation Report](docs/EVALUATION.md)
- [Demonstration Walkthrough Guide](docs/DEMO_GUIDE.md)
- [REST API Reference](docs/API.md)
- [Changelog](CHANGELOG.md)

---

## 7. License

ORION is licensed under the MIT License. See [LICENSE](LICENSE) for details.

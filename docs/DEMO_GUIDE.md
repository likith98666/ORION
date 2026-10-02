# ORION — Autonomous Software Engineering Demo Guide

This guide provides a step-by-step walkthrough for demonstrating ORION to technical leaders, senior engineers, and recruiters.

---

## 1. Demo Narrative: What Sets ORION Apart

Most AI coding demonstrations show a chatbot producing a code snippet and hoping it works. 

**ORION is fundamentally different**:
* It acts as a **controlled, observable engineering workforce**.
* It enforces **workspace boundary containment** — no arbitrary shell or host escapes.
* It uses **deterministic stage gates** — each stage has strict tool and mutation permissions.
* It separates knowledge into **Claimed**, **Observed**, and **Verified** tiers.
* It provides **authoritative verification** — a passing test alone is NOT sufficient for mission completion.
* It handles **failures transparently** through an automated `RecoveryCoordinator`.

---

## 2. Setting Up the Demo Environment

### Step 1: Launch the Pre-Flight Validator
```bash
python scripts/validate_environment.py
```
*Expected Output*: All 5 pre-flight checks (Python, Git, Workspace I/O, Subprocess Security, Static Assets) report `[PASS]`.

### Step 2: Start the Mission Command Center
```bash
python -m orion --host 127.0.0.1 --port 8000 --workspace .
```
The console will display the cybernetic telemetry startup banner and report the active endpoints:
```text
======================================================================
  ORION — Autonomous AI Execution Platform v1.0.0
  Flagship: Autonomous Software Engineering
======================================================================
  HTTP Server : http://127.0.0.1:8000
  Workspace   : C:\Users\LIKITH\ORION
  Health Check: http://127.0.0.1:8000/api/v1/health
  UI Console  : http://127.0.0.1:8000/
======================================================================
```

### Step 3: Open the Mission Command Center
Navigate to:
```text
http://127.0.0.1:8000/
```

---

## 3. Walkthrough 1: The Canonical 7-Stage SWE Mission

### Objective: Repair a Failing Unit Test in a Managed Repository
1. On the UI, observe the **Active Mission** hero panel showing:
   * Mission ID and Active Workspace
   * Real-time Stepper displaying the 7 stages
   * Telemetry badges (Engine Status: `ONLINE`, Uptime, Active Missions)
2. Click **"Execute Pipeline"** in the top action bar (or click "Next Stage" to step through manually).
3. Watch the interactive workflow stepper illuminate stage-by-stage:
   * **Stage 1: Inspect Repository**: Scans files, examines directory hierarchy, records repository state.
   * **Stage 2: Analyze Failure**: Executes targeted test runner in an isolated subprocess, captures stack trace and reproduces bug.
   * **Stage 3: Formulate Fix**: Records a structured `ProposedFixPlan` dataclass instance detailing target files, intended modification, and constraints.
   * **Stage 4: Implement Change**: Generates clean patch, checks file hash for concurrency safety, requests human approval for high-risk write, and applies change.
   * **Stage 5: Run Tests**: Executes unit test runner in subprocess; captures exit code 0 and passing test count.
   * **Stage 6: Verify**: Authoritatively certifies requirements using the `VerificationEngine`.
   * **Stage 7: Generate Report**: Compiles the complete evidence ledger and executes deterministic evaluation.
4. Switch to the **"Evidence Explorer"** tab:
   * Click **"Verified"** filter: see the authoritative `VerificationResult` entry.
   * Click **"Observed"** filter: inspect raw tool outputs, command results, and hashes.
   * Click **"Claimed"** filter: see the agent's diagnostic hypothesis and proposed fix plan.
5. Switch to the **"Diff Viewer"** tab:
   * Review the green/red unified diff showing the exact lines added and removed.
6. Switch to the **"Certified Report"** tab:
   * Review the final report summary, the 6 evaluation criteria (`PASS`), and the immutable verification stamp.

---

## 4. Walkthrough 2: Failure Recovery & Transparency

### Objective: Demonstrate That ORION Recovers Without Erasing History
1. Run the multi-attempt recovery scenario:
```bash
.\.venv\Scripts\python.exe -m pytest tests/benchmarks/test_swe_benchmarks.py -k test_benchmark_multi_attempt_recovery_cycle -v
```
2. Explain the architectural significance:
   * **Attempt 1**: The agent applies an incorrect fix that still fails the test suite.
   * **Failure Detection**: `VerificationEngine` flags the failure.
   * **Recovery Activation**: `VerificationFailureAdapter` transforms the result into a formal `Failure` object and hands it to `RecoveryCoordinator`.
   * **Recovery Action**: The coordinator selects a retry strategy and resets the stage to re-formulate.
   * **Attempt 2**: The agent applies the corrected fix and tests pass.
   * **Immutable Audit Trail**: The evidence ledger preserves **BOTH** Attempt 1 (failed) and Attempt 2 (succeeded). Attempt 1 is **NEVER** silently overwritten.

---

## 5. Walkthrough 3: Defense-in-Depth Security Sandbox

### Objective: Demonstrate Workspace Isolation and Protection
1. Run the security validation suite:
```bash
.\.venv\Scripts\python.exe -m pytest tests/unit/security/test_swe_security_suite.py -v
```
2. Key points to highlight to reviewers:
   * **Path Traversal Rejection**: Tools reject relative `../../` and absolute paths outside the workspace boundary (`PathOutsideWorkspaceError`).
   * **Protected Files**: Protected files like `.env`, `.git`, `.ssh`, and secret tokens are guarded from reading and writing.
   * **Secret Redaction**: Any accidental secret pattern in metadata (`api_key`, `token`, `password`) is automatically replaced with `[REDACTED]`.
   * **Human Approval Gating**: High-risk operations (`write_file`, `apply_change`) are structurally blocked unless an authorized approval token is provided.
   * **No Shell Access**: Subprocesses execute with `shell=False`, preventing command injection vulnerabilities.

---

## 6. Interview Talking Points: Why ORION is 10/10 Engineering

* **Deterministic Autonomy**: Instead of letting an LLM run wild in an infinite loop, ORION bounds autonomy within a strictly typed 7-stage task graph.
* **Separation of Concerns**: Tools execute $\neq$ Task succeeds. Test passes $\neq$ Fix verified. Verification requires formal criteria certified by an independent engine.
* **Zero Runtime Dependencies**: The entire core platform, REST API, and static server run on pure Python 3.12 standard library, guaranteeing exceptional portability, zero supply-chain risk, and high reliability.
* **Observable & Traceable**: Every action links to `request_id`, `trace_id`, `task_id`, `execution_id`, and `agent_id`.

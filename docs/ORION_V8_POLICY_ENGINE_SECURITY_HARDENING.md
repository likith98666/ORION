# ORION V8 — Autonomous Security Hardening & Central Policy Engine

## 1. Overview and Core Philosophy

ORION V8 implements the centralized Policy Engine and autonomous security hardening layer as specified in `docs/24_policy_engine_architecture.md`, `docs/08_security_architecture.md`, and `docs/43_ai_safety_architecture.md`.

In autonomous AI systems capable of self-directed planning, multi-agent delegation, dynamic tool invocation, and terminal execution, security cannot simply be an external firewall. The Policy Engine provides a deterministic, priority-ordered authorization and safety decision layer evaluating every operation before execution.

```text
       Execution Request (Agent / User / Tool)
                          ↓
              PolicyContext Formulation
        [Subject, Action, Resource, Environment, Risk]
                          ↓
               ORION Central Policy Engine
       ┌───────────────────────────────────────────────┐
       │ Priority Evaluation Chain (Rules 0..100)      │
       │ - Credential & Secret Protection (Rule 10)    │
       │ - Catastrophic Shell Interception (Rule 10)   │
       │ - Adversarial Prompt Injection Defense (15)  │
       │ - Cloud Metadata SSRF Prevention (Rule 20)    │
       │ - Production DB Destructive Safeguard (25)    │
       │ - Mandatory Critical Risk Approval (Rule 50)  │
       │ - Dynamic Custom RBAC / ABAC Rules           │
       └───────────────────────────────────────────────┘
                          ↓
      Policy Decision: ALLOW / DENY / REQUIRE_APPROVAL / MODIFY
                          ↓
       Immutable Decision History & Audit Trail (UUID)
```

---

## 2. Core Security Guardrails

### 2.1 Credential & Secret Exfiltration Defense (`RULE-SEC-001`)
Strictly prohibits reading, modifying, or transferring sensitive credential and configuration files:
* `.env`, `credentials.json`, `~/.aws/credentials`
* Private keys: `id_rsa`, `id_ed25519`, `.secret`
* OS credential stores: `/etc/passwd`, `/etc/shadow`

### 2.2 Catastrophic Shell Command Neutralization (`RULE-SEC-002`)
Identifies and rejects destructive operating system commands before dispatch to subprocess runners or terminal executors:
* Root/home file deletion: `rm -rf /`, `rm -rf ~`
* Disk formatting and wiping: `mkfs.*`, `dd if=/dev/zero`, `format [C-Z]:`
* Fork bombs and permission corruption: `:(){ :|:& };:`, `chmod -R 777 /`

### 2.3 Adversarial Prompt Injection Defense (`RULE-SEC-003`)
Neutralizes prompt injections, system prompt leak requests, and jailbreak payloads:
* `ignore all previous instructions`
* `system prompt override`
* `you are now in DAN mode`
* `bypass safety filter`

### 2.4 Cloud Instance Metadata SSRF Defense (`RULE-SEC-004`)
Prevents server-side request forgery (SSRF) against cloud provider metadata services:
* `169.254.169.254` (AWS, GCP, Azure, OpenStack)
* `metadata.google.internal`
* `100.100.100.200` (Alibaba Cloud)

### 2.5 Production Database Protection & Human-in-the-Loop Trigger (`RULE-SEC-005` & `006`)
* Destructive DDL/DML statements (`DROP DATABASE`, `DROP TABLE`, `TRUNCATE TABLE`) in `production` and `staging` environments require explicit human operator approval (`REQUIRE_APPROVAL`).
* Any operation assessed at `CRITICAL` risk tier halts and transitions to `REQUIRE_APPROVAL`, seamlessly coupling with V7 Human-in-the-Loop collaborative oversight.

---

## 3. Dynamic Policy Management & Parameter Sanitization

* **Dynamic Rule Injection**: Operators and security administrators can register high-priority custom rules via the REST API or Python SDK.
* **Parameter Modification (`SANITIZE` / `MODIFY`)**: Rules can automatically enforce safe execution flags (e.g., injecting `sandbox=True`, enforcing strict timeout caps) without outright failing an agent's task.
* **Audit Trail**: Every evaluated decision produces an immutable `PolicyDecision` with unique `audit_id`, UTC timestamp, rule ID, and contextual parameters for compliance auditing.

---

## 4. REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/policy/evaluate` | `POST` | Evaluates a context against policy rules and returns `allow`, `deny`, `require_approval`, or `modify`. |
| `/api/v1/policy/rules` | `GET` | Lists all registered policy rules sorted by evaluation priority. |
| `/api/v1/policy/rules` | `POST` | Registers a new operational or security policy rule with custom effects and matchers. |
| `/api/v1/policy/decisions` | `GET` | Retrieves recent policy decision logs for audit and security analysis. |

---

## 5. Verification Metrics

* Dedicated Policy Engine Test Suite: 9 tests passed in 1.23s.
* Static Type Checking: `mypy src` clean across 231 source files.
* Linter: `ruff check .` clean with 0 warnings or errors.

# ORION Security Policy & Invariant Architecture

## 1. Security Overview & Philosophy

ORION is engineered from the ground up under a **Zero-Trust Autonomous Execution Architecture**. Unlike untrusted chatbot loops that allow autonomous agents to execute arbitrary terminal commands with `shell=True` or roam unrestricted across file paths, ORION treats every agent as an untrusted actor constrained by cryptographic, physical, and policy guardrails.

All execution occurs strictly on local repositories using pure Python standard library runtime components with **zero third-party runtime dependencies**.

---

## 2. The 20 Non-Negotiable Security Invariants

| ID | Invariant Name | Scope | Enforcement Mechanism |
| :--- | :--- | :--- | :--- |
| **INV-01** | Zero Runtime Dependencies | Global | Standard library only; zero pip packages at runtime. |
| **INV-02** | No Shell Execution (`shell=False`) | Subprocess | All commands use explicit `list[str]` sequences; `shell=True` is forbidden. |
| **INV-03** | Path Containment (No Escape) | Filesystem | Canonical `Path.resolve()` validated with `is_relative_to(repo_root)`. |
| **INV-04** | Symlink & Junction Escape Rejection | Filesystem | Evaluates real target path before reading/writing; cross-root targets blocked. |
| **INV-05** | UNC & Device Path Rejection | Filesystem | Windows `\\`, `\\?\`, `CON`, `NUL`, `AUX` paths rejected with `403 FORBIDDEN`. |
| **INV-06** | Dual-Key Human Approval Gate | Mutation | Mutating file edits require explicit human sign-off in Controlled Mode. |
| **INV-07** | Single-Use Cryptographic Approval Tokens | Security | Approvals consume tokens once; replays fail with `PermissionError`. |
| **INV-08** | Dynamic Secret Redaction | Logging & Diff | High-entropy regex and token patterns scrubbed to `[REDACTED]`. |
| **INV-09** | Authoritative Ground-Truth Verification | Verification | Passing tests alone do NOT mark success; `VerificationEngine` certifies. |
| **INV-10** | Non-Destructive Transactional Rollback | Recovery | Snapshots taken before mutations; failed verifications trigger full rollback. |
| **INV-11** | Bounded Recovery Budgets | Self-Healing | Max 3 attempts, max 120s runtime, max 2 patch regenerations. |
| **INV-12** | Central Zero-Trust Policy Engine | Governance | Every tool action evaluated against rules; violations trigger immediate block. |
| **INV-13** | Subprocess Hard Timeout Caps | Execution | Pytest and tools have explicit non-zero timeouts to prevent hanging. |
| **INV-14** | Fail-Closed Error Handling | System | Unhandled anomalies terminate safely; system fails closed, never open. |
| **INV-15** | Token Bucket Rate Limiting | API | Sliding window token bucket prevents DoS and request floods. |
| **INV-16** | Strict MIME Content-Type Validation | API | Mutating endpoints require `application/json`; non-JSON rejected with 415. |
| **INV-17** | Pre-Read Request Body Size Limits | API | Payloads exceeding 10MB rejected with `413 Payload Too Large`. |
| **INV-18** | Static File Path Traversal Defense | API | Percent-decoding normalization via `unquote()` prevents `../` static leaks. |
| **INV-19** | Loopback or Token-Authenticated Binding | Network | Non-loopback bindings require `api_token` Bearer or `X-API-Key` headers. |
| **INV-20** | Immutable Append-Only Evidence Ledger | Auditing | Provenance items tier-separated (Claimed, Observed, Verified) with SHA-256. |

---

## 3. Threat Model Summary (TM-01 through TM-08)

For complete technical specifications, see [`docs/THREAT_MODEL.md`](file:///c:/Users/LIKITH/ORION/docs/THREAT_MODEL.md).

1. **TM-01: Workspace Escape** — Blocked via strict canonical boundary containment.
2. **TM-02: Symlink / Junction Traversal** — Physical target validation prevents symlink poisoning.
3. **TM-03: Secret Leakage** — Dynamic sanitizer scrubs API keys, private keys, and `.env` files.
4. **TM-04: Prompt / Instruction Injection** — Multi-pattern scanner detects directive overrides.
5. **TM-05: Runaway Execution** — Hard step budgets and execution loop detectors terminate runs.
6. **TM-06: Approval Token Replay** — Single-use cryptographic state machine rejects re-use.
7. **TM-07: API Path Traversal** — URL decoding normalization prevents static file breakout.
8. **TM-08: Oversized & Malformed Requests** — Pre-read headers cap payloads and enforce MIME types.

---

## 4. Reporting Vulnerabilities

If you discover a security vulnerability in ORION:

1. **Do not file public issues**: Do not create public GitHub issues or discussions.
2. **Contact**: Email `security@orion-platform.local` or the project maintainer directly.
3. **Details**: Provide proof-of-concept steps, affected component, and environment details.
4. **Response SLA**: Initial triage within 24 hours; patch and verification within 72 hours.

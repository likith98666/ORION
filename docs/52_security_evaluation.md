\# ORION â€” Security Evaluation



\## 1. Purpose



This document records the security controls currently implemented in ORION, the security invariants verified by automated tests, the evidence used to evaluate those controls, and the security capabilities intentionally reserved for later production phases.



This is an implementation and verification record. It does not claim that ORION is immune to all security threats.



\---



\## 2. Evaluation Scope



The current Phase 7 security evaluation covers the implemented security boundary around:



\* agent identity

\* agent permissions

\* tool authorization

\* tool risk classification

\* human approval for high-risk actions

\* approval binding and replay protection

\* tool input validation

\* secret references and secret resolution

\* secret redaction

\* audit events

\* untrusted model context

\* prompt-injection boundary

\* tool execution lifecycle

\* security integration behavior

\* adversarial authorization behavior

\* adversarial approval behavior



The evaluation is based on the current repository implementation and automated test suites.



\---



\## 3. Verification Baseline



The current Phase 7 security/tool verification checkpoint is:



| Verification                    |     Result |

| ------------------------------- | ---------: |

| Security + tool unit tests      | 184 passed |

| Test failures                   |          0 |

| Ruff checks                     |      Clean |

| Adversarial approval tests      |   8 passed |

| Adversarial authorization tests |   6 passed |



Command used for the focused regression:



```text

pytest -q tests\\unit\\core\\security tests\\unit\\core\\tools

```



The 184-test result is a focused Phase 7 security/tool checkpoint.



A full repository regression is required before Phase 7 is formally closed.



\---



\## 4. Security Control Matrix



| Security Control                  | Implementation                                       | Verification                            |

| --------------------------------- | ---------------------------------------------------- | --------------------------------------- |

| Agent identity binding            | `SecurityContext` + authorization subject validation | Authorization tests                     |

| Agent permissions                 | `AgentPermissionPolicy`                              | Permission boundary tests               |

| Capability separation             | Capabilities are distinct from permissions           | Adversarial authorization tests         |

| Tool authorization                | Central `AuthorizationService`                       | Authorization integration tests         |

| Tool risk classification          | `ToolRiskLevel`                                      | Risk tests                              |

| Risk policy                       | `ToolRiskPolicy`                                     | Risk-policy tests                       |

| High-risk approval                | `ApprovalService`                                    | Approval/integration tests              |

| Critical-risk approval            | HIGH/CRITICAL approval enforcement                   | HIGH/CRITICAL tests                     |

| Approval context binding          | Agent/execution/tool/action/risk matching            | Approval validation + adversarial tests |

| Approval replay protection        | One-time consumption                                 | Consumption/adversarial tests           |

| Approval expiration               | Expiration validation                                | Expiration tests                        |

| Tool input validation             | Bounded schema validation                            | Input validation tests                  |

| Secret references                 | Explicit `SecretReference` type                      | Secret isolation tests                  |

| Secret resolution                 | Separate handler arguments                           | Secret isolation tests                  |

| Secret persistence protection     | Redaction before lifecycle persistence               | Audit/security tests                    |

| Secret audit protection           | Central audit redaction                              | Audit security tests                    |

| Prompt-injection boundary         | Explicit trusted/untrusted context                   | Context/injection tests                 |

| Audit trail                       | Central `AuditService`                               | Audit tests                             |

| Execution correlation             | Parent execution ID propagation                      | Audit correlation tests                 |

| Tool lifecycle                    | Pending/running/completed/failed states              | Lifecycle tests                         |

| Unauthorized execution prevention | Authorization before handler invocation              | Integration/adversarial tests           |



\---



\## 5. Identity and Authorization Evaluation



ORION does not treat an agent's capabilities as equivalent to authorization.



Capabilities describe what an agent is designed to do.



Permissions determine what an agent is actually allowed to access.



The authorization boundary verifies that:



1\. the security context identifies the same agent being authorized;

2\. the agent possesses the required permission;

3\. the tool risk level is evaluated against the configured risk policy;

4\. high-risk decisions can require explicit approval;

5\. denied authorization does not reach the tool handler.



The adversarial authorization suite verifies that:



\* a capability cannot substitute for a permission;

\* unrelated permissions cannot escalate into another permission;

\* a spoofed agent identity is rejected;

\* additional unrelated permissions do not bypass the required permission;

\* authorization denial occurs before tool execution.



The authorization service returns a structured denial result. The tool execution boundary converts denied authorization into a `PermissionError` before invoking the handler.



\---



\## 6. Risk-Based Authorization



ORION assigns every tool a risk level:



\* LOW

\* MEDIUM

\* HIGH

\* CRITICAL



The default policy allows LOW and MEDIUM operations while requiring approval for HIGH and CRITICAL operations.



The security decision flow is:



```text

Permission

&#x20;   â†“

Risk classification

&#x20;   â†“

Risk policy

&#x20;   â†“

Approval requirement

&#x20;   â†“

Tool execution

```



HIGH and CRITICAL actions therefore cannot rely solely on possession of the underlying permission.



\---



\## 7. Human Approval Security



High-risk approval requests are bound to their intended execution context.



The approval validation boundary checks:



\* agent identity;

\* execution identity;

\* tool name;

\* action;

\* risk level;

\* approval state;

\* expiration.



Approval consumption is one-time.



The adversarial approval suite verifies that an approval cannot:



\* cross execution contexts;

\* cross agents;

\* be replayed after consumption;

\* authorize a denied request;

\* authorize an expired request;

\* authorize a different tool;

\* authorize a different risk level.



The tests also verify that invalid approval attempts do not reach the tool handler.



\---



\## 8. Tool Input Security



Tool inputs are validated before execution.



The input validation layer enforces constraints including:



\* dictionary/object input requirements;

\* required fields;

\* unknown-field rejection;

\* primitive type validation;

\* string length bounds;

\* collection size bounds;

\* nested depth bounds;

\* controlled dictionary structure;

\* explicit secret-reference handling.



The validation layer is intentionally bounded so malformed or excessively large inputs cannot freely propagate into tool execution.



Validation occurs before authorization and handler invocation where applicable.



\---



\## 9. Secret Handling



ORION uses explicit secret references rather than treating arbitrary strings as secrets.



A secret reference identifies a secret without embedding its value directly into the tool arguments.



The execution flow is:



```text

SecretReference

&#x20;     â†“

SecretProvider

&#x20;     â†“

Resolved private execution arguments

&#x20;     â†“

Tool handler

```



The persisted tool execution record retains the reference rather than the resolved secret.



The audit path applies redaction before persistence.



The current implementation supports explicit secret-reference isolation and known-secret redaction.



It does not claim generic detection of every possible secret format.



\---



\## 10. Audit Security



Security-sensitive decisions are recorded through the centralized `AuditService`.



Current event categories include:



\* authorization allowed;

\* authorization denied;

\* authorization approval required;

\* approval requested;

\* approval granted;

\* approval denied;

\* tool execution started;

\* tool execution completed;

\* tool execution failed;

\* secret redacted.



Audit records can be correlated using the parent execution identity.



Audit details pass through the redaction layer before persistence.



This provides an evidence trail for important authorization, approval, execution, and secret-handling decisions.



\---



\## 11. Prompt-Injection Boundary



ORION explicitly distinguishes trusted instructions from untrusted retrieved content.



Current model-context sections contain:



\* content;

\* trust level;

\* source.



Task instructions are treated as trusted task context.



Retrieved memory is treated as untrusted data.



The memory context formatter applies an explicit data-versus-authority boundary.



The adversarial prompt-injection tests verify resistance to attempts to make retrieved content:



\* override the task;

\* impersonate system instructions;

\* escalate permissions;

\* invoke tools;

\* extract secrets;

\* disable authorization;

\* fabricate completion;

\* manipulate recovery;

\* manipulate model selection.



These tests verify the implemented trust boundary.



They do not establish immunity against all future prompt-injection techniques.



\---



\## 12. Tool Execution Security



The protected execution path is:



```text

Agent

&#x20; â†“

Tool lookup

&#x20; â†“

Input validation

&#x20; â†“

Authorization

&#x20; â†“

Risk policy

&#x20; â†“

Human approval when required

&#x20; â†“

Execution lifecycle

&#x20; â†“

Secret resolution

&#x20; â†“

Handler

&#x20; â†“

Redaction

&#x20; â†“

Persisted execution/audit evidence

```



The handler is not invoked when authorization or approval requirements fail.



This ordering is an important security invariant because controls placed after handler invocation would not protect the actual side effect.



\---



\## 13. Adversarial Verification



\### 13.1 Approval attacks



The adversarial approval suite contains 8 tests covering:



1\. execution-context substitution;

2\. agent substitution;

3\. approval replay;

4\. denied approval;

5\. expired approval;

6\. tool substitution;

7\. risk-level substitution;

8\. combined attacker-context abuse.



Result:



```text

8 passed

```



\### 13.2 Authorization attacks



The adversarial authorization suite contains 6 tests covering:



1\. capability-to-permission escalation;

2\. unrelated-permission escalation;

3\. spoofed agent context;

4\. missing execution-context boundary;

5\. extra-permission bypass;

6\. denial-before-handler behavior.



Result:



```text

6 passed

```



\---



\## 14. Current Security Invariants



The following invariants are currently verified.



\### Identity invariant



An authorization request cannot authorize an operation on behalf of a different agent.



\### Permission invariant



Agent capabilities do not automatically grant tool permissions.



\### Risk invariant



HIGH and CRITICAL operations cannot bypass the configured approval requirement.



\### Approval-context invariant



An approval is valid only for its exact authorized context.



\### Approval-consumption invariant



A consumed approval cannot be reused.



\### Expiration invariant



Expired approvals cannot authorize execution.



\### Handler-boundary invariant



Invalid authorization or approval cannot reach the tool handler.



\### Input-boundary invariant



Malformed or oversized tool inputs are rejected before execution.



\### Secret-persistence invariant



Supported resolved secrets are not persisted into tool lifecycle or audit details.



\### Trust-boundary invariant



Retrieved untrusted content is represented as data rather than automatically becoming authoritative instructions.



\### Audit invariant



Important security decisions can be recorded with execution correlation.



\---



\## 15. Implemented vs Planned



Phase 7 intentionally establishes the security foundation rather than implementing every production security capability.



\### Implemented in Phase 7



\* permission model;

\* authorization service;

\* risk policy;

\* high-risk approval;

\* approval validation;

\* approval consumption;

\* approval expiration;

\* input validation;

\* secret references;

\* secret provider abstraction;

\* secret redaction;

\* audit repository;

\* audit service;

\* execution/audit correlation;

\* trusted/untrusted context model;

\* prompt-injection boundary;

\* security integration tests;

\* adversarial authorization tests;

\* adversarial approval tests.



\### Deliberately planned for later phases



The following depend on infrastructure introduced in later phases:



\* production authentication;

\* full RBAC/API identity layer;

\* distributed audit storage;

\* encrypted secret-management integration;

\* sandboxed code execution;

\* network isolation for code execution;

\* production database security;

\* tenant isolation;

\* production rate limiting;

\* distributed abuse prevention;

\* supply-chain scanning in CI;

\* runtime threat detection;

\* production incident response;

\* security telemetry and dashboards;

\* production policy management;

\* deployment-level security controls.



These are not treated as Phase 7 implementation defects where they depend on infrastructure that has not yet been introduced.



\---



\## 16. Security Limitations



The current evaluation has important limitations.

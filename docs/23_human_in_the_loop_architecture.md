# ORION — Human-in-the-Loop Architecture

## 1. Human-in-the-Loop Architecture Overview

ORION is designed to operate autonomously, but complete autonomy is not always appropriate.

Some decisions are:

* low risk
* reversible
* routine
* easily verifiable

Other decisions may involve:

* financial consequences
* sensitive information
* external communication
* destructive actions
* security risks
* ambiguous requirements
* irreversible changes

Human-in-the-Loop (HITL) architecture allows ORION to request human intervention when required.

The goal is not to make humans supervise every action.

The goal is:

> **Maximum useful autonomy with appropriate human control.**

---

## 2. Human-in-the-Loop Goals

The HITL system should provide:

1. risk-based human intervention
2. approval workflows
3. rejection workflows
4. human clarification
5. human feedback
6. human override
7. task pause and resume
8. escalation
9. decision recording
10. auditability
11. secure approval handling
12. timeout handling
13. notification support
14. minimal human dependency
15. measurable intervention quality

---

## 3. HITL Philosophy

ORION follows several principles.

### Principle 1 — Humans Should Not Be Required for Everything

Routine low-risk actions should remain autonomous.

### Principle 2 — High-Risk Actions Require Stronger Control

The higher the risk, the stronger the approval requirement.

### Principle 3 — Explain Before Asking

When requesting approval, ORION should clearly explain:

* what it wants to do
* why it wants to do it
* expected consequences
* relevant evidence
* risks
* alternatives

### Principle 4 — Approval Must Be Explicit

High-risk actions should not rely on ambiguous human signals.

### Principle 5 — Human Decisions Must Be Auditable

Important human decisions should be recorded.

### Principle 6 — Humans Can Override the System

Authorized humans should be able to stop or redirect execution.

### Principle 7 — Human Intervention Should Be Measured

Too many interventions may indicate poor planning or excessive conservatism.

---

## 4. What Is Human-in-the-Loop?

Human-in-the-Loop means a human participates in an AI system's execution when the system determines that human judgment is necessary or valuable.

Example:

```text
ORION
  ↓
Plans Action
  ↓
Risk Analysis
  ↓
High Risk
  ↓
Human Approval
  ↓
Approved
  ↓
Execute
```

---

## 5. HITL vs Human-on-the-Loop

These concepts should be distinguished.

### Human-in-the-Loop

The system pauses and requires a human decision.

```text
AI
 ↓
PAUSE
 ↓
Human
 ↓
Decision
 ↓
AI continues
```

### Human-on-the-Loop

The system continues operating while a human monitors execution and can intervene.

```text
AI ─────────────→ Execution
 ↑
Human Monitoring
```

ORION can support both models depending on task risk.

---

## 6. HITL vs Human-in-Command

Human-in-Command means humans retain ultimate authority over the system.

For ORION:

```text
Human Authority
      ↓
Policy
      ↓
ORION Autonomy
      ↓
Agents
      ↓
Tools
```

Agents should never outrank the system's authorization policies.

---

## 7. Human Roles

Potential human roles include:

```text
User
Reviewer
Approver
Administrator
Security Reviewer
Domain Expert
Operator
```

Each role should have clearly defined permissions.

---

## 8. User

The user is normally the person who initiates the task.

Responsibilities may include:

* defining the objective
* answering clarification questions
* approving actions
* reviewing results
* cancelling tasks

---

## 9. Reviewer

A reviewer evaluates outputs.

Example:

```text
Research Result
 ↓
Human Reviewer
 ↓
Accept / Reject / Request Changes
```

---

## 10. Approver

An approver authorizes high-risk actions.

Examples:

* external communication
* production changes
* sensitive data access
* expensive operations
* destructive actions

---

## 11. Domain Expert

Some tasks require specialized human knowledge.

Example:

```text
AI Analysis
 ↓
Domain Expert
 ↓
Validation
 ↓
Continue
```

The expert should not need to understand ORION's internal implementation.

---

## 12. Security Reviewer

Security reviewers may handle:

* suspicious tool activity
* prompt injection
* data exfiltration concerns
* permission escalation
* sensitive operations

Security intervention can override normal task execution.

---

## 13. Operator

Operators manage system-level execution.

Responsibilities may include:

* worker failures
* queue problems
* deployments
* incidents
* operational recovery

---

## 14. Human Authority Model

The authority hierarchy should be:

```text
System Security Policies
        ↓
Authorization Policies
        ↓
Human Authorized Decisions
        ↓
Orchestrator
        ↓
Agents
        ↓
Tools
```

An agent cannot override a higher-level security restriction.

---

## 15. Risk-Based Intervention

ORION should not ask for approval simply because an action exists.

Instead it should estimate action risk.

Conceptually:

```text
Risk =
Impact × Probability × Irreversibility × Exposure
```

The exact mathematical model can evolve through experimentation.

---

## 16. Low-Risk Actions

Examples:

* reading public information
* calculating values
* analyzing non-sensitive files
* generating a draft
* summarizing documents

These can normally execute autonomously.

---

## 17. Medium-Risk Actions

Examples:

* accessing internal datasets
* modifying non-critical files
* running expensive analysis
* executing larger workloads

Depending on policy, these may require conditional approval.

---

## 18. High-Risk Actions

Examples:

* deleting data
* modifying production systems
* sending external communications
* accessing highly sensitive information
* making consequential external changes

These should normally require explicit authorization.

---

## 19. Critical-Risk Actions

Critical actions may include:

* security-sensitive operations
* destructive operations
* privilege changes
* irreversible external actions

These should require the strongest authorization and may be prohibited entirely for autonomous agents.

---

## 20. Risk Classification

Each tool and action should have a risk classification.

Example:

```text
Tool: Web Search
Risk: Low

Tool: Internal Database Read
Risk: Medium

Tool: External Email
Risk: High

Tool: Delete Production Data
Risk: Critical
```

Risk is contextual, so the same tool may have different risk depending on the operation.

---

## 21. Approval Policy

The policy engine determines whether human intervention is required.

Conceptually:

```text
Action
 ↓
Permission Check
 ↓
Risk Classification
 ↓
Policy Evaluation
 ↓
┌───────────────┬───────────────┐
│ Auto Execute  │ Human Approval│
└───────────────┴───────────────┘
```

---

## 22. Approval Request

A human approval request should contain:

```text
Approval ID
Task ID
Requested Action
Reason
Agent
Tool
Risk Level
Expected Effect
Potential Risks
Evidence
Alternatives
Expiration
```

---

## 23. Approval Request Example

Conceptually:

```text
Action:
Send final report to external recipient

Requested by:
Writer Agent

Reason:
User requested external delivery

Risk:
High

Potential impact:
Information leaves ORION environment

Approval:
Required
```

The human should have enough information to make an informed decision.

---

## 24. Approval States

Approval can have states such as:

```text
PENDING
APPROVED
REJECTED
EXPIRED
CANCELLED
SUPERSEDED
```

---

## 25. Approval State Machine

```text
PENDING
   │
   ├── APPROVED
   │      ↓
   │   EXECUTE
   │
   ├── REJECTED
   │      ↓
   │   REPLAN / STOP
   │
   ├── EXPIRED
   │      ↓
   │   PAUSE / REPLAN
   │
   └── CANCELLED
          ↓
        STOP
```

---

## 26. Explicit Approval

For high-risk operations, approval should be explicit.

Examples:

```text
Approve
Reject
Cancel
```

Avoid ambiguous signals such as:

```text
Maybe
Looks good
Continue if necessary
```

---

## 27. Approval Scope

Approval should be narrowly scoped.

For example:

```text
Approve:
Read Dataset X
```

should not automatically mean:

```text
Approve:
Read Every Dataset
```

This follows least-privilege principles.

---

## 28. Approval Expiration

Approvals may expire.

Example:

```text
Approval:
Valid for 10 minutes
```

After expiration:

```text
Do not execute
```

A fresh approval may be required.

---

## 29. Approval Context Binding

An approval should be bound to the action it authorizes.

Conceptually:

```text
Approval
+
Task
+
Action
+
Tool
+
Parameters
+
Risk Context
```

If the action materially changes, ORION should request approval again.

---

## 30. Preventing Approval Abuse

An agent should not be able to manipulate humans into approving unsafe actions.

Therefore approval requests should:

* present relevant information
* avoid deceptive wording
* clearly display risks
* identify the requesting agent
* identify the tool
* show important parameters
* distinguish facts from assumptions

---

## 31. Human Clarification

Sometimes ORION does not need permission.

It needs information.

Example:

```text
User:
Prepare a report for the client.

ORION:
Which client should be used?
```

This is clarification rather than approval.

---

## 32. Clarification Workflow

```text
Execution
 ↓
Ambiguity Detected
 ↓
Generate Question
 ↓
Human Response
 ↓
Update Task Context
 ↓
Resume
```

---

## 33. Clarification Quality

Questions should be:

* specific
* minimal
* relevant
* actionable

ORION should avoid asking questions that can be safely resolved from available information.

---

## 34. Human Feedback

Humans may provide feedback such as:

```text
Correct
Incorrect
Incomplete
Unsafe
Too expensive
Use different source
Change strategy
```

This feedback can support evaluation and future system improvement.

---

## 35. Human Feedback vs Memory

Not every human comment should automatically become long-term memory.

Feedback should be evaluated for:

* relevance
* reliability
* scope
* persistence
* sensitivity

Only validated information should become durable memory.

---

## 36. Human Override

Authorized humans should be able to override execution.

Possible actions:

```text
Pause
Resume
Cancel
Retry
Skip
Modify
Replan
Approve
Reject
```

---

## 37. Pause

Pausing should preserve task state.

```text
RUNNING
 ↓
PAUSED
 ↓
Resume
 ↓
RUNNING
```

The task should not lose completed work.

---

## 38. Resume

When resuming:

```text
Load State
 ↓
Validate State
 ↓
Check Permissions
 ↓
Check Expired Approvals
 ↓
Continue
```

ORION should not blindly resume outdated actions.

---

## 39. Human-Initiated Cancellation

A user should be able to cancel an active task.

```text
RUNNING
 ↓
CANCEL REQUEST
 ↓
Graceful Shutdown
 ↓
CANCELLED
```

---

## 40. Cancellation Safety

Cancellation should account for active side effects.

For example:

```text
Analysis Running
→ Safe to stop
```

versus:

```text
External Transaction
→ Requires careful state handling
```

---

## 41. Human-Requested Retry

Humans may request a retry after failure.

However, retry policies and security restrictions still apply.

Human approval does not automatically bypass safety controls.

---

## 42. Human-Requested Replanning

A human may request:

```text
Use another approach
```

ORION can send the task back to the planning system.

```text
Human Feedback
 ↓
Planner
 ↓
New Plan
 ↓
Orchestrator
```

---

## 43. Human Review of Final Results

High-impact results may require human review before delivery.

Example:

```text
Final Result
 ↓
Human Review
 ↓
Approved
 ↓
Delivered
```

---

## 44. Human Review Criteria

A reviewer may evaluate:

* correctness
* completeness
* evidence
* clarity
* safety
* policy compliance
* relevance

---

## 45. Review Outcomes

Possible outcomes:

```text
APPROVE
REJECT
REQUEST_CHANGES
REQUEST_MORE_EVIDENCE
ESCALATE
```

---

## 46. Multi-Level Approval

Some actions may require multiple reviewers.

Example:

```text
Agent
 ↓
Technical Reviewer
 ↓
Security Reviewer
 ↓
Final Approver
 ↓
Execute
```

This should be used only when justified by risk.

---

## 47. Approval Delegation

Organizations may define approval delegation.

Example:

```text
Manager unavailable
 ↓
Authorized Delegate
 ↓
Approval
```

Delegation rules must be explicit and auditable.

---

## 48. Separation of Duties

For particularly sensitive operations, the same person should not necessarily:

1. create the action
2. approve the action
3. verify the action

This reduces abuse risk.

---

## 49. Human Escalation

ORION should escalate when:

```text
Risk Too High
No Safe Recovery
Ambiguous Requirements
Conflicting Evidence
Repeated Failure
Security Concern
Budget Exceeded
Policy Requires Human
```

---

## 50. Escalation Priority

Escalations can have priority levels:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Critical security or operational events should receive higher priority.

---

## 51. Escalation Timeout

If a human does not respond:

```text
Approval Pending
 ↓
Timeout
```

Possible actions:

```text
Pause
Abort
Replan
Retry Later
```

For high-risk actions, the default should be fail-safe rather than execute automatically.

---

## 52. Human Notification

The architecture should support notifications through an appropriate notification layer.

Potential channels may include:

* web interface
* application notifications
* email
* organizational messaging systems

The notification mechanism should be separated from the core orchestration logic.

---

## 53. Human Control Interface

The interface should provide:

```text
Task Status
Current Plan
Current Step
Pending Approval
Risk Level
Evidence
Failures
Recovery Attempts
Cost
Latency
Artifacts
Actions
```

The user should be able to understand what ORION is doing without seeing raw internal reasoning.

---

## 54. Human-Friendly Execution Timeline

A useful interface may display:

```text
10:01 Task started

10:02 Plan created

10:03 Research completed

10:04 Verification passed

10:05 High-risk action detected

10:05 Approval requested

10:07 Approval received

10:08 Action completed
```

---

## 55. Human Visibility

Users should be able to see meaningful execution information.

However, the system should avoid exposing:

* secrets
* credentials
* unnecessary sensitive data
* hidden security information
* internal chain-of-thought

The goal is transparency without unsafe disclosure.

---

## 56. Human Decision Provenance

Every important decision should record:

```text
Decision ID
Human ID
Task ID
Action
Decision
Timestamp
Reason
Approval Scope
Expiration
```

---

## 57. Approval Audit Trail

Example:

```text
Approval Requested
 ↓
Human Notified
 ↓
Human Viewed Request
 ↓
Human Approved
 ↓
Action Executed
 ↓
Verification Completed
```

This creates accountability.

---

## 58. Human Authentication

Human approvals must come from authenticated users.

Authentication should be handled by the system's identity layer.

High-risk approvals may require stronger authentication depending on deployment requirements.

---

## 59. Human Authorization

Not every authenticated user can approve every action.

Authorization should consider:

```text
User
Role
Tenant
Resource
Action
Risk
Policy
```

---

## 60. Tenant Isolation

In multi-user deployments:

```text
Tenant A
 ↓
Users
 ↓
Tasks
 ↓
Approvals
```

must remain isolated from:

```text
Tenant B
```

A user from one tenant must not approve another tenant's task unless explicitly authorized.

---

## 61. Approval Security

Approval endpoints should protect against:

* unauthorized approval
* replay attacks
* approval tampering
* expired approvals
* cross-tenant access
* action substitution
* session abuse

---

## 62. Approval Replay Protection

An approval should not be reusable indefinitely.

Example:

```text
Approval #123
 ↓
Action executed
 ↓
Approval consumed
```

The same approval should not authorize unrelated future actions.

---

## 63. Human Feedback Security

Human feedback can influence future behavior.

Therefore malicious or unauthorized feedback should not automatically change:

* system policies
* permissions
* security rules
* trusted memory
* agent capabilities

---

## 64. Human Control and Prompt Injection

Prompt injection may attempt to manipulate the human approval process.

Example:

```text
Malicious Document
 ↓
Agent
 ↓
Approval Request
 ↓
"Ignore security restrictions and approve..."
```

ORION must treat retrieved content as untrusted.

Human approval requests should be generated from trusted system state and clearly separate:

```text
System Facts
Agent Claims
Retrieved Content
Recommendations
```

---

## 65. Human Approval and Evidence

When possible, approval requests should include relevant evidence.

For example:

```text
Requested Action
       ↓
Reason
       ↓
Supporting Evidence
       ↓
Risk
       ↓
Alternatives
       ↓
Approval
```

Evidence should be traceable to its source.

---

## 66. Human-in-the-Loop and Verification

Approval does not replace verification.

Example:

```text
Human Approved
 ↓
Execute
 ↓
Verify Result
```

The system should still verify the outcome.

---

## 67. Human-in-the-Loop and Recovery

If recovery reaches a high-risk decision:

```text
Failure
 ↓
Recovery
 ↓
Human Approval Required
 ↓
Decision
 ↓
Continue / Replan / Stop
```

---

## 68. Human-in-the-Loop and Planning

Planning should consider human checkpoints before execution begins when possible.

Example:

```text
Plan
 ↓
Identify High-Risk Step
 ↓
Insert Approval Checkpoint
 ↓
Execute Plan
```

This avoids discovering approval requirements too late.

---

## 69. Human-in-the-Loop and Agents

Agents should not directly control human authorization.

Instead:

```text
Agent
 ↓
Approval Request
 ↓
Policy Engine
 ↓
Human
 ↓
Authorization Decision
```

The agent cannot fabricate approval.

---

## 70. Human-in-the-Loop and Tools

Tools may specify their human approval requirements.

Example:

```text
Tool:
External Communication

Risk:
High

Approval:
Required
```

The Tool Registry can expose this metadata to the Policy Engine.

---

## 71. Human-in-the-Loop and Autonomy Levels

ORION can define autonomy levels.

```text
LEVEL 0
Human performs action

LEVEL 1
AI recommends

LEVEL 2
AI executes with approval

LEVEL 3
AI executes low-risk actions autonomously

LEVEL 4
AI executes multi-step workflows with selective intervention

LEVEL 5
Highly autonomous execution under strict policy controls
```

The exact levels should be validated experimentally.

---

## 72. Dynamic Autonomy

Autonomy should change based on:

```text
Task Risk
Agent Reliability
Tool Risk
User Preferences
Historical Performance
Environment
Policy
```

A reliable low-risk workflow may require less intervention.

A new high-risk workflow may require more.

---

## 73. Autonomy Escalation

Example:

```text
Low Risk
 ↓
Autonomous

Medium Risk
 ↓
Conditional Approval

High Risk
 ↓
Explicit Approval

Critical Risk
 ↓
Human Controlled
```

---

## 74. Reducing Human Burden

A bad HITL system asks:

```text
Approve?
Approve?
Approve?
Approve?
Approve?
```

This creates human fatigue.

A better system groups related decisions where safe.

Example:

```text
Research Task
 ↓
20 Low-Risk Searches
 ↓
Autonomous
 ↓
1 High-Risk External Action
 ↓
One Approval
```

---

## 75. Approval Batching

Related low-impact actions may be grouped when:

* they have the same risk class
* they share the same authorization scope
* they are predictable
* policy permits batching

High-risk or materially different actions should remain separately controlled.

---

## 76. Human Fatigue

Excessive approval requests can reduce attention.

Metrics should therefore include:

```text
Approvals per Task
Approval Rate
Approval Rejection Rate
Average Review Time
Approval Fatigue Indicators
```

---

## 77. Human Intervention Metrics

Important metrics include:

```text
Human Intervention Rate
Approval Rate
Rejection Rate
Clarification Rate
Escalation Rate
Average Approval Time
Human Actions per Task
Human Time per Task
```

---

## 78. Human Intervention Quality

A useful system should measure whether human intervention actually improved outcomes.

Compare:

```text
Without Human Review
vs
With Human Review
```

Potential measures:

* correctness
* safety
* task success
* error reduction
* time
* cost

---

## 79. Human Override Metrics

Track:

```text
Pause Rate
Cancel Rate
Retry Requests
Replan Requests
Manual Corrections
Override Frequency
```

Frequent overrides may indicate weaknesses in:

* planning
* agent selection
* verification
* recovery
* user understanding

---

## 80. HITL Evaluation

The HITL architecture should be experimentally evaluated.

Questions include:

```text
Does HITL improve task success?
Does it reduce harmful actions?
Does it reduce hallucinations?
Does it increase latency?
Does it increase cost?
Does it create approval fatigue?
```

---

## 81. HITL Ablation Studies

Possible comparisons:

```text
Fully Autonomous
vs
Risk-Based HITL
```

and:

```text
Always Ask Human
vs
Risk-Based Approval
```

The expected goal is not maximum intervention.

The goal is:

> **Maximum safety and quality with minimum unnecessary human effort.**

---

## 82. Human Decision Dataset

ORION may maintain evaluation data containing:

```text
Task
Risk
Requested Action
Evidence
Human Decision
System Recommendation
Outcome
```

This can be used to evaluate the approval system.

Sensitive human data must be handled according to the deployment's privacy requirements.

---

## 83. Human-in-the-Loop Testing

Tests should include:

### Approval Tests

* approval
* rejection
* expiration
* cancellation

### Authorization Tests

* unauthorized user
* wrong tenant
* wrong role
* insufficient permission

### Workflow Tests

* pause
* resume
* cancel
* retry
* replan

### Security Tests

* approval tampering
* replay
* forged approval
* action substitution

---

## 84. Failure Injection

The system should deliberately test:

```text
Human Does Not Respond
Human Rejects
Approval Expires
Approval Service Unavailable
Notification Fails
User Cancels
Human Gives Invalid Input
Human Gives Conflicting Instructions
```

ORION should fail safely.

---

## 85. HITL Reliability

Human control mechanisms themselves are dependencies.

The architecture should handle:

* unavailable approval service
* notification failure
* session expiration
* stale approval
* duplicate approval
* concurrent decisions

---

## 86. Concurrent Human Decisions

Two authorized humans may attempt to approve the same action.

The system must define deterministic behavior.

Example:

```text
Approval Request
 ├── Reviewer A → Approve
 └── Reviewer B → Reject
```

The policy should determine the final state.

For critical operations, rejection may take precedence.

---

## 87. Human Decision Conflicts

Possible strategies:

```text
First Decision
Majority Decision
Required Approver Set
Security Reviewer Override
Escalation
```

The appropriate strategy depends on the action's risk.

---

## 88. Human-in-the-Loop Observability

Track:

```text
Approval Requests
Approval Latency
Approval Outcomes
Human Escalations
Human Overrides
Clarification Requests
Task Pauses
Task Cancellations
```

These events should connect to the task's overall trace.

---

## 89. Human-in-the-Loop Cost

Human involvement has a cost in:

* time
* attention
* operational effort

Therefore ORION should measure:

```text
Human Time
+
AI Cost
+
Execution Cost
=
Total Task Cost
```

---

## 90. Human-in-the-Loop State Model

Conceptually:

```text
RUNNING
   ↓
HUMAN_REQUIRED
   ↓
WAITING_FOR_HUMAN
   │
   ├── APPROVED → RESUMING
   ├── REJECTED → REPLANNING / STOP
   ├── EXPIRED → PAUSED / REPLAN
   └── CANCELLED → STOP
```

---

## 91. Human Control Architecture

The conceptual architecture is:

```text
                    ORION
                      │
                      ▼
                Policy Engine
                      │
                      ▼
                Risk Analysis
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
    Low / Medium Risk        High Risk
          │                       │
          ▼                       ▼
   Autonomous Action       Approval Request
                                  │
                                  ▼
                             Human User
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 Approve        Reject       Modify
                    │             │             │
                    ▼             ▼             ▼
                Execute        Replan        Replan
                    │             │
                    └──────┬──────┘
                           ▼
                       Verification
                           │
                           ▼
                        Continue
```

---

## 92. End-to-End HITL Example

Consider:

```text
User:
Research a company and prepare a report.
```

ORION:

```text
1. Understand objective
2. Create plan
3. Research sources
4. Analyze information
5. Verify evidence
6. Generate report
```

All of these may be low risk.

Then the user requests:

```text
Send the report externally.
```

ORION:

```text
External communication
 ↓
High-risk action
 ↓
Approval required
 ↓
Human review
 ↓
Approved
 ↓
Send
 ↓
Verify
 ↓
Complete
```

This demonstrates selective autonomy.

---

## 93. HITL Quality Gate

Before considering HITL production-ready:

```text
[ ] Human roles
[ ] Role permissions
[ ] Risk classification
[ ] Approval policies
[ ] Approval requests
[ ] Approval states
[ ] Explicit approval
[ ] Approval scope
[ ] Approval expiration
[ ] Approval binding
[ ] Clarification workflow
[ ] Human feedback
[ ] Human override
[ ] Pause
[ ] Resume
[ ] Cancellation
[ ] Retry
[ ] Replanning
[ ] Final result review
[ ] Escalation
[ ] Escalation timeout
[ ] Notifications
[ ] Human interface
[ ] Decision provenance
[ ] Audit trail
[ ] Authentication
[ ] Authorization
[ ] Tenant isolation
[ ] Approval security
[ ] Replay protection
[ ] Prompt injection protection
[ ] Evidence display
[ ] Verification after approval
[ ] Recovery integration
[ ] Planning integration
[ ] Agent integration
[ ] Tool integration
[ ] Autonomy levels
[ ] Dynamic autonomy
[ ] Approval batching
[ ] Human fatigue measurement
[ ] Intervention metrics
[ ] HITL evaluation
[ ] HITL ablation studies
[ ] HITL testing
[ ] Failure injection
[ ] Reliability
[ ] Conflict handling
[ ] Observability
[ ] Cost measurement
[ ] State management
```

---

## 94. Final Human-in-the-Loop Principle

ORION should not aim for:

```text
100% Autonomous
```

at all costs.

Nor should it aim for:

```text
Human Approval for Everything
```

Instead:

```text
Low Risk
   ↓
Autonomous

Medium Risk
   ↓
Conditional Human Control

High Risk
   ↓
Explicit Human Approval

Critical Risk
   ↓
Human Controlled
```

The objective is:

> **Humans should intervene when their judgment materially improves safety, correctness, accountability, or decision quality — not because the AI system is incapable of acting autonomously.**

A mature ORION system therefore creates a partnership:

```text
Human Judgment
      +
AI Autonomy
      +
Policy Controls
      +
Verification
      +
Observability
      =
Responsible Autonomous Execution
```

This is the foundation for making ORION autonomous **without making it uncontrolled**.


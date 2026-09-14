# ORION — Data Architecture

## 1. Data Architecture Overview

ORION requires a data architecture capable of supporting autonomous, multi-step AI workflows while maintaining reliability, traceability, security, and reproducibility.

The data architecture must store and manage:

* Users and tenants
* Tasks and subtasks
* Plans and execution state
* Agents and tools
* Permissions and policies
* Short-term and long-term memory
* Artifacts and generated files
* Verification results
* Failure and recovery information
* Human approvals
* Execution events
* Model configurations
* Evaluation datasets and results
* Provenance and evidence

The architecture separates different classes of data based on their purpose rather than storing everything in a single database.

### High-Level Data Architecture

```text
                         ORION DATA ARCHITECTURE
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
          Operational Data                   AI / Knowledge Data
                 │                                 │
          ┌──────┴──────┐                  ┌───────┴────────┐
          │             │                  │                │
     Relational DB   Event Store       Memory Store    Evaluation Store
          │             │                  │                │
 Users / Tasks /     Execution         Short-term /     Benchmark /
 Agents / Tools /    Events / Audit    Long-term        Evaluation
 Permissions /       Trail             Memory           Results
 Policies
          │
          └────────────────┬────────────────┐
                           │                │
                    Artifact Storage    Model Metadata
                           │                │
                     Files / Reports     Models /
                     Documents /        Configurations
                     Generated Code
```

The relational database acts as the primary source of truth for transactional system state.

Specialized storage systems are used when their capabilities provide a clear architectural advantage.

---

# 2. Core Data Entities

ORION is organized around explicit entities representing the lifecycle of an autonomous task.

## 2.1 User

Represents a person interacting with ORION.

Typical attributes:

* `user_id`
* `tenant_id`
* `name`
* `email`
* `role`
* `status`
* `created_at`
* `updated_at`

Responsibilities:

* Authentication identity reference
* Ownership of tasks
* Access control
* User preferences
* Human approval decisions

---

## 2.2 Tenant

Represents an isolated organization or workspace.

Typical attributes:

* `tenant_id`
* `name`
* `status`
* `configuration`
* `created_at`
* `updated_at`

Responsibilities:

* Logical data isolation
* Tenant-level policies
* Resource quotas
* Configuration boundaries
* Usage and cost accounting

ORION should be designed so that multi-tenancy is possible even if the initial deployment uses only one tenant.

---

## 2.3 Task

Represents the high-level objective submitted to ORION.

Typical attributes:

* `task_id`
* `tenant_id`
* `user_id`
* `objective`
* `status`
* `priority`
* `created_at`
* `started_at`
* `completed_at`
* `parent_task_id`
* `metadata`

Possible statuses:

```text
CREATED
PLANNING
RUNNING
WAITING_FOR_HUMAN
VERIFYING
RECOVERING
COMPLETED
FAILED
CANCELLED
```

A task represents the overall execution lifecycle.

---

## 2.4 Subtask

Represents an individual unit of work derived from a task.

Typical attributes:

* `subtask_id`
* `task_id`
* `parent_subtask_id`
* `description`
* `status`
* `assigned_agent_id`
* `dependencies`
* `priority`
* `input_reference`
* `output_reference`
* `created_at`
* `started_at`
* `completed_at`

Subtasks allow ORION to transform a high-level objective into manageable execution units.

Subtasks may form a directed dependency graph rather than only a simple linear sequence.

---

## 2.5 Plan

Represents an execution strategy generated for a task.

Typical attributes:

* `plan_id`
* `task_id`
* `version`
* `plan_definition`
* `reasoning_summary`
* `status`
* `created_at`
* `updated_at`

A task may have multiple plan versions.

For example:

```text
Plan v1
   ↓
Execution failure
   ↓
Replanning
   ↓
Plan v2
   ↓
Successful execution
```

This enables ORION to measure whether replanning improves task success.

---

## 2.6 Agent

Represents a specialized AI worker.

Typical attributes:

* `agent_id`
* `name`
* `role`
* `description`
* `version`
* `capabilities`
* `allowed_tools`
* `permissions`
* `memory_policy`
* `model_configuration`
* `evaluation_policy`
* `status`

Example agents:

```text
Planner
Researcher
Analyst
Coder
Reviewer
Fact Checker
Writer
```

ORION should not create unnecessary agents.

Agent specialization must be justified through measurable improvements in task performance, reliability, cost, or latency.

---

## 2.7 Tool

Represents an executable capability available to agents.

Typical attributes:

* `tool_id`
* `name`
* `description`
* `version`
* `input_schema`
* `output_schema`
* `risk_level`
* `permissions_required`
* `timeout`
* `enabled`
* `audit_policy`

Examples:

```text
Web Search
Python Execution
File Reader
Database Query
Document Generator
Internal Retrieval
External API
```

Tools must be treated as controlled capabilities rather than unrestricted functions.

---

## 2.8 Execution

Represents an actual execution attempt.

Typical attributes:

* `execution_id`
* `task_id`
* `subtask_id`
* `agent_id`
* `tool_id`
* `attempt_number`
* `status`
* `input_reference`
* `output_reference`
* `started_at`
* `completed_at`
* `latency_ms`
* `error_code`

An execution represents what actually happened, while a plan represents what ORION intended to happen.

This distinction is important for debugging and evaluation.

---

## 2.9 Memory

Represents information retained by ORION for future or current execution.

Memory can be divided into:

### Short-Term Memory

Contains information relevant to the current task.

Examples:

* Current plan
* Intermediate results
* Recent tool outputs
* Current conversation state
* Temporary reasoning context

### Long-Term Memory

Contains information that may remain useful across tasks.

Examples:

* User preferences
* Successful strategies
* Reusable knowledge
* Historical task outcomes
* Important learned information

Typical attributes:

* `memory_id`
* `tenant_id`
* `user_id`
* `task_id`
* `memory_type`
* `content_reference`
* `embedding_reference`
* `importance`
* `source`
* `created_at`
* `expires_at`
* `retention_policy`

ORION should not automatically store everything.

Memory creation should follow explicit policies.

---

## 2.10 Artifact

Represents a file or persistent output generated or consumed during execution.

Examples:

* PDF reports
* CSV files
* Images
* Source code
* Charts
* Research documents
* JSON outputs
* Generated datasets

Typical attributes:

* `artifact_id`
* `tenant_id`
* `task_id`
* `created_by`
* `artifact_type`
* `storage_reference`
* `content_hash`
* `mime_type`
* `size_bytes`
* `version`
* `created_at`

Large binary content should not be stored directly inside the relational database.

---

## 2.11 Verification

Represents an evaluation of an intermediate or final result.

Typical attributes:

* `verification_id`
* `task_id`
* `execution_id`
* `verifier_type`
* `criteria`
* `result`
* `confidence`
* `evidence_reference`
* `created_at`

Possible results:

```text
PASS
FAIL
PARTIAL
UNCERTAIN
```

Verification is a first-class component because ORION must not blindly trust agent outputs.

---

## 2.12 Recovery

Represents a failure recovery attempt.

Typical attributes:

* `recovery_id`
* `task_id`
* `execution_id`
* `failure_type`
* `failure_description`
* `recovery_strategy`
* `attempt_number`
* `result`
* `created_at`

Possible strategies:

```text
RETRY
ALTERNATIVE_TOOL
REPLAN
ALTERNATIVE_AGENT
HUMAN_ESCALATION
TASK_TERMINATION
```

Recovery data enables measurement of autonomous resilience.

---

## 2.13 Human Approval

Represents an intervention or approval request involving a human.

Typical attributes:

* `approval_id`
* `task_id`
* `execution_id`
* `requested_action`
* `risk_level`
* `requested_from`
* `status`
* `decision`
* `reason`
* `created_at`
* `resolved_at`

Possible statuses:

```text
PENDING
APPROVED
REJECTED
EXPIRED
CANCELLED
```

Human intervention should be risk-based rather than triggered for every uncertainty.

---

## 2.14 Execution Event

Represents an event occurring during task execution.

Examples:

```text
TASK_CREATED
PLAN_CREATED
AGENT_STARTED
TOOL_CALLED
TOOL_COMPLETED
VERIFICATION_STARTED
VERIFICATION_FAILED
RECOVERY_STARTED
HUMAN_APPROVAL_REQUESTED
TASK_COMPLETED
TASK_FAILED
```

Typical attributes:

* `event_id`
* `task_id`
* `execution_id`
* `event_type`
* `timestamp`
* `actor`
* `payload`
* `correlation_id`

Events provide the execution history required for debugging and observability.

---

## 2.15 Evaluation Run

Represents one execution of an evaluation experiment.

Typical attributes:

* `evaluation_run_id`
* `name`
* `version`
* `dataset_version`
* `system_configuration`
* `model_configuration`
* `started_at`
* `completed_at`
* `status`

An evaluation run should be reproducible whenever possible.

---

## 2.16 Evaluation Case

Represents one benchmark task.

Typical attributes:

* `evaluation_case_id`
* `dataset_version`
* `task_definition`
* `expected_properties`
* `difficulty_level`
* `domain`
* `evaluation_metrics`

Example difficulty levels:

```text
LEVEL 1 — Simple tool usage
LEVEL 2 — Multi-step task
LEVEL 3 — Research + analysis
LEVEL 4 — Multi-agent execution
LEVEL 5 — Long-horizon autonomous task
```

---

## 2.17 Model Configuration

Represents the configuration used for an AI model execution.

Typical attributes:

* `model_config_id`
* `provider`
* `model_name`
* `model_version`
* `temperature`
* `max_tokens`
* `parameters`
* `created_at`

Model configurations must be versioned so experiments can be reproduced.

---

## 2.18 Permission

Represents an allowed capability.

Examples:

```text
READ_DOCUMENTS
WEB_SEARCH
EXECUTE_PYTHON
QUERY_DATABASE
WRITE_ARTIFACT
CALL_EXTERNAL_API
ACCESS_MEMORY
```

Permissions should be granted according to the principle of least privilege.

---

## 2.19 Policy

Represents an explicit system rule governing execution.

Examples:

```text
Agent cannot access secrets
Agent cannot delete production data
High-risk tools require human approval
External API calls require permission
Sensitive artifacts cannot leave tenant boundary
```

Policies should be configuration-driven whenever practical.

---

## 2.20 Evidence

Represents a source supporting a claim or result.

Typical attributes:

* `evidence_id`
* `task_id`
* `source_type`
* `source_reference`
* `location`
* `content_hash`
* `retrieved_at`
* `relevance_score`

Evidence is particularly important for research and knowledge-intensive tasks.

---

## 2.21 Entity Design Principle

Each entity should represent one meaningful concept.

ORION should avoid creating tables merely because a technology or framework recommends them.

The data model should remain:

* Explicit
* Traceable
* Versionable
* Auditable
* Extensible
* Queryable
* Secure

---

## 2.22 Core Entity Summary

| Entity              | Primary Responsibility                |
| ------------------- | ------------------------------------- |
| Tenant              | Isolation and organizational boundary |
| User                | Human identity and ownership          |
| Task                | High-level objective                  |
| Subtask             | Decomposed unit of work               |
| Plan                | Intended execution strategy           |
| Agent               | Specialized AI worker                 |
| Tool                | Controlled executable capability      |
| Execution           | Actual execution attempt              |
| Memory              | Retained information                  |
| Artifact            | Persistent file/output                |
| Verification        | Result validation                     |
| Recovery            | Failure handling                      |
| Human Approval      | Human intervention                    |
| Execution Event     | Execution history                     |
| Evidence            | Source supporting results             |
| Evaluation Run      | Benchmark experiment                  |
| Evaluation Case     | Individual benchmark task             |
| Model Configuration | AI model configuration                |
| Permission          | Allowed capability                    |
| Policy              | Execution rule                        |

---

# 3. Entity Relationships

The major relationships are:

```text
Tenant
  │
  ├── Users
  │
  ├── Tasks
  │     │
  │     ├── Plans
  │     │
  │     ├── Subtasks
  │     │     │
  │     │     └── Executions
  │     │
  │     ├── Artifacts
  │     ├── Verifications
  │     ├── Recoveries
  │     ├── Human Approvals
  │     ├── Events
  │     └── Evidence
  │
  ├── Agents
  │
  ├── Tools
  │
  ├── Policies
  │
  └── Permissions
```

Important relationship rules:

* One tenant can contain many users.
* One tenant can contain many tasks.
* One user can create many tasks.
* One task can contain many subtasks.
* One task can have multiple plan versions.
* One subtask can have multiple execution attempts.
* One agent can execute many subtasks.
* One agent can use multiple tools.
* One tool can be available to multiple agents subject to permissions.
* One execution can generate multiple events.
* One execution can have multiple verification results.
* One failed execution can produce multiple recovery attempts.
* One task can produce multiple artifacts.
* One task can reference multiple evidence sources.

Many-to-many relationships should be represented explicitly through association tables where appropriate.

Examples:

```text
Agent ↔ Tool
Agent ↔ Permission
Agent ↔ Policy
Task ↔ Evidence
Evaluation Run ↔ Evaluation Case
```

---

# 4. Database Architecture

ORION should use a polyglot storage architecture where each storage system has a clear responsibility.

## 4.1 Relational Database

The relational database is the primary source of truth for structured operational data.

It should store:

* Users
* Tenants
* Tasks
* Subtasks
* Plans
* Agents
* Tools
* Permissions
* Policies
* Executions
* Verifications
* Recoveries
* Human approvals
* Model configurations
* Artifact metadata
* Memory metadata

The relational database provides:

* Transactions
* Constraints
* Referential integrity
* Structured queries
* Consistency
* Reliable state transitions

---

## 4.2 Vector / Retrieval Storage

Vector-capable storage is used for semantic retrieval.

It may store:

* Memory embeddings
* Document embeddings
* Knowledge chunks
* Evidence representations

Each vector record should retain a reference to its original source.

The vector representation must never become the sole source of truth.

---

## 4.3 Object Storage

Object storage is used for large files.

Examples:

```text
PDF
DOCX
PPTX
CSV
Images
Generated reports
Source archives
Large datasets
```

The relational database stores metadata and references rather than the complete binary object.

---

## 4.4 Event Storage

Execution events may initially be stored in the relational database.

As system scale increases, a dedicated event or streaming architecture may be introduced if measurable requirements justify it.

This avoids premature infrastructure complexity.

---

## 4.5 Evaluation Storage

Evaluation datasets and results should be separated logically from operational task data.

Evaluation storage should contain:

* Benchmark cases
* Dataset versions
* Experiment configurations
* Evaluation results
* Metric results
* Baseline comparisons
* Failure analysis

This separation prevents production task data from becoming an uncontrolled benchmark.

---

# 5. Memory Architecture

Memory is divided into multiple layers.

```text
                  ORION MEMORY
                       │
          ┌────────────┴────────────┐
          │                         │
     Short-Term                 Long-Term
       Memory                     Memory
          │                         │
 Current Task State          Persistent Knowledge
 Intermediate Results        User Preferences
 Recent Context             Successful Strategies
 Temporary Information      Historical Outcomes
```

## 5.1 Short-Term Memory

Short-term memory contains information needed during the current execution.

Characteristics:

* Task-scoped
* Temporary
* High relevance
* Frequently updated
* May expire after task completion

---

## 5.2 Long-Term Memory

Long-term memory contains information that may be useful across future tasks.

Characteristics:

* Persistent
* Selectively stored
* Reusable
* Importance-ranked
* Subject to retention policies

---

## 5.3 Memory Lifecycle

```text
Candidate Information
        ↓
Importance Evaluation
        ↓
Policy Check
        ↓
Store / Reject
        ↓
Retrieve When Relevant
        ↓
Update / Decay / Expire
```

ORION should avoid uncontrolled memory growth.

---

## 5.4 Memory Provenance

Every persistent memory item should have traceability to its origin.

For example:

```text
Memory
   ↓
Source Task
   ↓
Execution
   ↓
Evidence / Artifact
```

This allows ORION to determine where a memory originated.

---

# 6. Artifact Storage

Artifacts are stored externally from the primary relational database.

Example:

```text
Task
  │
  ├── Artifact Metadata
  │       │
  │       └── Object Storage Reference
  │
  └── Artifact Version
```

Artifact metadata should include:

* Unique identifier
* Owner
* Task reference
* Type
* MIME type
* Size
* Hash
* Version
* Creation timestamp
* Storage location
* Access policy

Content hashes can be used to detect accidental corruption or duplicate artifacts.

---

# 7. Event Data

ORION should maintain a structured execution event history.

Example:

```text
TASK_CREATED
      ↓
PLAN_CREATED
      ↓
SUBTASK_CREATED
      ↓
AGENT_ASSIGNED
      ↓
TOOL_CALLED
      ↓
TOOL_COMPLETED
      ↓
VERIFICATION_FAILED
      ↓
RECOVERY_STARTED
      ↓
REPLAN_CREATED
      ↓
TOOL_CALLED
      ↓
VERIFICATION_PASSED
      ↓
TASK_COMPLETED
```

Each event should include:

* Event ID
* Task ID
* Execution ID when applicable
* Event type
* Timestamp
* Actor
* Correlation ID
* Structured payload

Events should be append-oriented whenever possible.

Historical events should not normally be modified after creation.

---

# 8. Data Provenance

Data provenance answers:

> Where did this information come from?

ORION should maintain provenance for important outputs and claims.

A provenance chain may look like:

```text
Final Claim
    ↓
Agent Output
    ↓
Verification Result
    ↓
Execution
    ↓
Tool Result
    ↓
External Source
```

For generated artifacts:

```text
Artifact
    ↓
Generation Execution
    ↓
Agent
    ↓
Input Data
    ↓
Source Evidence
```

Provenance improves:

* Trust
* Debugging
* Verification
* Reproducibility
* Auditability
* Hallucination analysis

---

# 9. Data Isolation and Security

Security must be enforced at multiple layers.

## 9.1 Tenant Isolation

Tenant-specific data must not be accessible across tenant boundaries.

Every relevant operational entity should contain or inherit a tenant boundary.

---

## 9.2 User Authorization

Users should only access resources for which they have permission.

Example:

```text
User
  ↓
Authentication
  ↓
Authorization
  ↓
Tenant Check
  ↓
Resource Permission
  ↓
Data Access
```

---

## 9.3 Agent Data Access

Agents must not automatically receive access to all data.

Access should depend on:

* Agent identity
* Task context
* Tool permissions
* Policy
* Tenant boundary
* Data sensitivity

---

## 9.4 Sensitive Data

Secrets and credentials must not be stored inside normal task records.

Sensitive configuration should be managed separately from application data.

---

## 9.5 Auditability

Important data access and execution actions should be auditable.

Examples:

* Who accessed the resource
* Which agent accessed it
* Which tool was used
* When access occurred
* What action was performed
* Whether human approval was required

---

# 10. Data Lifecycle

Data should have defined lifecycle policies.

```text
Created
   ↓
Active
   ↓
Updated / Versioned
   ↓
Archived
   ↓
Deleted / Expired
```

Different data types may have different retention periods.

Examples:

| Data                     | Possible Lifecycle                  |
| ------------------------ | ----------------------------------- |
| Active Task              | Retained                            |
| Execution Events         | Long-term audit retention           |
| Short-Term Memory        | Temporary                           |
| Long-Term Memory         | Policy-based                        |
| Artifacts                | Policy-based                        |
| Evaluation Results       | Long-term                           |
| Temporary Files          | Automatic cleanup                   |
| Failed Intermediate Data | Shorter retention where appropriate |

Retention should consider:

* Storage cost
* Privacy
* Security
* Audit requirements
* Debugging needs
* Regulatory requirements where applicable

Deletion should respect dependency relationships and audit requirements.

---

# 11. Data Consistency

ORION contains long-running asynchronous workflows, so consistency must be designed explicitly.

## 11.1 Transactional Consistency

Critical state changes should use database transactions.

Examples:

```text
Task status change
Approval decision
Permission update
Plan version creation
Execution state transition
```

---

## 11.2 Idempotency

Operations that may be retried should be idempotent where possible.

Example:

```text
Tool execution request
       ↓
Unique operation ID
       ↓
Retry
       ↓
System detects previous attempt
       ↓
Avoid unintended duplicate side effect
```

---

## 11.3 Concurrency

Multiple agents may operate simultaneously.

The system must therefore handle:

* Concurrent task updates
* Duplicate events
* Race conditions
* Conflicting state transitions
* Concurrent artifact creation
* Parallel subtasks

Optimistic locking, unique constraints, state validation, and transactional updates may be used where appropriate.

---

## 11.4 State Machine Integrity

Task and execution status transitions should be validated.

Example:

```text
CREATED
   ↓
PLANNING
   ↓
RUNNING
   ↓
VERIFYING
   ↓
COMPLETED
```

Invalid transitions should be rejected.

For example:

```text
COMPLETED → RUNNING
```

should not occur unless an explicitly supported workflow allows it.

---

# 12. Initial Database Schema

The initial relational schema should include tables conceptually similar to:

```text
tenants
users

tasks
subtasks
plans
plan_versions

agents
agent_versions

tools
tool_versions

permissions
policies

agent_tools
agent_permissions
agent_policies

executions
execution_events

memories
memory_sources

artifacts
artifact_versions

evidence
verifications
recoveries
human_approvals

model_configurations

evaluation_runs
evaluation_cases
evaluation_results
```

Additional tables may be introduced when implementation requirements justify them.

---

## 12.1 Example Task Record

```text
tasks
------------------------------------------------
task_id
tenant_id
user_id
parent_task_id
objective
status
priority
created_at
started_at
completed_at
metadata
```

---

## 12.2 Example Execution Record

```text
executions
------------------------------------------------
execution_id
task_id
subtask_id
agent_id
tool_id
attempt_number
status
input_reference
output_reference
started_at
completed_at
latency_ms
error_code
metadata
```

---

## 12.3 Example Agent-Tool Relationship

```text
agent_tools
------------------------------------------------
agent_id
tool_id
permission_id
enabled
created_at
```

This allows many agents to use many tools while keeping the relationship explicit.

---

## 12.4 Example Memory Record

```text
memories
------------------------------------------------
memory_id
tenant_id
user_id
task_id
memory_type
content_reference
embedding_reference
importance
source
created_at
expires_at
retention_policy
```

---

# 13. Data Architecture Quality Requirements

The ORION data architecture should satisfy the following requirements.

## 13.1 Reliability

Data should survive:

* Process crashes
* Worker failures
* Network failures
* Retry operations
* Partial task failures

---

## 13.2 Traceability

The system should be able to answer:

```text
What happened?
Why did it happen?
Which agent did it?
Which tool was used?
What data was used?
What evidence supported the result?
What failed?
How was the failure recovered?
Was a human involved?
```

---

## 13.3 Reproducibility

Important executions should retain sufficient metadata to reproduce or investigate them.

This includes:

* Model configuration
* Agent version
* Tool version
* Plan version
* Relevant prompts/instructions where appropriate
* Input references
* Output references
* Evaluation configuration
* Execution timestamps

---

## 13.4 Security

The data layer must support:

* Authentication
* Authorization
* Tenant isolation
* Least privilege
* Secure secret handling
* Auditability
* Data access controls

---

## 13.5 Performance

The architecture should support:

* Fast task-state queries
* Efficient event retrieval
* Semantic retrieval
* Large artifact storage
* Parallel task execution
* Scalable evaluation workloads

Performance should be measured rather than assumed.

---

## 13.6 Versioning

Important components should be versioned.

Examples:

```text
Task Plan
Agent
Tool
Model Configuration
Artifact
Evaluation Dataset
Evaluation Run
Memory Policy
```

Versioning allows ORION to compare system behavior over time.

---

# 14. Data Architecture Design Principles Summary

The ORION data architecture follows these principles:

### Principle 1 — Source of Truth

Operational state must have a clearly defined authoritative source.

### Principle 2 — Separation of Concerns

Transactional data, vector data, binary artifacts, events, and evaluation data should have distinct responsibilities.

### Principle 3 — Traceability

Important outputs should be traceable to their sources and execution history.

### Principle 4 — Least Privilege

Agents and users receive only the data access required for their tasks.

### Principle 5 — Version Everything Important

Plans, agents, tools, models, artifacts, and evaluation datasets should be versionable.

### Principle 6 — Safe Retries

The system must protect against duplicate side effects during retries.

### Principle 7 — Explicit State

Task and execution states must be represented explicitly and validated.

### Principle 8 — Policy-Based Retention

Memory and artifacts should not grow without control.

### Principle 9 — Reproducibility

Important experiments and executions should contain sufficient metadata for investigation and comparison.

### Principle 10 — Evidence-Grounded Intelligence

Important outputs should retain links to the evidence that supports them.

### Principle 11 — Measurable Architecture

Data architecture decisions should ultimately be validated through performance, reliability, cost, and operational measurements.

---

# 15. Final Data Architecture Goal

The final ORION data architecture should enable the system to answer the following questions for any important task:

```text
WHO
  → submitted the task?

WHAT
  → was the objective?

HOW
  → was the task planned?

WHICH AGENTS
  → participated?

WHICH TOOLS
  → were used?

WHAT DATA
  → was accessed?

WHAT HAPPENED
  → during execution?

WHAT FAILED
  → and why?

HOW WAS IT RECOVERED
  → retry, replan, alternative tool, or human intervention?

WHAT EVIDENCE
  → supports the result?

WHAT WAS VERIFIED
  → before completion?

WHAT DID IT COST
  → in tokens, latency, compute, and external services?

CAN IT BE REPRODUCED
  → or investigated later?

WHO WAS ALLOWED
  → to access the data?

```

The ultimate goal is not simply to store ORION's data.

The goal is to create a **reliable, secure, traceable, versioned, reproducible, and measurable data foundation for autonomous AI execution.**

ORION should therefore treat data architecture as part of the intelligence system itself—not merely as a storage layer.

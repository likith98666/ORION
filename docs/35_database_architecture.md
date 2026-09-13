# ORION — Database Architecture

## 1. Database Architecture Overview

The ORION database architecture defines how persistent application data is stored, queried, updated, protected, versioned, and recovered.

ORION is a long-running autonomous AI system.

It therefore requires reliable storage for:

* users
* tenants
* tasks
* subtasks
* plans
* agents
* tools
* executions
* state
* approvals
* verification results
* recovery attempts
* events
* memory metadata
* artifacts
* evaluations
* model configurations
* policies
* permissions
* audit records

---

## 2. Database Goals

The database architecture should provide:

* correctness
* durability
* consistency
* transactional integrity
* concurrency safety
* scalability
* security
* tenant isolation
* observability
* recoverability
* efficient querying
* schema evolution
* reproducibility

---

## 3. Database Philosophy

The database should be selected based on actual requirements.

ORION should not use multiple databases simply because they are popular technologies.

Every storage technology must have a clear responsibility.

---

## 4. Primary Database

The primary transactional database should be relational.

A PostgreSQL-based implementation is a strong initial choice because ORION requires:

* relational data
* transactions
* constraints
* joins
* indexing
* concurrency control
* JSON support
* mature tooling

The architecture should remain conceptually database-aware rather than tightly coupled to undocumented vendor behavior.

---

## 5. Source of Truth

The primary relational database should be the source of truth for transactional application state.

Examples:

```text id="a5r8f2"
Task
Subtask
Execution
Approval
Verification
Agent
Tool
Policy
Permission
```

---

## 6. Storage Responsibilities

Different data types may use different storage systems.

```text id="m7q3d1"
PostgreSQL
→ transactional metadata and state

Vector Store
→ embeddings and vector retrieval

Object Storage
→ large files and artifacts

Cache
→ temporary high-speed access
```

Each system should have a defined responsibility.

---

## 7. Why Relational Storage?

ORION has strongly related entities.

For example:

```text id="h4k8p6"
Tenant
 ↓
User
 ↓
Task
 ↓
Subtask
 ↓
Execution
 ↓
Agent
 ↓
Tool
```

A relational model naturally represents these relationships.

---

## 8. Database Entities

Important entities include:

* Tenant
* User
* Task
* Subtask
* Plan
* Plan Version
* Agent
* Tool
* Execution
* Execution Attempt
* Approval
* Verification
* Recovery
* Artifact Metadata
* Event
* Memory Metadata
* Evaluation Run
* Evaluation Case
* Model Configuration
* Permission
* Policy
* Evidence
* Audit Record

---

## 9. Tenant Table

The tenant represents an isolated logical customer or workspace.

Potential fields:

```text id="j8f2s5"
tenant_id
name
status
created_at
updated_at
```

---

## 10. User Table

Potential fields:

```text id="q5n7c4"
user_id
tenant_id
identity_reference
role
status
created_at
updated_at
```

---

## 11. Task Table

Potential fields:

```text id="w3k6m9"
task_id
tenant_id
created_by
title
objective
status
priority
plan_id
created_at
started_at
completed_at
updated_at
version
```

---

## 12. Subtask Table

Potential fields:

```text id="r4x8v2"
subtask_id
task_id
parent_subtask_id
description
status
assigned_agent
priority
dependency_count
created_at
started_at
completed_at
version
```

---

## 13. Plan Table

A plan represents the logical execution strategy.

Potential fields:

```text id="k6m3y9"
plan_id
task_id
current_version
status
created_at
updated_at
```

---

## 14. Plan Version Table

Plans should be versioned.

Example:

```text id="f7q2n4"
Plan v1
Plan v2
Plan v3
```

This allows ORION to determine which strategy produced an outcome.

---

## 15. Agent Table

The agent registry may store:

```text id="b9m5x3"
agent_id
name
role
version
status
configuration
created_at
updated_at
```

---

## 16. Tool Table

The tool registry may store:

```text id="v8p4c6"
tool_id
name
version
risk_level
status
configuration
created_at
updated_at
```

Sensitive credentials should never be stored directly in ordinary tool records.

---

## 17. Execution Table

Execution represents a concrete attempt to perform work.

Potential fields:

```text id="n4s7k2"
execution_id
task_id
subtask_id
agent_id
worker_id
status
attempt_number
started_at
completed_at
error_code
checkpoint_id
version
```

---

## 18. Execution Attempts

A single subtask may have multiple attempts.

Example:

```text id="y5c8m1"
Attempt 1 → FAILED
Attempt 2 → FAILED
Attempt 3 → COMPLETED
```

The database should preserve this history.

---

## 19. Approval Table

Human approval records may include:

```text id="p4v7q8"
approval_id
task_id
requested_by
approved_by
action
risk_level
status
reason
created_at
resolved_at
expires_at
```

---

## 20. Verification Table

Verification records may include:

```text id="h7m3c9"
verification_id
task_id
execution_id
verifier
status
score
criteria
evidence_reference
created_at
```

---

## 21. Recovery Table

Recovery records may include:

```text id="x6n4r8"
recovery_id
execution_id
failure_type
strategy
attempt_number
status
reason
created_at
completed_at
```

---

## 22. Event Table

Events may be stored for historical and audit purposes.

Potential fields:

```text id="s5q9k3"
event_id
tenant_id
task_id
event_type
event_version
correlation_id
causation_id
sequence_number
payload
created_at
```

Large event payloads should be handled carefully.

---

## 23. Audit Table

Security-sensitive operations should have audit records.

Examples:

* login
* authorization decisions
* policy changes
* approval decisions
* secret access
* permission changes
* administrative actions

---

## 24. Evidence Table

Evidence records may associate outputs with their supporting sources.

Potential fields:

```text id="m2v8f4"
evidence_id
task_id
artifact_id
source_type
source_reference
content_reference
confidence
created_at
```

---

## 25. Artifact Metadata Table

The database should store metadata about artifacts rather than necessarily storing large binary content directly.

Example:

```text id="g5n7w2"
artifact_id
task_id
execution_id
artifact_type
storage_reference
size
checksum
mime_type
created_at
```

---

## 26. Memory Metadata

Memory records may contain:

```text id="c8r4p6"
memory_id
tenant_id
memory_type
source
confidence
importance
created_at
updated_at
expires_at
version
```

Actual vector embeddings may be stored in a vector-capable storage layer.

---

## 27. Model Configuration Table

Model configurations should be versioned.

Potential fields:

```text id="f3q6x8"
model_config_id
provider
model_name
version
capabilities
configuration
status
created_at
```

Secrets must remain outside ordinary configuration records.

---

## 28. Policy Table

Policies may contain:

```text id="j4m8v5"
policy_id
tenant_id
name
version
rules
status
created_at
updated_at
```

---

## 29. Permission Table

Permissions define what identities or components are allowed to do.

Potential relationships:

```text id="v6c9s2"
Principal
 ↓
Permission
 ↓
Resource
 ↓
Action
```

---

## 30. Database Relationships

Core relationships include:

```text id="r8f3n6"
Tenant
 ├── Users
 ├── Tasks
 ├── Memories
 ├── Policies
 └── Audit Records

Task
 ├── Subtasks
 ├── Plans
 ├── Executions
 ├── Approvals
 ├── Verifications
 ├── Recoveries
 ├── Events
 └── Artifacts
```

---

## 31. Foreign Keys

Foreign keys should be used where they provide meaningful integrity guarantees.

Examples:

```text id="w6h4k9"
task.tenant_id
→ tenant.id

subtask.task_id
→ task.id

execution.task_id
→ task.id
```

---

## 32. Referential Integrity

The database should prevent invalid references.

For example, an execution should not reference a nonexistent task.

---

## 33. Cascading Deletes

Cascading deletion should be used carefully.

Automatic cascading may accidentally remove large amounts of historical information.

Explicit lifecycle policies are preferred for important data.

---

## 34. Transactions

Operations affecting multiple related records should use transactions where atomicity is required.

Example:

```text id="p7m4x8"
Create Task
+
Create Initial State
+
Create Event
```

may require an atomic transaction boundary.

---

## 35. Transaction Boundaries

Transactions should be:

* short
* explicit
* predictable
* failure-safe

Long-running AI execution should not remain inside a database transaction.

---

## 36. Long-Running Tasks

LLM calls, web requests, Python execution, and other long-running operations should happen outside ordinary database transactions.

Their progress should be persisted through separate state updates.

---

## 37. Atomic State Updates

State transitions should be updated atomically.

Example:

```text id="c5v7m2"
Current State = RUNNING
Version = 12

Update:
State = COMPLETED
Version = 13
```

---

## 38. Optimistic Concurrency

Version numbers can prevent stale updates.

Conceptually:

```text id="x8n4q6"
UPDATE task
SET status = 'COMPLETED',
    version = version + 1
WHERE task_id = ?
AND version = 12
```

If zero rows are updated, the state may have changed concurrently.

---

## 39. Database Locks

Locks may be used for operations where concurrent modification could cause serious corruption.

Locks should be narrowly scoped.

---

## 40. Deadlock Prevention

The application should minimize deadlocks by:

* keeping transactions short
* acquiring locks in consistent order
* avoiding unnecessary locks
* detecting transaction failures

---

## 41. Indexing

Indexes should support common query patterns.

Likely indexed fields include:

```text id="m9f2s5"
tenant_id
task_id
status
created_at
updated_at
execution_id
agent_id
event_type
correlation_id
```

---

## 42. Index Design

Indexes should be driven by measured query patterns.

Too many indexes increase:

* storage
* write cost
* maintenance overhead

---

## 43. Composite Indexes

Composite indexes may support common queries.

Example:

```text id="h7q5r3"
tenant_id + status + created_at
```

Actual indexes should be validated using query plans and production-like workloads.

---

## 44. Query Optimization

Slow queries should be investigated using:

* query plans
* execution statistics
* indexes
* data volume
* connection usage

---

## 45. Pagination

Large result sets should use pagination.

APIs should not load thousands of task records unnecessarily.

---

## 46. Cursor Pagination

Cursor-based pagination may be preferred for large or frequently changing datasets.

---

## 47. Database Connection Pooling

The application should use controlled database connection pools.

Pool size should be based on:

* workload
* database capacity
* number of workers
* query behavior

---

## 48. Connection Limits

Unbounded database connections can overload the database.

Connection limits should therefore be explicitly configured.

---

## 49. Database Availability

The system should detect database health through appropriate health checks.

---

## 50. Database Failure Handling

If the database becomes temporarily unavailable:

```text id="f6p8v3"
Detect Failure
 ↓
Retry Safe Operation
 ↓
Backoff
 ↓
Recover
```

Retries must not duplicate unsafe side effects.

---

## 51. Database Retry Policy

Retry behavior should consider:

* transient errors
* connection failures
* deadlocks
* serialization conflicts
* timeout errors

Permanent errors should not be retried indefinitely.

---

## 52. Database Circuit Protection

Repeated database failures may require temporary traffic reduction or fail-fast behavior.

---

## 53. Database Migrations

Schema changes should use controlled migrations.

Every migration should be:

* versioned
* reviewed
* tested
* reversible where practical

---

## 54. Backward Compatibility

During deployment, application versions may overlap.

Schema changes should therefore support safe transitions between compatible application versions.

---

## 55. Migration Testing

Before production:

```text id="k3v9m5"
Backup
 ↓
Migration
 ↓
Validation
 ↓
Application Tests
 ↓
Rollback Test
```

should be performed where appropriate.

---

## 56. Database Backups

Backups should protect against:

* accidental deletion
* corruption
* infrastructure failure
* deployment mistakes
* security incidents

---

## 57. Backup Verification

A backup is not considered reliable merely because it exists.

Restore procedures should be tested periodically.

---

## 58. Recovery Objectives

Database disaster recovery should define:

### RPO

Maximum acceptable data loss.

### RTO

Maximum acceptable restoration time.

Actual values should be defined according to deployment requirements.

---

## 59. Database Security

Database security should include:

* authentication
* authorization
* encryption in transit
* encryption at rest where supported
* least privilege
* network restrictions
* secret management
* audit logging

---

## 60. Application Database User

The application should use a dedicated database identity rather than a superuser.

---

## 61. Least Privilege

Different components should receive only the permissions they need.

Example:

```text id="q7m4c9"
Application
→ normal application access

Migration Tool
→ schema modification

Analytics
→ read-only access
```

---

## 62. SQL Injection Protection

Database queries should use parameterized queries or safe ORM/query-builder mechanisms.

User input must never be concatenated directly into SQL.

---

## 63. Row-Level Isolation

Tenant-sensitive data should always be filtered by tenant scope.

Additional database-level controls may be used where appropriate.

---

## 64. Tenant Isolation

A task from Tenant A must never accidentally appear in Tenant B's queries.

Isolation should exist at multiple layers:

```text id="r4n8x2"
API
 ↓
Authorization
 ↓
Application Query
 ↓
Database
```

---

## 65. Sensitive Data

The database may contain:

* user information
* task content
* prompts
* model outputs
* evidence
* operational metadata

Sensitive data should be classified and protected accordingly.

---

## 66. Secret Storage

API keys, passwords, tokens, and credentials should not be stored as ordinary database fields.

A dedicated secret-management mechanism should be used.

---

## 67. Data Encryption

Sensitive information should be protected during:

```text id="m8q5v3"
Application → Database
Database → Backup
```

according to deployment requirements.

---

## 68. Auditability

Important database-related operations should be traceable.

Audit records should answer:

```text id="x5f7k2"
Who?
What?
When?
Why?
Which resource?
What changed?
```

---

## 69. Database Observability

Important database metrics include:

* query latency
* query error rate
* connection usage
* transaction rate
* lock contention
* deadlocks
* CPU usage
* memory usage
* storage usage
* replication health where applicable

---

## 70. Database Performance

Performance should be measured under realistic workloads.

Important measurements include:

* p50 latency
* p95 latency
* p99 latency
* throughput
* connection utilization

---

## 71. Database Load Testing

Load tests should simulate:

* concurrent tasks
* concurrent state updates
* event insertion
* task listing
* execution updates
* approval operations

---

## 72. Database Stress Testing

Stress testing should determine behavior beyond expected operating load.

The goal is to identify:

* bottlenecks
* lock contention
* connection exhaustion
* query degradation

---

## 73. Database Caching

Caching may reduce repeated database reads.

However:

> Cached data must never silently become more authoritative than transactional state.

---

## 74. Cache Invalidation

Cache invalidation should occur through controlled mechanisms such as:

* TTL
* explicit invalidation
* event-driven invalidation

---

## 75. Database and Event Architecture

Database updates and event publication should be coordinated carefully.

An important pattern is the transactional outbox.

Conceptually:

```text id="q9c4m6"
Database Transaction
       |
       +--> State Update
       |
       +--> Outbox Event
       
After Commit
       |
       ↓
Event Publisher
```

This reduces the risk of state changing without its corresponding event being published.

---

## 76. Database and State Management

The database stores durable execution state.

The State Manager determines valid state transitions.

The database enforces persistence and integrity.

---

## 77. Database and Memory

Transactional metadata for memory may reside in the relational database.

Large vector data may reside in a vector-capable storage system.

---

## 78. Database and Artifacts

Large artifacts should generally remain outside the relational database.

The database stores metadata and references.

---

## 79. Database and Evaluation

Evaluation records should be isolated from production task state where appropriate.

Evaluation datasets and experiment results should have clear versioning.

---

## 80. Database and Observability

Operational telemetry may be stored in specialized observability systems rather than forcing all telemetry into the primary database.

---

## 81. Database and Multi-Agent Execution

Multiple agents may concurrently access shared transactional state.

Concurrency controls must prevent:

* duplicate updates
* conflicting state transitions
* unauthorized access

---

## 82. Database and Human Approval

Approval state must be durable.

A system restart must not lose a pending approval.

---

## 83. Database and Recovery

Recovery operations should reference persistent execution and failure history.

---

## 84. Database and Reproducibility

Important experiment metadata should record:

* model version
* configuration
* prompt version
* agent version
* tool version
* dataset version
* evaluation version

---

## 85. Database Schema Versioning

Database schema versions should be tracked independently from application versions.

---

## 86. Data Lifecycle

A typical lifecycle is:

```text id="b8f5k3"
Created
 ↓
Active
 ↓
Completed
 ↓
Retained
 ↓
Archived
 ↓
Deleted
```

Actual lifecycle depends on data category.

---

## 87. Data Retention

Retention should be based on:

* operational value
* compliance requirements
* privacy
* cost
* debugging
* reproducibility

---

## 88. Data Archival

Historical records that are no longer required for active operations may be archived.

---

## 89. Data Deletion

Deletion must consider dependencies.

For example, deleting a task should not unintentionally destroy required audit records.

---

## 90. Soft Deletion

Soft deletion may be appropriate for certain records requiring recovery or auditability.

---

## 91. Hard Deletion

Hard deletion may be required for:

* expired temporary data
* privacy-driven deletion
* obsolete operational data

It must follow defined policies.

---

## 92. Database Testing

Database testing should include:

* schema tests
* migration tests
* constraint tests
* transaction tests
* concurrency tests
* query tests
* backup/restore tests

---

## 93. Data Integrity Testing

Tests should verify:

* foreign keys
* unique constraints
* state consistency
* tenant isolation
* transaction atomicity

---

## 94. Concurrency Testing

Simulate:

```text id="n6r4x9"
Worker A → Update Task
Worker B → Update Task
Worker C → Cancel Task
```

and verify deterministic, valid behavior.

---

## 95. Failure Injection

Simulate:

* database disconnect
* transaction rollback
* deadlock
* timeout
* worker crash
* partial failure

---

## 96. Database Security Testing

Security testing should include:

* SQL injection
* authorization bypass
* tenant isolation
* privilege escalation
* credential exposure
* unsafe migrations

---

## 97. Database Evaluation Metrics

Potential metrics include:

```text id="v3k8q5"
Query p95 latency
Transaction success rate
Deadlock rate
Connection utilization
Storage growth
Backup recovery success
Migration success rate
```

---

## 98. Database Scalability

Initial architecture should support vertical scaling and sensible indexing.

Horizontal scaling should be introduced only when actual workload requires it.

Potential future techniques include:

* read replicas
* partitioning
* sharding
* workload-specific databases

---

## 99. Avoiding Premature Complexity

ORION should not immediately introduce:

* distributed databases
* sharding
* multiple relational databases
* complex replication systems

without measurable requirements.

---

## 100. Database Documentation

Database documentation should describe:

* schema
* relationships
* indexes
* constraints
* migrations
* retention
* backup
* recovery
* security

---

## 101. Database Architecture Summary

The initial architecture is:

```text id="c6m9p4"
                ORION APPLICATION
                       |
                       ↓
                Database Layer
                       |
          +------------+------------+
          |            |            |
     PostgreSQL    Vector Store  Object Storage
          |            |            |
     State/Data     Embeddings     Artifacts
          |
      Transactions
          |
       Outbox
          |
        Events
```

---

## 102. Database Design Principles

The major principles are:

1. Use a relational database for transactional state.
2. Keep storage responsibilities clearly separated.
3. Treat the primary database as the source of truth.
4. Use transactions where atomicity matters.
5. Use concurrency control for shared state.
6. Protect tenant boundaries.
7. Never store secrets as ordinary data.
8. Use indexes based on measured workloads.
9. Version database schemas.
10. Test backups and recovery.
11. Monitor database performance.
12. Avoid premature database complexity.

---

## 103. Database Quality Gate

Before production, ORION should demonstrate:

* correct schema
* referential integrity
* transaction safety
* concurrency safety
* tenant isolation
* secure access
* migration reliability
* backup capability
* restore capability
* performance measurements
* failure handling
* observability

---

## 104. Final Database Architecture Goal

The ultimate goal is:

> Build a secure, durable, consistent, observable, and scalable data layer that provides ORION with a trustworthy source of truth for autonomous execution.

The goal is not:

**"Connect ORION to PostgreSQL."**

The goal is:

**"Create a reliable data foundation on which autonomous AI execution can safely operate."**

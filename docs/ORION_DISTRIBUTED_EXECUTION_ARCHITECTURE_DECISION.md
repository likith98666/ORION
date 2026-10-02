# ORION Architecture Decision Record: Distributed Execution Boundary

## Status: APPROVED (OPTION A)

**Date**: 2026-10-03  
**Context**: ORION V10 Final Release Candidate  
**Decision Authority**: ORION Core Architecture Team  

---

## 1. Context and Problem Statement

The ORION V1–V9 roadmap reconciliation audit identified that while the original V7 concept contemplated "Distributed Production Execution", ORION's actual implementation developed a robust, single-node, multi-threaded execution engine coupled with Human-in-the-Loop collaborative oversight (V7), Central Policy Engine security (V8), and Distributed Telemetry & Observability (V9).

Prior to freezing V10, an architectural decision is required:
* **Option A**: Harden and stabilize the current single-node execution architecture, define its boundaries with rigorous mathematical precision, and declare multi-node clustering as future out-of-process infrastructure.
* **Option B**: Introduce minimal distributed clustering infrastructure (distributed task queues, Redis/etcd distributed locks, worker heartbeats, and remote node eviction recovery).

---

## 2. Evaluation Criteria

1. **Current Single-Node Capabilities**:
   * Thread-safe multi-worker task execution (`agent_executor.py`, `mission_engine.py`).
   * Asynchronous message passing via Python `queue.Queue`.
   * High-throughput `ThreadingHTTPServer` with connection pooling, rate limiting, and SSE streaming.
   * Atomic file operations and workspace containment.
   * Deterministic test reproducibility (1,388 passing tests executing in <90 seconds).

2. **Operational Complexity of Option B**:
   * Requiring Redis, Celery, or Kafka introduces external daemon dependencies, breaking zero-configuration local installation and developer ergonomics.
   * Distributed consensus (raft/leases) introduces non-deterministic network partition failure modes that complicate self-healing verification.
   * Workspace synchronization across multiple physical servers requires distributed network file systems (NFS/Ceph), creating substantial latency penalties for AST parsing and test execution.

3. **Production Alignment**:
   * Autonomous software engineering tasks are inherently repo-centric and workspace-bound. Running an agentic SWE workflow within an isolated container or dedicated developer virtual machine with bounded high-performance NVMe storage provides superior execution speed, sandbox containment, and security isolation compared to distributed remote workers.

---

## 3. Decision: Option A — Hardened Single-Node Architecture

ORION formally adopts **Option A** for the V10 Final Release Candidate.

### Key Architectural Tenets of Option A:
1. **Single-Node Multi-Threading Sovereignty**:
   ORION executes as a sovereign, self-contained single-node application. All concurrency is handled via Python threading primitives, thread-safe memory queues, and non-blocking IO.
2. **Explicit Boundary Definition**:
   ORION makes **zero false claims** of being a distributed cluster. The "Distributed" nomenclature in V9 applies specifically to *Distributed Tracing and Telemetry Context Propagation* (W3C trace context, span trees, parent-child correlations across agent/tool boundaries), not multi-node hardware clustering.
3. **Container-Level Scalability**:
   Multi-tenant or fleet-wide scale is achieved via horizontal container replication (each ORION instance owning an independent workspace/mission), orchestrated via standard container runtimes (Docker, Kubernetes) rather than internal distributed queue brokers.
4. **Hardened Lifecycle & Cleanup**:
   All in-process queues, worker threads, and workspace checkouts must guarantee graceful shutdown, leak-free termination, and transactional memory serialization.

---

## 4. Consequences and Validation

* **Positive**: Zero external service dependencies, deterministic reproducibility, 100% test reliability, instant setup via `pip install -e .`, and sub-second IPC latency.
* **Trade-off**: Individual long-running missions cannot migrate live in-flight execution state across physical nodes mid-step if the host operating system suffers a catastrophic power loss.
* **Mitigation**: `MissionMemory` periodically persists state checkpoints, allowing missions to be resumed safely after restart.

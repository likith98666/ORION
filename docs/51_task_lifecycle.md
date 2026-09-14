# ORION Task Lifecycle

## 1. Purpose

The ORION task lifecycle defines the valid states and transitions
through which an autonomous task can move from creation to completion,
failure, or cancellation.

The lifecycle provides a controlled state machine for task execution.

---

## 2. Task States

### CREATED

The task has been accepted by ORION but execution has not started.

Typical activities:

- Validate the task objective
- Store the task
- Assign a task ID
- Prepare the task for planning

Valid next states:

- PLANNING
- CANCELLED

---

### PLANNING

ORION is analyzing the objective and preparing an execution plan.

Typical activities:

- Understand the objective
- Decompose the objective
- Identify required capabilities
- Select appropriate agents
- Identify required tools
- Build an execution plan

Valid next states:

- RUNNING
- CANCELLED

---

### RUNNING

The task is actively being executed.

Typical activities:

- Execute planned steps
- Invoke agents
- Use tools
- Process results
- Maintain task state

Valid next states:

- WAITING
- VERIFYING
- FAILED
- CANCELLED

---

### WAITING

Execution is temporarily paused.

Possible reasons:

- Human approval required
- External dependency
- Additional information required
- Temporary resource availability issue

Valid next states:

- RUNNING
- CANCELLED

---

### VERIFYING

The task execution has produced a result that must be evaluated.

Typical activities:

- Check correctness
- Check completeness
- Check evidence
- Check consistency
- Detect unsupported claims
- Evaluate output quality

Valid next states:

- COMPLETED
- FAILED

---

### COMPLETED

The task has successfully passed verification.

This is a terminal state.

No further task execution is permitted.

---

### FAILED

The task could not successfully complete its current execution.

Possible reasons:

- Agent failure
- Tool failure
- Invalid result
- Verification failure
- Execution error
- Resource failure

Valid next states:

- PLANNING
- CANCELLED

Returning to PLANNING allows ORION's future recovery system
to create a new plan after failure.

---

### CANCELLED

The task has been intentionally stopped.

This is a terminal state.

No further task execution is permitted.

---

## 3. State Transition Rules

The valid transitions are:

```text
CREATED
    |
    +----> PLANNING
    |
    +----> CANCELLED


PLANNING
    |
    +----> RUNNING
    |
    +----> CANCELLED


RUNNING
    |
    +----> WAITING ----> RUNNING
    |
    +----> VERIFYING
    |
    +----> FAILED
    |
    +----> CANCELLED


VERIFYING
    |
    +----> COMPLETED
    |
    +----> FAILED


FAILED
    |
    +----> PLANNING
    |
    +----> CANCELLED


COMPLETED
    |
    +----> TERMINAL


CANCELLED
    |
    +----> TERMINAL
---

## 4. Terminal States

The following states are terminal:

- COMPLETED
- CANCELLED

Once a task enters a terminal state, it cannot transition
to another state.

---

## 5. Recovery

FAILED is intentionally not a terminal state.

A failed task may return to PLANNING.

This allows future ORION recovery mechanisms to:

1. Detect failure
2. Analyze the failure
3. Determine whether recovery is possible
4. Create a new execution plan
5. Resume execution

The recovery mechanism will be implemented separately from
the task state model.

---

## 6. Design Principle

The Task object represents the lifecycle of a task.

It should not contain every piece of information produced during
execution.

Separate domain concepts will later represent:

- Plans
- Agent executions
- Tool calls
- Memory
- Artifacts
- Verification results
- Events
- Metrics
- Execution traces

This separation keeps the architecture modular and maintainable.

---

## 7. Future Extensions

The task lifecycle will later integrate with:

- Planning Engine
- Agent Orchestrator
- Tool System
- Memory System
- Verification Engine
- Failure Recovery Engine
- Human-in-the-Loop System
- Observability
- Evaluation Framework

The lifecycle should remain stable while these systems evolve.
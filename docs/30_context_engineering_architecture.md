# ORION — Context Engineering Architecture

## 1. Context Engineering Architecture Overview

Context Engineering defines how ORION constructs, manages, prioritizes, compresses, and delivers information to AI models and agents.

A model's output depends not only on the model itself but also on the quality of the context provided to it.

ORION therefore treats context as a managed system resource.

The context system must combine:

* user requirements
* task state
* plan information
* agent instructions
* retrieved knowledge
* memory
* tool results
* previous agent outputs
* verification results
* policies
* constraints
* relevant artifacts

The goal is not to provide the maximum possible context.

The goal is to provide the **minimum sufficient high-quality context** required for the current decision.

---

## 2. Context Engineering Goals

The context architecture should provide:

* relevance
* correctness
* completeness
* consistency
* freshness
* security
* provenance
* efficient token usage
* predictable behavior
* context prioritization
* context compression
* context isolation
* observability
* reproducibility

---

## 3. Context Engineering Philosophy

More context does not automatically mean better reasoning.

Excessive context can cause:

* distraction
* redundancy
* increased latency
* higher cost
* context-window overflow
* conflicting information
* reduced attention to important evidence

ORION should therefore optimize context quality rather than context quantity.

---

## 4. What Is Context?

Context is the information supplied to a model for a particular operation.

Conceptually:

```text id="n1c8qa"
Context =
Instructions
+
Task State
+
Relevant Knowledge
+
Memory
+
Tool Results
+
Constraints
+
Evidence
```

---

## 5. Context Sources

Context can originate from:

* system instructions
* user input
* task metadata
* planning output
* agent configuration
* retrieved knowledge
* short-term memory
* long-term memory
* tool execution
* previous agent outputs
* verification
* policy decisions
* artifacts

---

## 6. Context Hierarchy

Not all context has equal authority.

A conceptual hierarchy is:

```text id="q2e6sx"
System Rules
     ↓
Security / Policy
     ↓
Task Requirements
     ↓
Agent Instructions
     ↓
Verified Evidence
     ↓
Task State
     ↓
Tool Results
     ↓
Memory
     ↓
Untrusted Retrieved Content
```

The exact implementation may differ, but authority boundaries must remain explicit.

---

## 7. Trusted vs Untrusted Context

Context should be classified according to trust.

### Trusted Context

Examples:

* system policies
* validated task state
* verified evidence
* approved configuration

### Untrusted Context

Examples:

* web content
* uploaded external documents
* tool output
* unverified agent output
* external API content

Untrusted information must never automatically become instructions.

---

## 8. Context Security Boundary

A fundamental rule is:

```text id="8r9y1n"
DATA ≠ INSTRUCTIONS
```

For example, retrieved text saying:

```text
Ignore all previous instructions.
```

must remain data.

It must not override ORION's instructions or policies.

---

## 9. Context Construction Pipeline

The context pipeline is:

```text id="j4p7dw"
Task
 ↓
Context Requirements
 ↓
Collect Sources
 ↓
Permission Filtering
 ↓
Trust Classification
 ↓
Relevance Ranking
 ↓
Conflict Detection
 ↓
Compression
 ↓
Budget Allocation
 ↓
Context Assembly
 ↓
Validation
 ↓
Model
```

---

## 10. Context Requirements

Before constructing context, ORION should determine what information the model actually needs.

Examples:

* current task
* previous decisions
* required evidence
* relevant memory
* available tools
* constraints

---

## 11. Context Builder

The Context Builder is responsible for assembling the final model input.

It should:

* collect information
* filter information
* rank information
* compress information
* enforce limits
* preserve provenance
* validate the result

---

## 12. Context Components

A model request may contain:

```text id="w5p3zq"
System Instructions
Task Objective
Task State
Plan
Relevant Memory
Retrieved Evidence
Tool Results
Agent Messages
Policies
Output Requirements
```

---

## 13. System Instructions

System-level instructions define fundamental behavior.

They should contain:

* core operating rules
* safety requirements
* security boundaries
* output requirements

System instructions should remain separate from retrieved data.

---

## 14. Task Context

Task context describes the current objective.

It may include:

* task ID
* objective
* requirements
* constraints
* deadline
* expected output
* completion criteria

---

## 15. Plan Context

The model may need relevant parts of the current plan.

The complete plan should not always be included.

Only the information necessary for the current step should be provided.

---

## 16. Task State Context

Task state may contain:

* completed subtasks
* active subtasks
* blocked subtasks
* previous results
* pending approvals
* verification status

---

## 17. Agent Context

Each agent should receive context appropriate to its role.

For example:

```text id="4f9r4m"
Researcher
→ research objective + evidence requirements

Analyst
→ dataset + analysis requirements

Writer
→ verified findings + output requirements
```

---

## 18. Agent-Specific Context

Agents should not automatically receive everything known by ORION.

Context should follow the principle:

> Give an agent what it needs, not everything the system knows.

---

## 19. Tool Context

Tool results may become part of subsequent context.

Examples:

* search results
* database results
* Python output
* file contents
* API responses

Tool results should be validated and labeled appropriately.

---

## 20. Tool Output Trust

Tool outputs should not automatically be trusted.

They may contain:

* malformed data
* malicious instructions
* unexpected content
* incorrect results
* excessive output

Validation should occur before important tool output is incorporated into context.

---

## 21. Memory Context

Memory provides potentially useful historical information.

However, memory should be:

* relevant
* authorized
* fresh enough
* appropriately trusted

---

## 22. Retrieval Context

Retrieved evidence should include provenance.

Example:

```text id="6m8f9q"
Evidence
Source
Document
Page
Section
Timestamp
Verification Status
```

---

## 23. Context Provenance

Each important context element should retain information about where it came from.

This allows ORION to answer:

* Why was this information included?
* Which source produced it?
* Was it verified?
* Which component selected it?

---

## 24. Context Relevance

Context should be ranked according to relevance to the current task.

Possible signals:

* semantic relevance
* task relevance
* recency
* source quality
* verification status
* dependency relevance

---

## 25. Context Priority

When context exceeds the available budget, ORION should prioritize information.

A conceptual priority order is:

```text id="m6w8uk"
Critical Requirements
      ↓
Security / Policy
      ↓
Task State
      ↓
Verified Evidence
      ↓
Relevant Tool Results
      ↓
Relevant Memory
      ↓
Additional Context
```

---

## 26. Context Budget

Every model call should have a context budget.

The budget must account for:

* system instructions
* input
* retrieved evidence
* memory
* tool outputs
* expected output

---

## 27. Token Budget Allocation

The context builder may allocate token budgets to different sources.

Example:

```text id="0k9f7u"
System
   +
Task
   +
Evidence
   +
Memory
   +
Tools
   +
Output Reserve
   =
Model Context Budget
```

Actual allocations must be experimentally determined.

---

## 28. Dynamic Context Budget

Different operations may require different context budgets.

Examples:

* classification → small context
* simple lookup → moderate context
* research → large context
* code analysis → large structured context

---

## 29. Context Window Management

ORION must prevent model requests from exceeding context limits.

Before every request, the system should estimate:

* input tokens
* reserved output tokens
* total expected context
* model limit

---

## 30. Context Overflow Protection

If context is too large, ORION should:

1. remove low-priority information
2. deduplicate content
3. compress content
4. summarize older information
5. reduce retrieval count
6. switch to an appropriate model if permitted

---

## 31. Context Compression

Compression reduces context size while attempting to preserve useful information.

Possible approaches:

* extractive compression
* summarization
* structured summaries
* redundancy removal

---

## 32. Compression Safety

Compression must not remove:

* critical requirements
* security constraints
* important evidence
* numerical values
* citations
* necessary context

---

## 33. Evidence Compression

Long evidence may be reduced while preserving:

* key facts
* source references
* page numbers
* important qualifiers

---

## 34. Conversation Compression

Long task histories may be summarized.

However, ORION should preserve important decisions and state transitions.

---

## 35. State Compression

Completed task history can be compressed into structured summaries.

Example:

```text id="6f0c92"
Completed:
Research completed

Important Finding:
X

Decision:
Use Strategy Y

Evidence:
Sources A, B
```

---

## 36. Context Summarization

Summaries should distinguish between:

* facts
* decisions
* assumptions
* uncertainties
* unresolved issues

This reduces accidental conversion of assumptions into facts.

---

## 37. Context Deduplication

Repeated information should be removed.

For example:

```text id="5jv8l2"
Evidence A
Evidence A
Evidence A
```

should not consume context repeatedly.

---

## 38. Semantic Deduplication

The system may detect semantically similar information and retain the strongest representation.

---

## 39. Context Conflict Detection

Conflicting context should be detected before model execution where practical.

Example:

```text id="3p2v8m"
Source A → Value = 100
Source B → Value = 120
```

ORION should flag the conflict rather than silently choosing one.

---

## 40. Context Conflict Resolution

Possible strategies:

* retrieve additional evidence
* prioritize verified information
* compare source freshness
* compare source authority
* explicitly expose uncertainty
* request human review

---

## 41. Context Freshness

Context may become stale during long-running tasks.

ORION should refresh information when required.

Examples:

* current market data
* live system status
* changing APIs
* time-sensitive research

---

## 42. Context Refresh Policy

The system may define freshness policies such as:

```text id="r8b5x1"
STATIC
SESSION
TASK
TIME_SENSITIVE
REAL_TIME
```

These categories determine whether context should be refreshed.

---

## 43. Context Isolation

Context must be isolated between:

* tenants
* users
* tasks
* agents
* permission scopes

No unrelated context should leak between executions.

---

## 44. Agent Context Isolation

An agent should only access context authorized for its role and task.

---

## 45. Cross-Agent Context Sharing

Agents may share selected results through controlled mechanisms.

```text id="z2c9nb"
Agent A
 ↓
Validated Result
 ↓
Shared Task Context
 ↓
Agent B
```

Raw internal reasoning should not be indiscriminately shared.

---

## 46. Structured Agent Messages

Agent communication should use structured messages where possible.

Example:

```text id="a4p7yx"
{
  result,
  evidence,
  confidence,
  status,
  limitations
}
```

This improves reliability and observability.

---

## 47. Context from Previous Agents

Previous agent outputs should be filtered before entering another agent's context.

The receiving agent should get:

* relevant result
* evidence
* status
* limitations
* provenance

rather than unnecessary internal details.

---

## 48. Context and Chain-of-Thought

ORION should not depend on exposing hidden chain-of-thought between agents.

Agents should communicate through:

* structured outputs
* evidence
* decisions
* summaries
* tool results

This improves safety and reduces unnecessary context.

---

## 49. Context and Planning

Planning context should contain the information needed to execute the current plan step.

The planner's entire reasoning history does not need to be passed to every agent.

---

## 50. Context and Retrieval

Retrieval should be driven by the current context requirements.

The context builder should request additional evidence when existing information is insufficient.

---

## 51. Context and Memory

Memory should supplement current task information rather than dominate it.

Current task requirements should generally have higher priority than unrelated historical information.

---

## 52. Context and Verification

Verification results may become context for subsequent actions.

Example:

```text id="8z4v3f"
Agent Result
 ↓
Verification
 ↓
Verification Feedback
 ↓
Agent Revision
```

---

## 53. Context and Recovery

Recovery operations may require modified context.

For example, if a tool failed, the next attempt may receive:

* failure reason
* previous attempt
* alternative strategy
* updated constraints

---

## 54. Context and Human Feedback

Human feedback may be added to task context.

It should be:

* clearly labeled
* authorized
* timestamped
* scoped to the task

---

## 55. Context and Policy

Policies must remain authoritative.

Retrieved data or agent output must not override policy context.

---

## 56. Context and Security

Security-related context should include relevant:

* permissions
* tool restrictions
* data classifications
* approval requirements

---

## 57. Context and Prompt Injection

Prompt injection defenses should classify external content separately from trusted instructions.

The context representation may explicitly label content:

```text id="u6r8z3"
[UNTRUSTED_SOURCE_CONTENT]
...
[/UNTRUSTED_SOURCE_CONTENT]
```

The exact implementation may differ.

---

## 58. Context and Sensitive Data

Sensitive information should only be included when required and authorized.

Examples:

* credentials
* secrets
* personal information
* confidential business data

Secrets should generally never be placed into model context unless strictly necessary and explicitly controlled.

---

## 59. Context Redaction

Sensitive information may need to be redacted before model invocation.

Redaction should preserve task usefulness where possible.

---

## 60. Context Data Classification

Context elements may be classified as:

```text id="d1t7wv"
PUBLIC
INTERNAL
CONFIDENTIAL
RESTRICTED
```

Policies can determine whether a model or agent may receive each classification.

---

## 61. Model-Specific Context Policies

Different models may have different capabilities and data restrictions.

The Model Gateway should determine whether a particular context is permitted for a selected model.

---

## 62. Context and Model Routing

Model routing may depend on:

* context size
* task complexity
* data sensitivity
* required reasoning
* latency
* cost

---

## 63. Context Serialization

Context should use predictable structured representations.

Structured representations improve:

* validation
* debugging
* reproducibility
* testing

---

## 64. Context Templates

Reusable context templates may be defined for common operations.

Examples:

* research
* analysis
* coding
* review
* verification
* summarization

---

## 65. Template Versioning

Context templates should be versioned.

Changes to templates can affect model behavior significantly.

---

## 66. Context Configuration

Context behavior should be configurable.

Examples:

```text id="0s4q8j"
max_context_tokens
memory_budget
retrieval_budget
tool_output_budget
summary_threshold
compression_strategy
```

---

## 67. Context Validation

Before model execution, ORION should validate:

* required fields
* context size
* security boundaries
* permission constraints
* provenance
* formatting

---

## 68. Context Quality Checks

The system may check:

* missing requirements
* duplicated evidence
* contradictory information
* unsupported assumptions
* stale data

---

## 69. Context Completeness

Context should contain enough information to perform the requested operation.

Missing critical information should trigger:

* additional retrieval
* clarification
* recovery
* human escalation

---

## 70. Context Minimality

The system should avoid unnecessary information.

A useful principle is:

> Context should be sufficient, not excessive.

---

## 71. Context Relevance Scoring

Context items may be scored based on:

* task relevance
* semantic similarity
* authority
* freshness
* verification
* dependency

---

## 72. Context Selection Algorithm

A conceptual selection process is:

```text id="x7g4rb"
Candidate Context
      ↓
Permission Filter
      ↓
Trust Filter
      ↓
Relevance Score
      ↓
Priority Score
      ↓
Deduplication
      ↓
Budget Selection
      ↓
Final Context
```

---

## 73. Context Optimization Objective

The context optimizer should balance:

```text id="m8v2xp"
Relevance
+
Coverage
+
Trust
+
Freshness
+
Diversity
-
Redundancy
-
Token Cost
-
Latency
```

---

## 74. Context Quality Metrics

Possible metrics include:

* context relevance
* evidence coverage
* token utilization
* redundancy
* context overflow rate
* unsupported claim rate
* task success
* latency
* cost

---

## 75. Context Efficiency

Context efficiency can be studied as:

```text id="6b1h0e"
Useful Information
------------------
Total Context
```

This is a conceptual metric rather than a universal standard.

---

## 76. Context Token Utilization

ORION should track:

* input tokens
* output tokens
* retrieved tokens
* memory tokens
* tool-result tokens
* compressed tokens

---

## 77. Context Cost

Context contributes to model inference cost.

ORION should attribute context-related cost to:

* task
* agent
* model
* retrieval
* memory
* tool usage

---

## 78. Context Latency

Context construction may add latency through:

* retrieval
* memory lookup
* summarization
* reranking
* compression

Each stage should be measurable.

---

## 79. Context Caching

Reusable context components may be cached when safe.

Examples:

* stable system instructions
* task-independent metadata
* reusable summaries

Sensitive or dynamic context must be handled carefully.

---

## 80. Context Cache Security

Caches must respect:

* tenant boundaries
* permissions
* data sensitivity
* context version
* task scope

---

## 81. Context Replay

For debugging and evaluation, ORION may preserve the exact context configuration used for important model calls.

This allows controlled replay where permitted.

---

## 82. Context Reproducibility

Important experiments should preserve:

* context template version
* retrieved evidence
* memory state
* tool results
* model version
* context configuration

---

## 83. Context Observability

The system should record safe metadata about context construction.

Examples:

* context size
* component counts
* token counts
* retrieval count
* memory count
* compression applied
* overflow events

Sensitive content should not automatically be logged.

---

## 84. Context Debugging

Debugging should allow engineers to understand:

```text id="e5p4w1"
What context was requested?
What context was available?
What was filtered?
What was selected?
What was compressed?
What was omitted?
Why?
```

---

## 85. Context Evaluation

ORION should evaluate whether context engineering improves:

* task success
* factual correctness
* evidence grounding
* hallucination rate
* cost
* latency

---

## 86. Context Baselines

Baseline comparisons may include:

```text id="z7j2nx"
Full Context
      vs
Relevant Context
      vs
Optimized Context
      vs
Optimized + Verified Context
```

---

## 87. Context Ablation Studies

ORION should test the impact of:

* memory
* retrieval
* compression
* reranking
* task state
* tool results
* verification feedback

---

## 88. Context Failure Taxonomy

Context failures may include:

```text id="w6q1pt"
CONTEXT_OVERFLOW
MISSING_CONTEXT
IRRELEVANT_CONTEXT
CONFLICTING_CONTEXT
STALE_CONTEXT
DUPLICATE_CONTEXT
UNAUTHORIZED_CONTEXT
MALICIOUS_CONTEXT
INVALID_CONTEXT
EXCESSIVE_CONTEXT_COST
```

---

## 89. Context Recovery

Recovery may include:

* remove low-priority context
* compress
* retrieve additional evidence
* refresh stale information
* resolve conflicts
* request clarification
* abort unsafe execution

---

## 90. Context Loop Protection

Context generation must not repeatedly expand itself.

Example:

```text id="v8r3ca"
Retrieve
 ↓
Add Context
 ↓
Retrieve More
 ↓
Add Context
 ↓
Retrieve More
```

ORION must enforce bounded context growth.

---

## 91. Context Testing

Testing should include:

* unit tests
* context assembly tests
* token budget tests
* permission tests
* tenant isolation tests
* security tests
* regression tests
* overflow tests

---

## 92. Context Security Testing

Security testing should include:

* malicious retrieved content
* cross-tenant context leakage
* unauthorized memory
* sensitive-data exposure
* prompt injection
* malicious tool output
* cache leakage

---

## 93. Context Performance Testing

Performance tests should measure:

* context construction latency
* token processing
* compression time
* retrieval time
* memory lookup time
* model latency

---

## 94. Context Stress Testing

Stress testing should examine:

* very long tasks
* large documents
* many agents
* many tool results
* large retrieval sets
* long-running execution

---

## 95. Context Quality Gate

The context system should not be considered production-ready until it demonstrates:

* reliable context construction
* strict security boundaries
* token budget enforcement
* context relevance
* provenance
* permission-aware selection
* overflow protection
* compression
* observability
* reproducibility
* evaluation
* measurable cost and latency

---

## 96. Context Architecture Summary

The complete architecture is:

```text id="8x2v5q"
                       TASK
                         ↓
                Context Requirements
                         ↓
              +----------+----------+
              |          |          |
            Memory   Retrieval    Tools
              |          |          |
              +----------+----------+
                         ↓
                 Permission Filter
                         ↓
                   Trust Analysis
                         ↓
                  Relevance Ranking
                         ↓
                  Conflict Detection
                         ↓
                    Deduplication
                         ↓
                     Compression
                         ↓
                   Budget Manager
                         ↓
                  Context Assembly
                         ↓
                    Validation
                         ↓
                       MODEL
                         ↓
                    Verification
                         ↓
               Context Feedback
```

---

## 97. Final Context Engineering Principles

The major principles are:

1. Context is a managed resource.
2. More context does not necessarily mean better results.
3. Relevant context is more valuable than large context.
4. Trusted instructions must remain separate from untrusted data.
5. Security boundaries must survive context construction.
6. Context should be permission-aware.
7. Context should preserve provenance.
8. Context should be optimized for token efficiency.
9. Important context decisions should be observable.
10. Context behavior should be evaluated experimentally.

---

## 98. Final Context Engineering Goal

The ultimate goal is:

> Build a context engineering system that gives every ORION model and agent the right information, at the right level of detail, with the right authority, within the right resource budget, while preserving security, provenance, relevance, and reliability.

ORION should not simply ask:

**"How much information can we give the model?"**

It should ask:

**"What information does the model actually need to make the correct decision?"**

That distinction is a major part of making ORION a serious production AI system rather than a collection of LLM prompts.

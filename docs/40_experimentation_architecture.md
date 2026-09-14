
# ORION — Experimentation Architecture

## 1. Overview

Experimentation is a core engineering capability of ORION.

ORION contains many architectural decisions that should be validated empirically:

- model selection
- model routing
- planning strategies
- agent architectures
- retrieval strategies
- reranking
- memory strategies
- context engineering
- prompt strategies
- verification
- failure recovery
- human-in-the-loop
- caching
- parallel execution
- tool selection
- cost optimization
- latency optimization

A complex architecture is not automatically a better architecture.

ORION must therefore use controlled experimentation to determine whether a change actually improves the system.

The central principle is:

> **Architectural complexity must be justified by measurable improvement.**

---

## 2. Goals

The experimentation architecture should provide:

1. reproducible experiments
2. controlled comparisons
3. baseline comparison
4. hypothesis-driven development
5. ablation studies
6. A/B testing
7. parameter experiments
8. model comparisons
9. architecture comparisons
10. quality measurement
11. cost measurement
12. latency measurement
13. reliability measurement
14. statistical analysis
15. experiment versioning
16. experiment tracking
17. failure analysis
18. regression detection
19. reproducibility
20. decision support

---

## 3. Core Philosophy

ORION experimentation should follow:

```text
Hypothesis
    ↓
Experiment Design
    ↓
Baseline
    ↓
Controlled Change
    ↓
Execution
    ↓
Measurement
    ↓
Analysis
    ↓
Decision
````

The objective is not to produce impressive-looking charts.

The objective is:

> **Learn which engineering and AI decisions actually improve ORION.**

---

## 4. Experiment Definition

An experiment is a controlled investigation comparing one or more system configurations.

Example:

```text
Experiment:
Does hybrid retrieval improve evidence retrieval quality
compared with semantic-only retrieval?
```

---

## 5. Experiment ID

Every experiment should have a unique identifier.

Example:

```text
EXP-RAG-001
```

---

## 6. Experiment Metadata

An experiment should record:

```text
experiment_id
name
description
owner
hypothesis
status
created_at
started_at
completed_at
```

---

## 7. Experiment Owner

Every experiment should have an owner responsible for:

* experiment design
* execution
* analysis
* documentation
* conclusion

---

## 8. Experiment Status

Possible states:

```text
DRAFT
DESIGNED
RUNNING
COMPLETED
FAILED
CANCELLED
ARCHIVED
```

---

## 9. Hypothesis

Every important experiment should begin with a hypothesis.

Example:

```text
Hypothesis:

Hybrid retrieval will improve evidence recall over
semantic-only retrieval while keeping latency within
an acceptable operational budget.
```

---

## 10. Hypothesis Structure

A useful structure is:

```text
If
    [change]

then
    [expected improvement]

because
    [reason].
```

---

## 11. Null Hypothesis

Where appropriate, experiments should define a null hypothesis.

Example:

```text
There is no meaningful difference between
semantic retrieval and hybrid retrieval.
```

---

## 12. Experiment Objective

The objective should define what decision the experiment supports.

Example:

```text
Decision:
Should hybrid retrieval become the ORION default?
```

---

## 13. Baseline

Every significant experiment should have a baseline.

Example:

```text
Baseline:
semantic retrieval

Variant:
hybrid BM25 + semantic retrieval
```

---

## 14. Baseline Importance

Without a baseline, improvement claims are difficult to interpret.

---

## 15. Baseline Version

The baseline should be versioned.

Example:

```text
baseline_version=rag_v1
```

---

## 16. Variant

A variant is the changed system configuration.

Example:

```text
variant_version=rag_v2
```

---

## 17. Single Variable Principle

Where practical, experiments should change one important factor at a time.

This makes causal interpretation easier.

---

## 18. Multiple Variable Experiments

Multiple variables may be changed when factorial or controlled experimental designs justify it.

---

## 19. Experiment Configuration

Every experiment should capture relevant configuration.

Example:

```text
configuration_version
feature_flag_version
model_version
prompt_version
dataset_version
code_version
```

---

## 20. Dataset Version

Experiments must record the exact dataset version used.

---

## 21. Model Version

Experiments must record model identity and version information where available.

---

## 22. Prompt Version

Prompt changes can materially affect results.

Prompt versions should therefore be recorded.

---

## 23. Code Version

The exact code revision should be recorded.

Example:

```text
git_commit=abc123
```

---

## 24. Feature Flag Version

Relevant feature flags must be captured.

---

## 25. Configuration Snapshot

An experiment should ideally use an immutable configuration snapshot.

---

## 26. Experiment Reproducibility

A successful experiment should be reproducible using the recorded:

```text
code
configuration
model
prompt
dataset
feature flags
random seeds
environment
```

---

## 27. Random Seeds

Where randomness exists, record random seeds when practical.

---

## 28. Determinism

Experiments should maximize determinism where it improves reproducibility.

However, deterministic settings should not be forced when they misrepresent real production behavior.

---

## 29. Experiment Environment

Record:

```text
environment
hardware
software versions
dependency versions
runtime configuration
```

---

## 30. Hardware Information

For performance experiments, record:

```text
CPU
GPU
RAM
storage
network
```

where relevant.

---

## 31. Dependency Versions

Important dependencies should be versioned.

---

## 32. Experiment Dataset

Datasets should be divided appropriately.

Possible sets:

```text
training
validation
development
test
benchmark
```

---

## 33. Data Leakage

Experiments must prevent data leakage.

---

## 34. Evaluation Split

Evaluation data should remain separate from data used for tuning whenever possible.

---

## 35. Golden Dataset

ORION should maintain a curated benchmark dataset for important system behaviors.

---

## 36. Security Dataset

Security experiments should use dedicated adversarial datasets.

Examples:

```text
prompt injection
tool abuse
data exfiltration
malicious documents
permission attacks
```

---

## 37. Failure Dataset

ORION should maintain examples of known failures.

This enables regression testing.

---

## 38. Experiment Categories

Experiments may include:

1. model experiments
2. prompt experiments
3. retrieval experiments
4. planning experiments
5. agent experiments
6. memory experiments
7. verification experiments
8. recovery experiments
9. context experiments
10. tool experiments
11. infrastructure experiments
12. security experiments
13. performance experiments
14. cost experiments

---

## 39. Model Experiments

Examples:

```text
Model A
vs
Model B
```

Measure:

* quality
* latency
* cost
* reliability

---

## 40. Model Routing Experiments

Compare:

```text
single model
vs
static routing
vs
adaptive routing
```

---

## 41. Prompt Experiments

Compare different prompt strategies.

Metrics may include:

```text
task success
instruction adherence
hallucination
token usage
latency
```

---

## 42. Retrieval Experiments

Compare:

```text
semantic
vs
BM25
vs
hybrid
vs
hybrid + reranking
```

---

## 43. Planning Experiments

Compare:

```text
direct execution
vs
planner
vs
planner + verification
vs
planner + replanning
```

---

## 44. Agent Experiments

Compare:

```text
single agent
vs
specialized multi-agent system
```

---

## 45. Agent Count Experiment

Test whether additional agents improve results.

Example:

```text
1 agent
3 agents
5 agents
8 agents
```

Do not assume more agents are better.

---

## 46. Agent Complexity

Measure whether additional coordination creates:

* better quality
* more latency
* more cost
* more failures

---

## 47. Memory Experiments

Compare:

```text
no memory
vs
short-term memory
vs
long-term memory
```

---

## 48. Memory Retrieval Experiments

Test:

```text
top_k
similarity threshold
recency weighting
importance weighting
```

---

## 49. Verification Experiments

Compare:

```text
no verification
vs
single verifier
vs
independent verifier
```

Measure:

* error detection
* false positives
* latency
* cost

---

## 50. Recovery Experiments

Compare:

```text
retry only
vs
retry + alternative tool
vs
retry + replanning
```

---

## 51. Context Experiments

Compare different context construction strategies.

Measure:

```text
task success
token usage
latency
grounding
```

---

## 52. Tool Selection Experiments

Compare:

```text
fixed tool
vs
model-selected tool
vs
policy-aware tool selection
```

---

## 53. Performance Experiments

Measure:

```text
latency
throughput
CPU
memory
network
queue delay
```

---

## 54. Cost Experiments

Measure:

```text
model cost
tool cost
compute cost
storage cost
cost per task
```

---

## 55. Security Experiments

Measure:

```text
attack success
attack detection
policy violations
data leakage
unauthorized actions
```

---

## 56. Experiment Metrics

Metrics should be explicitly defined before execution.

---

## 57. Quality Metrics

Possible metrics:

```text
task success rate
answer correctness
evidence coverage
groundedness
hallucination rate
verification accuracy
```

---

## 58. Planning Metrics

Measure:

```text
plan validity
task completion
replanning frequency
unnecessary steps
dependency errors
```

---

## 59. Tool Metrics

Measure:

```text
tool success rate
tool failure rate
tool selection accuracy
tool latency
tool cost
```

---

## 60. Agent Metrics

Measure:

```text
agent success
agent failure
coordination overhead
communication count
agent latency
agent cost
```

---

## 61. Recovery Metrics

Measure:

```text
failure detection rate
recovery success rate
recovery latency
recovery cost
safe termination rate
```

---

## 62. Verification Metrics

Measure:

```text
verification precision
verification recall
false acceptance
false rejection
verification latency
```

---

## 63. Reliability Metrics

Measure:

```text
success rate
failure rate
timeout rate
retry rate
crash rate
```

---

## 64. Latency Metrics

Record:

```text
p50
p95
p99
```

where sufficient sample size exists.

---

## 65. Throughput Metrics

Measure:

```text
tasks per minute
tasks per hour
tool calls per second
requests per second
```

depending on the experiment.

---

## 66. Cost Metrics

Measure:

```text
cost per request
cost per task
cost per successful task
```

Cost per successful task can be especially useful when quality differs between variants.

---

## 67. Token Metrics

Measure:

```text
input tokens
output tokens
total tokens
tokens per successful task
```

---

## 68. Resource Metrics

Measure:

```text
CPU
memory
GPU
network
storage
```

where relevant.

---

## 69. Sample Size

Experiments should use sufficient samples to support the intended conclusion.

Do not draw strong conclusions from tiny samples.

---

## 70. Statistical Significance

Where appropriate, use statistical tests to determine whether observed differences are likely meaningful.

---

## 71. Practical Significance

Statistical significance alone is not enough.

A tiny improvement may not justify substantial:

* cost
* latency
* complexity
* operational risk

---

## 72. Confidence Intervals

Where appropriate, report confidence intervals.

---

## 73. Variance

AI systems may produce variable outcomes.

Experiments should measure variance rather than relying only on averages.

---

## 74. Mean vs Median

Latency and cost distributions may be skewed.

Use appropriate statistics such as:

```text
mean
median
p95
p99
```

---

## 75. Outliers

Outliers should be investigated rather than automatically discarded.

---

## 76. Failure Analysis

Every major experiment should analyze failures.

Questions:

```text
What failed?
Why did it fail?
Which component caused the failure?
Was the failure expected?
Did the variant introduce new failure modes?
```

---

## 77. Failure Taxonomy

Failures may be classified as:

```text
planning
agent
tool
model
retrieval
memory
verification
recovery
security
infrastructure
data
```

---

## 78. Regression Detection

A feature may improve one metric while degrading another.

Example:

```text
quality ↑
latency ↑↑
cost ↑↑
```

The overall result may therefore be unacceptable.

---

## 79. Multi-Objective Evaluation

ORION should consider multiple objectives:

```text
quality
reliability
latency
cost
security
```

---

## 80. Experiment Scorecard

A scorecard may contain:

```text
Quality
Reliability
Latency
Cost
Security
Complexity
```

---

## 81. Weighted Scores

A weighted score may be used when appropriate.

However, raw metrics should remain visible.

---

## 82. No Hidden Metrics

Important decision metrics should not be hidden behind a single composite score.

---

## 83. Ablation Studies

Ablation studies determine whether individual components contribute value.

Example:

```text
Full ORION
    ↓
remove verification
    ↓
measure change
```

---

## 84. Agent Ablation

Example:

```text
Full:
Planner + Researcher + Reviewer

Ablation:
Planner + Researcher
```

---

## 85. Memory Ablation

Compare:

```text
with memory
vs
without memory
```

---

## 86. Verification Ablation

Compare:

```text
with verification
vs
without verification
```

---

## 87. Recovery Ablation

Compare:

```text
recovery enabled
vs
recovery disabled
```

---

## 88. RAG Ablation

Compare:

```text
RAG
vs
no RAG
```

---

## 89. Context Ablation

Remove individual context sources to measure contribution.

---

## 90. Multi-Agent Ablation

Compare:

```text
single agent
vs
multi-agent
```

---

## 91. Tool Ablation

Determine whether a tool materially improves task success.

---

## 92. Complexity Measurement

Experiments should consider engineering complexity.

Possible indicators:

```text
components
dependencies
execution steps
model calls
tool calls
configuration parameters
```

---

## 93. Complexity vs Benefit

A useful question is:

> Does the measurable benefit justify the added complexity?

---

## 94. Experiment Matrix

ORION may maintain a matrix:

```text
Experiment
Baseline
Variant
Quality
Latency
Cost
Reliability
Decision
```

---

## 95. Example Experiment

```text
Experiment:
EXP-ORION-001

Question:
Does verification improve final task quality?

Baseline:
Planner + Agents

Variant:
Planner + Agents + Verification

Metrics:
Task Success
Unsupported Claims
Latency
Cost
```

---

## 96. Example Decision

A valid decision could be:

```text
Verification improved task correctness,
but increased latency significantly.

Decision:
Keep verification for high-risk tasks only.
```

This is better than blindly enabling verification everywhere.

---

## 97. Experiment Registry

ORION should maintain an experiment registry.

It should store:

```text
experiment_id
hypothesis
configuration
dataset
results
status
decision
```

---

## 98. Experiment Storage

Experiment metadata may be stored in PostgreSQL.

Large results and artifacts may be stored separately.

---

## 99. Experiment Artifacts

Artifacts may include:

```text
metrics
plots
logs
reports
model outputs
evaluation results
failure samples
```

---

## 100. Artifact Versioning

Experiment artifacts should be versioned where reproducibility requires it.

---

## 101. Experiment Reports

Each major experiment should produce a structured report.

---

## 102. Experiment Report Structure

A report should contain:

```text
Objective
Hypothesis
Baseline
Variant
Dataset
Configuration
Metrics
Results
Failure Analysis
Statistical Analysis
Decision
Limitations
Next Steps
```

---

## 103. Experiment Reproduction

Another engineer should be able to understand how the experiment was executed.

---

## 104. Experiment Automation

Repeated experiments should be automated where practical.

---

## 105. Experiment Pipeline

Conceptually:

```text
Experiment Definition
        ↓
Environment Preparation
        ↓
Dataset Loading
        ↓
Configuration Loading
        ↓
Execution
        ↓
Evaluation
        ↓
Metric Calculation
        ↓
Analysis
        ↓
Report
```

---

## 106. Experiment Runner

ORION may provide an experiment runner.

Conceptually:

```python
experiment.run(
    configuration=...,
    dataset=...
)
```

---

## 107. Experiment Isolation

Experiments should not accidentally modify production state.

---

## 108. Production Safety

Experiments involving production systems should have:

* strict isolation
* limited traffic
* controlled permissions
* rollback

---

## 109. Shadow Experiments

Shadow execution may allow testing a new strategy without affecting the production result.

---

## 110. Online Experiments

Online experiments may expose controlled traffic to a variant.

---

## 111. Offline Experiments

Offline benchmarks should be preferred when they can answer the question safely and accurately.

---

## 112. A/B Experiments

A/B testing may compare two variants under controlled conditions.

---

## 113. Traffic Assignment

Traffic assignment should be:

* deterministic where appropriate
* measurable
* reproducible

---

## 114. Variant Contamination

Users should not unintentionally switch variants during an experiment.

---

## 115. Long-Running Tasks

Long-running tasks should preserve their assigned experiment variant.

---

## 116. Experiment Context

Execution records should include:

```text
experiment_id
variant_id
```

---

## 117. Experiment and Feature Flags

Feature flags may control experiment variants.

---

## 118. Experiment and Configuration

Configuration snapshots must identify experiment settings.

---

## 119. Experiment and Model Gateway

Model experiments should use the Model Gateway so provider/model selection remains controlled.

---

## 120. Experiment and Policy

Experiments cannot bypass security policy.

---

## 121. Experiment and HITL

Human approval remains mandatory when required even inside an experiment.

---

## 122. Experiment and Verification

Experimental features should not disable mandatory verification.

---

## 123. Experiment and Recovery

Experimental recovery strategies should remain bounded.

---

## 124. Experiment Security

Experiments must be protected against:

* unauthorized modification
* result tampering
* dataset poisoning
* configuration manipulation
* secret exposure

---

## 125. Result Integrity

Experiment results should be protected from unauthorized modification.

---

## 126. Experiment Audit

Important experiment actions should be audited.

---

## 127. Experiment Permissions

Possible roles:

```text
Experiment Viewer
Experiment Developer
Experiment Operator
Experiment Administrator
```

---

## 128. Dataset Permissions

Sensitive evaluation datasets should have restricted access.

---

## 129. Model Access

Experiments should only use models that the experiment is authorized to access.

---

## 130. Secret Protection

Experiment outputs must not contain credentials.

---

## 131. Prompt Injection Experiments

ORION should maintain dedicated prompt-injection experiments.

Measure:

```text
attack success
attack detection
policy enforcement
data leakage
```

---

## 132. Tool Abuse Experiments

Test whether malicious inputs can cause unauthorized tool use.

---

## 133. Memory Poisoning Experiments

Test whether malicious content can enter and influence long-term memory.

---

## 134. Retrieval Poisoning Experiments

Test whether malicious documents can influence retrieval and final responses.

---

## 135. Data Exfiltration Experiments

Test whether an agent can be induced to expose protected information.

---

## 136. Autonomous Loop Experiments

Test:

```text
excessive retries
repeated replanning
agent cycles
tool loops
```

---

## 137. Resource Limit Experiments

Test whether:

```text
token budgets
time limits
tool limits
cost limits
```

are correctly enforced.

---

## 138. Chaos Experiments

Controlled failures may include:

```text
model unavailable
tool unavailable
database unavailable
queue delay
network failure
worker crash
```

---

## 139. Recovery Measurement

Measure whether ORION:

```text
detects failure
recovers safely
avoids duplicate side effects
produces useful partial results
terminates safely
```

---

## 140. Performance Experiments

Test under:

```text
normal load
high load
burst load
concurrent tasks
long-running tasks
```

---

## 141. Scalability Experiments

Measure how performance changes with:

```text
workers
tasks
agents
tool calls
retrieval volume
```

---

## 142. Cost Scaling

Measure cost growth as task complexity increases.

---

## 143. Latency Breakdown

Break latency into:

```text
queue
planning
model
tool
retrieval
verification
synthesis
```

---

## 144. Bottleneck Analysis

Identify the largest contributors to:

* latency
* cost
* failures

---

## 145. Experiment Observability

Experiments should integrate with ORION observability.

---

## 146. Correlation IDs

Experiment executions should use correlation IDs.

---

## 147. Experiment Tracing

Distributed traces should identify:

```text
experiment
variant
task
agent
tool
model
```

---

## 148. Experiment Logging

Logs should contain experiment metadata but not secrets.

---

## 149. Experiment Metrics

Metrics should be tagged carefully with:

```text
experiment_id
variant_id
environment
```

Avoid excessive metric-cardinality growth.

---

## 150. Experiment Cost Attribution

Costs should be attributed to:

```text
experiment
variant
task
model
tool
```

where practical.

---

## 151. Experiment Comparison

Comparisons should use consistent measurement definitions.

---

## 152. Metric Definition Stability

Changing metric definitions midway through an experiment can invalidate comparisons.

Metric versions should therefore be tracked when necessary.

---

## 153. Evaluator Version

If an LLM judge or automated evaluator is used, record its version.

---

## 154. Evaluation Bias

Automated evaluators may have biases.

Where important, use multiple evaluation approaches.

---

## 155. Human Evaluation

Human evaluation may be used for difficult quality dimensions.

---

## 156. Inter-Rater Agreement

For human evaluation, agreement between evaluators may be measured.

---

## 157. LLM Judge Validation

LLM judges should themselves be evaluated before being trusted for important decisions.

---

## 158. Experiment Failure

An experiment may fail because of:

```text
infrastructure
data
configuration
model
evaluation
implementation
```

Failure should be recorded rather than silently discarded.

---

## 159. Partial Experiment Results

Partial results may be retained but clearly marked incomplete.

---

## 160. Experiment Cancellation

Experiments should support controlled cancellation.

---

## 161. Experiment Timeout

Experiments should have resource and time limits.

---

## 162. Experiment Budget

Experiments should define budgets where appropriate:

```text
maximum runtime
maximum tokens
maximum model calls
maximum cost
```

---

## 163. Experiment Scheduling

Large experiments may be scheduled during appropriate resource windows.

---

## 164. Experiment Priority

Experiments may have priorities:

```text
low
normal
high
critical
```

---

## 165. Experiment Queue

Large experiments should not overwhelm production workloads.

---

## 166. Experiment Resource Isolation

Experiment workloads should have controlled resource limits.

---

## 167. Experiment Reproducibility Package

Important experiments may produce a package containing:

```text
code reference
configuration
dataset reference
model reference
prompt reference
results
report
```

---

## 168. Experiment Naming

Names should clearly communicate purpose.

Example:

```text
retrieval_hybrid_vs_semantic_v1
```

---

## 169. Experiment Tags

Experiments may be tagged:

```text
rag
retrieval
performance
security
model
planning
```

---

## 170. Experiment Search

Researchers should be able to find previous experiments by:

* ID
* tag
* component
* date
* owner
* result

---

## 171. Experiment Knowledge Base

Experiment results may contribute to ORION's engineering knowledge base.

---

## 172. Experiment Reuse

Previous experiments should be reused where relevant instead of repeating identical work.

---

## 173. Negative Results

Negative results should be documented.

Example:

```text
Adding a third reviewer did not improve quality
and increased cost significantly.
```

Negative results are valuable engineering knowledge.

---

## 174. Failed Hypotheses

Failed hypotheses should remain available for future reference.

---

## 175. Experiment Decision Log

Major architecture decisions should reference supporting experiments.

Example:

```text
ADR-022
Supported by:
EXP-RAG-014
```

---

## 176. Experiment to ADR Integration

Experiments should help inform Architecture Decision Records.

---

## 177. Experiment to Evaluation Integration

Experiments should reuse ORION's evaluation infrastructure where possible.

---

## 178. Experiment to Benchmark Integration

Benchmark datasets should be versioned and reusable.

---

## 179. Experiment Regression

Previously successful improvements should be protected against future regressions.

---

## 180. Regression Benchmark

ORION should run important experiments or benchmark subsets during CI/CD.

---

## 181. Experiment Quality Gate

Before accepting an architectural change:

```text
[ ] Hypothesis defined
[ ] Baseline defined
[ ] Variant defined
[ ] Dataset version recorded
[ ] Configuration recorded
[ ] Model recorded
[ ] Prompt recorded
[ ] Metrics defined
[ ] Results measured
[ ] Failure analysis completed
[ ] Cost measured
[ ] Latency measured
[ ] Security considered
[ ] Decision documented
```

---

## 182. Experiment Decision Framework

A change should be considered using:

```text
Quality Improvement
+
Reliability
+
Security
-
Latency Cost
-
Financial Cost
-
Complexity
```

The exact decision framework should depend on the use case.

---

## 183. Complexity Budget

ORION should maintain a practical complexity budget.

Not every improvement deserves another subsystem.

---

## 184. Experiment-Driven Architecture

Architecture decisions should increasingly follow:

```text
Question
    ↓
Experiment
    ↓
Evidence
    ↓
Architecture Decision
```

rather than:

```text
Technology Trend
    ↓
Add Technology
```

---

## 185. Experiment-Driven Development

For uncertain AI features:

```text
Prototype
    ↓
Benchmark
    ↓
Experiment
    ↓
Measure
    ↓
Decide
    ↓
Productionize
```

---

## 186. Avoid Premature Optimization

Do not optimize a component before measuring whether it is actually a bottleneck.

---

## 187. Avoid Technology for Buzzwords

A technology should be introduced only when an experiment or engineering requirement justifies it.

---

## 188. Example Architecture Decision

Suppose ORION considers adding a second verifier.

Experiment:

```text
Baseline:
single verifier

Variant:
dual independent verifier
```

Measure:

```text
error detection
false rejection
latency
cost
```

Possible result:

```text
Quality improvement: small
Latency increase: large
Cost increase: large
```

Decision:

```text
Use dual verification only for high-risk tasks.
```

---

## 189. Example Multi-Agent Decision

Experiment:

```text
single agent
vs
3 specialized agents
vs
7 specialized agents
```

If 3 agents provide the best quality-cost trade-off, ORION should prefer 3.

---

## 190. Example Retrieval Decision

Experiment:

```text
semantic
BM25
hybrid
hybrid + reranking
```

Choose the strategy based on measured:

```text
retrieval quality
grounding
latency
cost
```

---

## 191. Example Model Routing Decision

Experiment:

```text
single expensive model
vs
adaptive model routing
```

Measure:

```text
task success
cost
latency
failure rate
```

---

## 192. Example Memory Decision

Experiment:

```text
no long-term memory
vs
episodic memory
vs
episodic + semantic memory
```

Measure:

```text
task quality
repetition reduction
retrieval accuracy
storage cost
latency
```

---

## 193. Experiment Lifecycle

The complete lifecycle is:

```text
Idea
 ↓
Question
 ↓
Hypothesis
 ↓
Design
 ↓
Baseline
 ↓
Implementation
 ↓
Execution
 ↓
Measurement
 ↓
Analysis
 ↓
Decision
 ↓
Documentation
 ↓
Archive
```

---

## 194. Experiment Governance

Important experiments should have:

* owner
* scope
* risk classification
* approval where required
* resource limits
* result review

---

## 195. Experiment Review

High-impact experiments should be reviewed before architecture changes are accepted.

---

## 196. Experiment Documentation

Experiment reports should remain understandable months later.

---

## 197. Experiment Retention

Important experiments should be retained according to engineering knowledge-retention requirements.

---

## 198. Experiment Archival

Old experiments may be archived while preserving their results and metadata.

---

## 199. Experiment Reproducibility Standard

A high-quality experiment should allow another engineer to answer:

```text
What changed?
Compared with what?
Why was it changed?
What data was used?
What model was used?
What configuration was used?
What happened?
How reliable is the result?
What did we learn?
```

---

## 200. Final Architecture

The conceptual ORION experimentation architecture is:

```text
                     ┌──────────────────────┐
                     │ Experiment Registry  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Hypothesis + Design  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Baseline / Variant   │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Experiment Runner    │
                     └──────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
          Model/AI          Retrieval          Agents
          Systems           /Memory            /Tools
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Evaluation Engine    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Metrics + Analysis   │
                     └──────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
           Quality            Cost             Latency
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Decision + Report    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Architecture / ADR   │
                     └──────────────────────┘
```

---

## 201. Core Principles

ORION experimentation follows these principles:

1. every major experiment begins with a question
2. important experiments should have hypotheses
3. baselines are mandatory for meaningful comparisons
4. experiments must be reproducible
5. configurations must be versioned
6. datasets must be versioned
7. models must be recorded
8. prompts must be recorded
9. feature flags must be recorded
10. metrics must be defined before analysis
11. quality must be measured
12. latency must be measured
13. cost must be measured
14. reliability must be measured
15. security must be considered
16. failures must be analyzed
17. negative results are valuable
18. statistical significance should be considered where appropriate
19. practical significance matters
20. complexity must be justified by measurable value

---

## 202. Final Goal

The goal of ORION's Experimentation Architecture is to turn architectural decisions into measurable engineering decisions.

ORION should not say:

> "This architecture seems better."

It should be able to say:

> "We compared the baseline and the proposed architecture under controlled conditions, measured quality, reliability, latency, cost, and security, analyzed failures, and selected the design that provides the best measured trade-off for the intended workload."

The final principle is:

> **Build hypotheses, establish baselines, run controlled experiments, measure real outcomes, analyze failures, and let evidence—not technology trends or assumptions—drive ORION's architecture.**

```


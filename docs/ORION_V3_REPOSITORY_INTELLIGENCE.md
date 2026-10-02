# ORION V3 — Deep Repository Intelligence

## Overview

ORION V3 provides deep, structural, and semantic comprehension of software repositories. Rather than relying on naive text searches or unbounded file dumps that overwhelm LLM context windows and degrade reasoning fidelity, V3 constructs a deterministic, AST-indexed dependency graph of the workspace. This enables exact symbol definition discovery, automated test-to-source mapping, pre-patch change impact analysis, and tightly bounded context optimization.

---

## 1. Architectural Components

### 1.1 AST Symbol Indexer (`orion.core.repo_intel.indexer.ASTSymbolIndexer`)
* **Standard-Library Grounded**: Utilizes Python's native `ast` module for deterministic parsing without external binary dependencies.
* **Extracted Entities**: Classes, member methods, top-level functions, argument signatures, and import relationships (`import x`, `from x import y`).
* **Fault-Tolerant Parsing**: Broken syntax files are isolated as `<SyntaxError>` symbols without halting repository-wide indexing.

### 1.2 Repository Code Graph (`orion.core.repo_intel.graph.RepoCodeGraph`)
* **Bidirectional Relationship Tracking**:
  * Module-to-module dependencies (`imports`) and dependents (`imported_by`).
  * Symbol-level index mapping identifiers to their declaring file and line numbers.
* **Automated Test Mapping**: Detects and links test files directly to the implementation modules they exercise.

### 1.3 Change Impact Analysis (`orion.core.repo_intel.impact.ChangeImpactAnalyzer`)
* **Blast Radius Traversal**: Identifies all directly and transitively affected modules when a source file or symbol is modified.
* **Impacted Test Discovery**: Computes the minimal set of test suites that must run to validate the change.
* **Regression Risk Scoring**: Quantifies blast radius into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` risk tiers to inform capability approval gating.

### 1.4 Architecture & Framework Detector (`orion.core.repo_intel.detector.ArchitectureDetector`)
* Identifies project configuration manifests (`pyproject.toml`, `setup.py`, `requirements.txt`).
* Detects testing frameworks (`pytest`, `unittest`) and active source directory roots.

### 1.5 Context Optimizer (`orion.core.repo_intel.optimizer.ContextOptimizer`)
* Replaces monolithic repository dumps with bounded, token-efficient neighborhood prompts.
* Includes declared symbols, method signatures, relevant imported types, covering test names, and bounded source previews.

---

## 2. API Endpoints

* `GET /api/v1/repo/index`: Returns complete repository module graph, symbol count, and architectural profile.
* `POST /api/v1/repo/impact`: Calculates direct/transitive blast radius, impacted tests, and regression risk for a target file.
* `POST /api/v1/repo/context`: Produces an optimized, token-bounded context snippet ready for prompt injection.

---

## 3. Quality Verification

* **Unit & Integration Suite**: `tests/unit/repo_intel/test_repo_intelligence.py` covering AST extraction, syntax resilience, code graphs, test mapping, blast radius calculation, architecture detection, context optimization, and REST endpoints.
* **Type Safety & Style**: 100% compliant with `mypy` and `ruff`.

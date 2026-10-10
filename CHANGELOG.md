# Changelog

All notable changes to the ORION platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-10

### Added
- **10-Task SWE Benchmark Suite (`v1`)**: Standardized, reproducible evaluation suite in `src/orion/core/benchmarks/tasks.py` covering 10 distinct failure taxonomy categories (`off_by_one`, `type_error`, `missing_none_check`, `wrong_exception`, `bad_regex`, `concurrency_race`, `resource_leak`, `wrong_operator`, `bad_default_argument`, `floating_point_rounding`).
- **Comprehensive Evaluation Report (`docs/EVALUATION.md`)**: Full empirical evaluation report documenting 30/30 task passes (100.0% Pass@1) across 3 benchmark trials compared to 0.0% unassisted baseline, with 0.773s median duration and 180 evidence items logged.
- **Failure-Injection Recovery Suite (`tests/integration/test_recovery_failure_injection.py`)**: Automated verification of 4 injected failure modes:
  - Broken tool output -> `CHANGE_TOOL` strategy selection.
  - Model repetition loop -> `CHANGE_MODEL` fallback.
  - Test runner crash/timeout -> `RETRY_CURRENT_TASK` recovery.
  - Bad patch regressions -> `ROLLBACK` via `PatchRecoveryManager` preserving repository integrity.
- **Threat Model & Security Negative Test Suite (`docs/THREAT_MODEL.md`, `tests/integration/test_security_threat_model.py`)**: 8 threat vectors with automated negative verification tests:
  - TM-01: Canonical workspace escape containment.
  - TM-02: Symlink and junction traversal boundary enforcement.
  - TM-03: Dynamic high-entropy secret redaction.
  - TM-04: Prompt and instruction injection isolation.
  - TM-05: Runaway execution step budgets and loop detection.
  - TM-06: Single-use cryptographic approval token replay prevention.
  - TM-07: Static URL percent-decoding traversal prevention (`403 FORBIDDEN_PATH`).
  - TM-08: Pre-read payload body caps (10MB 413) and strict JSON MIME enforcement (415).
- **Interactive Timeline Replay**: Step-by-step playback scrubber (`#btnReplayMission`) supporting play, pause, step forward, step backward, variable playback speeds (1x, 2x, 4x), and live stream resumption.
- **Real Headless Chrome CDP E2E Smoke Suite (`tests/e2e/test_smoke_controls.py`)**: DevTools Protocol smoke testing over standard library WebSockets verifying zero console errors and 200 OK network responses across all application views.
- **Complete REST API Table (`src/orion/api/routes.py`, `docs/API.md`)**: 64 total endpoints with strict route table synchronization and zero documentation drift.
- **Distributed Trace Waterfall UI Wiring**: Dynamic `#btnMissionTraceLink` in mission header opening the System Observability waterfall with correlated span telemetry.
- **Negative UI String Hygiene Test (`tests/unit/api/test_ui_contracts.py`)**: Automated tests enforcing zero emojis, zero em-dashes, zero TODOs/FIXMEs, zero placeholder links, and honest default verification states.
- **Continuous Integration Workflow (`.github/workflows/ci.yml`)**: Multi-platform (Ubuntu + Windows) GitHub Actions matrix validating Ruff, Mypy, and Pytest on Python 3.12.
- **Root Security & Architecture Policies (`SECURITY.md`, `ARCHITECTURE.md`)**: Complete specifications of the 20 non-negotiable security invariants and 7-stage deterministic task graph.

### Changed
- **API Server Hardening**: Enforced mandatory token authentication on non-loopback interfaces, payload caps, and CORS defaults.
- **Static Assets Hygiene**: Replaced external raster assets with high-performance procedural `<canvas>` starfields respecting `prefers-reduced-motion` and `document.hidden`.
- **Honest UI Defaults**: Replaced hardcoded static "VERIFIED / PASS" values in verification panels with honest default `PENDING / STANDBY / -- / 0 RECORDS` indicators.

### Fixed
- **Windows Socket Resets**: Safely drained request body sockets before returning 413 / 415 HTTP status codes to prevent `WinError 10053` connection resets on Windows clients.
- **Static Path Normalization**: Added `urllib.parse.unquote` decoding before path resolution to prevent URL-encoded path traversal attacks.

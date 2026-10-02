"""Tests for ORION Product UI contracts, DOM elements, and API bindings."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STATIC_DIR = REPO_ROOT / "src" / "orion" / "ui" / "static"


def test_ui_html_structure_and_identifiers():
    """Verify index.html contains all critical product IDs and semantic structures."""
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    # Command Center & Task Entry
    assert 'id="commandCenterForm"' in index_html
    assert 'id="taskInputPrompt"' in index_html
    assert 'id="workspaceInputPath"' in index_html
    assert 'id="executionModeSelect"' in index_html
    assert 'id="btnSubmitTask"' in index_html

    # Interactive Dual-Key Approval Banner & Modal
    assert 'id="approvalAlertBanner"' in index_html
    assert 'id="btnQuickApprove"' in index_html
    assert 'id="btnQuickDeny"' in index_html
    assert 'id="approvalModalBackdrop"' in index_html
    assert 'id="modalApprovalDiff"' in index_html
    assert 'id="btnModalApprove"' in index_html
    assert 'id="btnModalDeny"' in index_html

    # Stepper Stages & Approval Gate
    stages = [
        "inspect_repository",
        "analyze_failure",
        "formulate_fix",
        "approval_gate",
        "implement_change",
        "run_tests",
        "verify",
        "generate_report",
    ]
    for s in stages:
        assert f'id="step-{s}"' in index_html

    # Phase 6 Recovery Observatory
    assert 'id="tab-recovery"' in index_html
    assert 'id="recFailureCatVal"' in index_html
    assert 'id="recStrategyVal"' in index_html
    assert 'id="recAttemptVal"' in index_html
    assert 'id="budgetBarAttempts"' in index_html
    assert 'id="budgetBarTime"' in index_html
    assert 'id="budgetBarPatch"' in index_html
    assert 'id="budgetBarTests"' in index_html
    assert 'id="rollbackAuditBadge"' in index_html

    # Unified Diff Viewer
    assert 'id="tab-changes"' in index_html
    assert 'id="diffCodeBlock"' in index_html
    assert 'id="modifiedFilesCount"' in index_html
    assert 'id="diffLinesAdded"' in index_html
    assert 'id="diffLinesRemoved"' in index_html

    # Controlled Tests Runner Output
    assert 'id="tab-tests"' in index_html
    assert 'id="testTargetVal"' in index_html
    assert 'id="testExitCodeBadge"' in index_html
    assert 'id="testOutputContent"' in index_html

    # Evidence Ledger Explorer
    assert 'id="tab-evidence"' in index_html
    assert 'id="evidenceFilterGroup"' in index_html
    assert 'id="evidenceFeed"' in index_html

    # Authoritative Verification
    assert 'id="tab-verification"' in index_html
    assert 'id="verifStatusBox"' in index_html


def test_ui_css_visual_system_tokens():
    """Verify app.css implements the Cinematic Obsidian visual design system."""
    app_css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")

    # Obsidian dark mode palette tokens
    assert "--bg-void:" in app_css
    assert "--bg-deep:" in app_css
    assert "--bg-panel:" in app_css

    # Luminous accents
    assert "--accent-cyan:" in app_css
    assert "--accent-emerald:" in app_css
    assert "--accent-amber:" in app_css
    assert "--accent-rose:" in app_css

    # Technical fonts
    assert "'Outfit'" in app_css
    assert "'JetBrains Mono'" in app_css

    # Diff styling
    assert ".diff-line-add" in app_css
    assert ".diff-line-del" in app_css
    assert ".diff-code-block" in app_css

    # Responsive media queries
    assert "@media (max-width:" in app_css


def test_ui_js_api_bindings_and_event_listeners():
    """Verify app.js binds to real backend API endpoints and handles SSE events."""
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    # REST endpoints
    assert "/api/tasks" in app_js
    assert "/api/tasks/${taskId}/events" in app_js or "/api/tasks/" in app_js
    assert "/approve" in app_js
    assert "/changes" in app_js
    assert "/tests" in app_js
    assert "/recovery" in app_js
    assert "/verification" in app_js

    # Real-time SSE event handling
    required_events = [
        "TASK_CREATED",
        "APPROVAL_REQUIRED",
        "PATCH_APPROVED",
        "PATCH_DENIED",
        "PATCH_APPLIED",
        "TEST_COMPLETED",
        "VERIFICATION_COMPLETED",
        "RECOVERY_STARTED",
        "RECOVERY_COMPLETED",
        "TASK_COMPLETED",
        "TASK_TERMINATED",
    ]
    for ev in required_events:
        assert ev in app_js

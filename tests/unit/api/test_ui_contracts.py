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

    # Execution Graph (DAG) & Workforce Observatory
    assert 'id="tab-graph"' in index_html
    assert 'id="dagNodesGrid"' in index_html
    assert 'id="dagNodeDetailPanel"' in index_html
    assert 'id="tab-workforce"' in index_html
    assert 'id="workforceCardsGrid"' in index_html
    assert 'id="btnCancelMission"' in index_html
    assert 'id="btnReplayMission"' in index_html
    assert 'id="missionReplayBar"' in index_html
    assert 'id="missionReplayScrubber"' in index_html
    assert 'id="connectionLostBanner"' in index_html

    # Screen 1: Quick Interventions
    assert 'id="btnQuickPause"' in index_html
    assert 'id="btnQuickResume"' in index_html
    assert 'id="btnQuickSteer"' in index_html
    assert 'id="btnQuickForceFail"' in index_html

    # Screen 4: Repository Intelligence
    assert 'id="tab-repo"' in index_html
    assert 'id="repoImpactTargetFile"' in index_html
    assert 'id="btnAnalyzeImpact"' in index_html
    assert 'id="repoContextTargetFile"' in index_html
    assert 'id="btnAnalyzeContext"' in index_html

    # Screen 8: Human Oversight (HITL)
    assert 'id="tab-hitl"' in index_html
    assert 'id="hitlClarificationsList"' in index_html
    assert 'id="hitlInterveneForm"' in index_html
    assert 'id="hitlFeedbackForm"' in index_html
    assert 'id="hitlHistoryList"' in index_html

    # Screen 9: Policy & Security
    assert 'id="tab-policy"' in index_html
    assert 'id="policyRulesList"' in index_html
    assert 'id="policyDecisionsList"' in index_html
    assert 'id="policySimForm"' in index_html

    # Screen 10: Evaluation Lab
    assert 'id="tab-eval"' in index_html
    assert 'id="evalRunsTable"' in index_html
    assert 'id="btnRunEvaluation"' in index_html
    assert 'id="btnCompareExperiments"' in index_html

    # Screen 11: Observability
    assert 'id="tab-observability"' in index_html
    assert 'id="obsTraceWaterfall"' in index_html
    assert 'id="obsBottlenecksList"' in index_html
    assert 'id="obsRecommendationsList"' in index_html


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

    # Graph DAG and Workforce styles
    assert ".dag-node-card" in app_css
    assert ".agent-roster-card" in app_css
    assert ".btn-rose-subtle" in app_css
    assert ".connection-lost-banner" in app_css

    # V10 Observatory styles
    assert ".repo-tool-card" in app_css
    assert ".hitl-card" in app_css
    assert ".policy-rules-table" in app_css
    assert ".eval-runs-table" in app_css
    assert ".trace-waterfall-container" in app_css
    assert ".waterfall-bar" in app_css

    # Responsive media queries
    assert "@media (max-width:" in app_css


def test_ui_js_api_bindings_and_event_listeners():
    """Verify app.js binds to real backend API endpoints and handles SSE events."""
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    # REST endpoints
    assert "/api/tasks" in app_js
    assert "/api/tasks/${taskId}/events" in app_js or "/api/tasks/" in app_js
    assert "/approve" in app_js
    assert "/cancel" in app_js
    assert "/changes" in app_js
    assert "/tests" in app_js
    assert "/recovery" in app_js
    assert "/verification" in app_js
    assert "/graph" in app_js
    assert "/agents" in app_js

    # V10 Observatories REST endpoints
    assert "/api/v1/repo/impact" in app_js
    assert "/api/v1/repo/context" in app_js
    assert "/api/v1/hitl/intervene" in app_js
    assert "/api/v1/hitl/clarifications" in app_js
    assert "/api/v1/hitl/feedback" in app_js
    assert "/api/v1/policy/rules" in app_js
    assert "/api/v1/policy/evaluate" in app_js
    assert "/api/v1/evaluation/run" in app_js
    assert "/api/v1/evaluation/compare" in app_js
    assert "/api/v1/observability/spans" in app_js
    assert "/api/v1/observability/bottlenecks" in app_js
    assert "/api/v1/observability/optimize" in app_js

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
        "TASK_CANCELLED",
        "TASK_TERMINATED",
    ]
    for ev in required_events:
        assert ev in app_js


def test_interactive_product_experience_contracts():
    """Verify contracts for interactive Demo Center, Architecture Explorer,
    Product Tour, and Presentation Mode.
    """
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    # 1. Landing Screen Actions
    assert 'id="btnEnterOrion"' in index_html
    assert 'id="btnIntroDemo"' in index_html
    assert 'id="btnIntroArch"' in index_html
    assert 'id="btnIntroMission"' in index_html

    # 2. Mission Templates Quick-Launch
    assert 'id="missionTemplatesBar"' in index_html
    assert 'data-task="Fix Calculator Addition Offset"' in index_html
    assert 'data-task="Resolve Validator Syntax AST Error"' in index_html
    assert 'data-task="Repair Cache Expiration Check"' in index_html
    assert 'data-task="Enforce Path Traversal Boundary"' in index_html
    assert 'data-task="Autonomous Self-Healing Recovery"' in index_html

    # 3. Timeline Replay Bar
    assert 'id="timelineReplayBar"' in index_html
    assert 'id="timelineReplayScrubber"' in index_html
    assert 'id="btnReplayPrev"' in index_html
    assert 'id="btnReplayNext"' in index_html
    assert 'id="btnReplayLive"' in index_html
    assert 'id="replayStepCounter"' in index_html

    # 4. Demo Center & Player
    assert 'id="tab-demo"' in index_html
    assert 'id="demoScenariosGrid"' in index_html
    assert 'id="btnDemoPlay"' in index_html
    assert 'id="btnDemoRestart"' in index_html
    assert 'id="btnDemoPrevStage"' in index_html
    assert 'id="btnDemoNextStage"' in index_html
    assert 'id="demoScrubber"' in index_html
    assert 'id="demoSpeedSelect"' in index_html
    assert 'id="demoTimelineTrack"' in index_html
    assert 'id="demoStageViewport"' in index_html
    assert 'id="btnDemoRunReal"' in index_html
    assert "FROZEN DEMO" in index_html or "DEMONSTRATION SCENARIO" in index_html

    # 5. Architecture Explorer Modal
    assert 'id="architectureModal"' in index_html
    assert 'id="archPipelineFlow"' in index_html
    assert 'id="archDetailPanel"' in index_html
    assert 'id="btnOpenArchitecture"' in index_html
    assert 'id="btnArchClose"' in index_html

    # 6. Guided Product Tour
    assert 'id="productTourCard"' in index_html
    assert 'id="tourStepBadge"' in index_html
    assert 'id="tourTitle"' in index_html
    assert 'id="tourDescription"' in index_html
    assert 'id="btnTourPrev"' in index_html
    assert 'id="btnTourNext"' in index_html
    assert 'id="btnTourClose"' in index_html
    assert 'id="btnTourSkip"' in index_html
    assert 'id="btnHelpTour"' in index_html

    # 7. Presentation Mode & Toasts
    assert 'id="btnPresentationMode"' in index_html
    assert 'id="presentationBanner"' in index_html
    assert 'id="toastContainer"' in index_html
    assert ".presentation-mode" in app_css
    assert ".toast-container" in app_css
    assert ".toast-item" in app_css

    # 8. JS Demo Scenarios Ground Truth Integrity
    assert "DEMO_SCENARIOS" in app_js
    assert "SWE-BUG-001" in app_js
    assert "SWE-SYN-001" in app_js
    assert "SWE-REG-001" in app_js
    assert "SWE-SEC-001" in app_js
    assert "SWE-REC-001" in app_js
    assert "SUBSYSTEM_SPECS" in app_js
    assert "TOUR_STEPS" in app_js
    assert "showToast" in app_js


def test_product_console_information_architecture():
    """Verify ORION Product Console information architecture, shell, and pages."""
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    # 1. Stable Application Shell
    assert 'class="orion-shell"' in index_html
    assert 'id="mainNavbar"' in index_html
    assert 'id="topbarBreadcrumb"' in index_html
    assert 'id="appSidebar"' in index_html
    assert 'id="sidebarNav"' in index_html
    assert 'id="appMainViewport"' in index_html

    # 2. Compact Sidebar Navigation Groups & Links
    assert 'id="navOverview"' in index_html
    assert 'id="navMissionActive"' in index_html
    assert 'id="navMissionsAll"' in index_html
    assert 'id="navMissionsHistory"' in index_html
    assert 'id="navExecPipeline"' in index_html
    assert 'id="navExecTestScope"' in index_html
    assert 'id="navExecChanges"' in index_html
    assert 'id="navExecRecovery"' in index_html
    assert 'id="navEvidenceLedger"' in index_html
    assert 'id="navEvidenceVerification"' in index_html
    assert 'id="navSystemWorkforce"' in index_html
    assert 'id="navSystemSecurity"' in index_html

    # 3. Pages
    assert 'id="viewOverview"' in index_html
    assert 'id="viewMissionDetail"' in index_html
    assert 'id="viewMissionsAll"' in index_html
    assert 'id="viewAgents"' in index_html
    assert 'id="viewEvidence"' in index_html
    assert 'id="viewSystem"' in index_html

    # 4. Overview Page Structure
    assert 'id="overviewHeader"' in index_html
    assert 'id="systemStatusRow"' in index_html
    assert 'id="activeMissionCard"' in index_html
    assert 'id="recentMissionsTable"' in index_html
    assert 'id="btnOverviewNewMission"' in index_html

    # 5. Integrated Test Scope Selection
    assert 'id="testSelectionSection"' in index_html
    assert 'id="testSelectionStrategyBadge"' in index_html
    assert 'id="testSelectionModeBadge"' in index_html
    assert 'id="testSelectionReasonVal"' in index_html
    assert 'id="testSelectedTargetsList"' in index_html

    # 6. Evidence Ledger & Workforce Tables
    assert 'id="evidenceTable"' in index_html
    assert 'id="workforceTable"' in index_html

    # 7. Modals
    assert 'id="newMissionModal"' in index_html
    assert 'id="demoToolsModal"' in index_html
    assert 'id="commandPaletteBackdrop"' in index_html

    # 8. CSS & JS Router Tokens
    assert ".app-topbar" in app_css
    assert ".app-sidebar" in app_css
    assert ".view-page" in app_css
    assert "switchView" in app_js
    assert "initProductConsole" in app_js
    assert "openModal" in app_js


def test_premium_website_redesign_contracts():
    """Verify contracts for Landing page, Documentation, Privacy, Terms,
    Favicon, and zero dead buttons.
    """
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    favicon_svg = (STATIC_DIR / "favicon.svg").read_text(encoding="utf-8")

    # 1. Custom SVG Favicon & Metadata
    assert "<svg" in favicon_svg
    assert 'rel="icon"' in index_html
    assert 'href="/static/favicon.svg"' in index_html
    assert "Mission Command Center" in index_html

    # 2. Pages: Landing, Documentation, Privacy, Terms
    assert 'id="viewLanding"' in index_html
    assert 'id="viewDocs"' in index_html
    assert 'id="viewPrivacy"' in index_html
    assert 'id="viewTerms"' in index_html

    # 3. Landing Hero & Call to Actions
    assert 'id="btnLandingLaunchApp"' in index_html
    assert 'id="btnLandingViewArch"' in index_html
    assert 'id="btnLandingOpenDocs"' in index_html
    assert 'id="btnLandingFrameOpen"' in index_html

    # 4. Landing Footer & Documentation Links
    assert 'id="btnFootLaunch"' in index_html
    assert 'id="btnFootArch"' in index_html
    assert 'id="btnFootDemo"' in index_html
    assert 'id="btnFootDocs"' in index_html
    assert 'id="btnFootPrivacy"' in index_html
    assert 'id="btnFootTerms"' in index_html

    # 5. Zero Dead Buttons: No placeholder href="#"
    assert 'href="#"' not in index_html
    assert 'id="btnDocsOpenCockpit"' in index_html
    assert 'id="btnPrivBackCockpit"' in index_html
    assert 'id="btnTermsBackCockpit"' in index_html

    # 6. CSS Design System Classes for Redesign
    assert ".landing-hero-section" in app_css
    assert ".landing-badge-chip" in app_css
    assert ".cockpit-preview-frame" in app_css
    assert ".workflow-cards-grid" in app_css
    assert ".docs-container" in app_css
    assert ".legal-container" in app_css

    # 7. JS Router & Event Wiring for all views
    assert "'landing': 'viewLanding'" in app_js
    assert "'docs': 'viewDocs'" in app_js
    assert "'privacy': 'viewPrivacy'" in app_js
    assert "'terms': 'viewTerms'" in app_js
    assert "'settings': 'viewSettings'" in app_js
    assert "btnLandingLaunchApp" in app_js
    assert "btnFootLaunch" in app_js

    # 8. Cinematic Deep-Space & Orbital Canvas Visuals
    assert (STATIC_DIR / "favicon.svg").exists()
    assert (STATIC_DIR / "favicon.svg").stat().st_size > 100
    assert 'id="heroSpaceCanvas"' in index_html
    assert ".hero-space-canvas" in app_css
    assert "initHeroSpaceVisuals" in app_js
    assert "Autonomous AI Workforce" in index_html
    assert "Engineering missions, under control." in index_html
    assert (
        "Plan, execute, inspect, and verify software engineering work with traceable evidence."
        in index_html
    )

    # 9. Screen I: Settings View & Navigation
    assert 'id="viewSettings"' in index_html
    assert 'id="navSettings"' in index_html
    assert 'id="cfgWorkspaceRoot"' in index_html
    assert 'id="cfgDefaultExecMode"' in index_html
    assert 'id="btnSaveSettings"' in index_html
    assert 'id="btnResetSettings"' in index_html
    assert ".settings-container" in app_css

    # 10. Obsidian & Antique Bronze Design System Palette Tokens
    assert "#080A0C" in app_css  # Obsidian background
    assert "#111519" in app_css  # Graphite surface
    assert "#171C20" in app_css  # Elevated charcoal
    assert "#EEECE5" in app_css  # Warm ivory primary text
    assert "#929BA3" in app_css  # Muted slate secondary text
    assert "#B39A70" in app_css  # Antique bronze accent
    assert "#527E9C" in app_css  # Atmospheric Earth blue
    assert "#293137" in app_css  # Fine border
    assert "#77A88C" in app_css  # Restrained success
    assert "#C5A36A" in app_css  # Restrained warning
    assert "#C77B76" in app_css  # Restrained error

    # 11. Strictly Prohibited Elements Verification (No emojis)
    assert not any(ord(c) > 0x25FF for c in index_html)
    assert not any(ord(c) > 0x25FF for c in app_js)

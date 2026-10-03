/**
 * ORION — Autonomous AI Workforce Command Center Client
 * Communicates with Orion REST & SSE Streaming API at /api/tasks/ and /api/v1/
 */

(function () {
  'use strict';

  let currentTaskId = null;
  let eventSource = null;
  let currentEvidenceFilter = 'all';
  let cachedEvidence = [];
  let pollFallbackInterval = null;
  let activePendingApproval = null;

  const STAGES = [
    'inspect_repository',
    'analyze_failure',
    'formulate_fix',
    'implement_change',
    'run_tests',
    'verify',
    'generate_report',
  ];

  // DOM Elements
  const dom = {
    // Header telemetry
    sseStatusDot: document.getElementById('sseStatusDot'),
    sseStatusText: document.getElementById('sseStatusText'),
    coreStatusDot: document.getElementById('coreStatusDot'),
    coreStatusText: document.getElementById('coreStatusText'),
    engineUptime: document.getElementById('engineUptime'),
    activeMissionsCount: document.getElementById('activeMissionsCount'),
    btnRefresh: document.getElementById('btnRefresh'),
    btnNewMission: document.getElementById('btnNewMission'),
    navMissionPill: document.getElementById('navMissionPill'),
    navMissionId: document.getElementById('navMissionId'),
    navMissionStage: document.getElementById('navMissionStage'),

    // Command Center Entry
    commandCenterForm: document.getElementById('commandCenterForm'),
    taskInputPrompt: document.getElementById('taskInputPrompt'),
    workspaceInputPath: document.getElementById('workspaceInputPath'),
    executionModeSelect: document.getElementById('executionModeSelect'),
    btnSubmitTask: document.getElementById('btnSubmitTask'),

    // Approval Banner
    approvalAlertBanner: document.getElementById('approvalAlertBanner'),
    approvalToolBadge: document.getElementById('approvalToolBadge'),
    approvalRiskBadge: document.getElementById('approvalRiskBadge'),
    approvalRationaleText: document.getElementById('approvalRationaleText'),
    btnInspectApprovalDiff: document.getElementById('btnInspectApprovalDiff'),
    btnQuickApprove: document.getElementById('btnQuickApprove'),
    btnQuickDeny: document.getElementById('btnQuickDeny'),

    // Mission Hero
    missionHeroSection: document.getElementById('missionHeroSection'),
    missionIdBadge: document.getElementById('missionIdBadge'),
    missionStatusBadge: document.getElementById('missionStatusBadge'),
    missionLifecycleBadge: document.getElementById('missionLifecycleBadge'),
    missionWorkspaceBadge: document.getElementById('missionWorkspaceBadge'),
    missionObjective: document.getElementById('missionObjective'),
    btnRunPipeline: document.getElementById('btnRunPipeline'),
    btnAdvanceStage: document.getElementById('btnAdvanceStage'),
    btnCancelMission: document.getElementById('btnCancelMission'),
    connectionLostBanner: document.getElementById('connectionLostBanner'),
    btnReconnectNow: document.getElementById('btnReconnectNow'),
    stepperFill: document.getElementById('stepperFill'),
    stepperNodes: document.getElementById('stepperNodes'),

    // Workforce & Telemetry
    agentSWE: document.getElementById('agentSWE'),
    agentDiagnostics: document.getElementById('agentDiagnostics'),
    agentVerifier: document.getElementById('agentVerifier'),
    agentRecovery: document.getElementById('agentRecovery'),
    badgeAgentSWE: document.getElementById('badgeAgentSWE'),
    badgeAgentDiagnostics: document.getElementById('badgeAgentDiagnostics'),
    badgeAgentVerifier: document.getElementById('badgeAgentVerifier'),
    badgeAgentRecovery: document.getElementById('badgeAgentRecovery'),
    metricTestsPassed: document.getElementById('metricTestsPassed'),
    metricTestsFailed: document.getElementById('metricTestsFailed'),
    metricVerifPassed: document.getElementById('metricVerifPassed'),
    metricRecoveryAttempts: document.getElementById('metricRecoveryAttempts'),
    metricEvidenceCount: document.getElementById('metricEvidenceCount'),
    timelineStream: document.getElementById('timelineStream'),

    // Observatory Tabs
    commandTabBar: document.getElementById('commandTabBar'),
    tabCounterChanges: document.getElementById('tabCounterChanges'),
    tabRecoveryPulse: document.getElementById('tabRecoveryPulse'),
    tabCounterNodes: document.getElementById('tabCounterNodes'),
    tabCounterAgents: document.getElementById('tabCounterAgents'),

    // Execution Graph
    graphNodeCountBadge: document.getElementById('graphNodeCountBadge'),
    graphActiveNodeBadge: document.getElementById('graphActiveNodeBadge'),
    dagNodesGrid: document.getElementById('dagNodesGrid'),
    dagNodeDetailPanel: document.getElementById('dagNodeDetailPanel'),
    dagDetailNodeTitle: document.getElementById('dagDetailNodeTitle'),
    dagDetailMetaGrid: document.getElementById('dagDetailMetaGrid'),

    // Workforce Observatory
    workforceTotalBadge: document.getElementById('workforceTotalBadge'),
    workforceActiveBadge: document.getElementById('workforceActiveBadge'),
    workforceCardsGrid: document.getElementById('workforceCardsGrid'),

    // Tab 1: Overview
    ovTaskId: document.getElementById('ovTaskId'),
    ovExecutionId: document.getElementById('ovExecutionId'),
    ovWorkspaceRoot: document.getElementById('ovWorkspaceRoot'),
    ovLifecycleState: document.getElementById('ovLifecycleState'),
    ovCurrentStage: document.getElementById('ovCurrentStage'),
    ovStagesCompleted: document.getElementById('ovStagesCompleted'),
    ovApprovalStatus: document.getElementById('ovApprovalStatus'),

    // Tab 2: Code Changes
    modifiedFilesCount: document.getElementById('modifiedFilesCount'),
    diffLinesAdded: document.getElementById('diffLinesAdded'),
    diffLinesRemoved: document.getElementById('diffLinesRemoved'),
    diffValidationBadge: document.getElementById('diffValidationBadge'),
    diffApprovalBadge: document.getElementById('diffApprovalBadge'),
    diffApplicationBadge: document.getElementById('diffApplicationBadge'),
    diffFileLabel: document.getElementById('diffFileLabel'),
    diffCodeBlock: document.getElementById('diffCodeBlock'),
    btnCopyDiff: document.getElementById('btnCopyDiff'),
    operationsList: document.getElementById('operationsList'),

    // Tab 3: Controlled Tests
    testTargetVal: document.getElementById('testTargetVal'),
    testExitCodeBadge: document.getElementById('testExitCodeBadge'),
    testOutcomeBadge: document.getElementById('testOutcomeBadge'),
    testDurationBadge: document.getElementById('testDurationBadge'),
    testOutputContent: document.getElementById('testOutputContent'),

    // Tab 4: Recovery Observatory
    recFailureCatVal: document.getElementById('recFailureCatVal'),
    recStrategyVal: document.getElementById('recStrategyVal'),
    recAttemptVal: document.getElementById('recAttemptVal'),
    recLifecycleStateVal: document.getElementById('recLifecycleStateVal'),
    budgetValAttempts: document.getElementById('budgetValAttempts'),
    budgetBarAttempts: document.getElementById('budgetBarAttempts'),
    budgetValTime: document.getElementById('budgetValTime'),
    budgetBarTime: document.getElementById('budgetBarTime'),
    budgetValPatch: document.getElementById('budgetValPatch'),
    budgetBarPatch: document.getElementById('budgetBarPatch'),
    budgetValTests: document.getElementById('budgetValTests'),
    budgetBarTests: document.getElementById('budgetBarTests'),
    rollbackAuditBadge: document.getElementById('rollbackAuditBadge'),
    recoveryEventsList: document.getElementById('recoveryEventsList'),

    // Tab 5: Verification Center
    verifStatusBox: document.getElementById('verifStatusBox'),
    verifIcon: document.getElementById('verifIcon'),
    verifHeading: document.getElementById('verifHeading'),
    verifReason: document.getElementById('verifReason'),
    verifCriteriaList: document.getElementById('verifCriteriaList'),
    critExitCode: document.getElementById('critExitCode'),
    critRequirements: document.getElementById('critRequirements'),
    critEvidenceLedger: document.getElementById('critEvidenceLedger'),

    // Tab 6: Evidence Explorer
    evidenceFilterGroup: document.getElementById('evidenceFilterGroup'),
    evidenceFilteredCount: document.getElementById('evidenceFilteredCount'),
    evidenceFeed: document.getElementById('evidenceFeed'),

    // Tab 7: Report
    reportContainer: document.getElementById('reportContainer'),
    reportEmptyState: document.getElementById('reportEmptyState'),
    reportContent: document.getElementById('reportContent'),
    btnGenReportNow: document.getElementById('btnGenReportNow'),

    // Modals
    approvalModalBackdrop: document.getElementById('approvalModalBackdrop'),
    modalApprovalCloseBtn: document.getElementById('modalApprovalCloseBtn'),
    modalApprovalReqId: document.getElementById('modalApprovalReqId'),
    modalApprovalAction: document.getElementById('modalApprovalAction'),
    modalApprovalFiles: document.getElementById('modalApprovalFiles'),
    modalApprovalRationale: document.getElementById('modalApprovalRationale'),
    modalApprovalDiff: document.getElementById('modalApprovalDiff'),
    inputApproverName: document.getElementById('inputApproverName'),
    inputApprovalReason: document.getElementById('inputApprovalReason'),
    btnModalDeny: document.getElementById('btnModalDeny'),
    btnModalApprove: document.getElementById('btnModalApprove'),
    approvalDecisionForm: document.getElementById('approvalDecisionForm'),

    modalBackdrop: document.getElementById('modalBackdrop'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    btnCancelModal: document.getElementById('btnCancelModal'),
    createMissionForm: document.getElementById('createMissionForm'),

    // Quick Interventions & Overview Metrics
    btnQuickPause: document.getElementById('btnQuickPause'),
    btnQuickResume: document.getElementById('btnQuickResume'),
    btnQuickSteer: document.getElementById('btnQuickSteer'),
    btnQuickForceFail: document.getElementById('btnQuickForceFail'),
    ovBlockerStatus: document.getElementById('ovBlockerStatus'),
    ovRecoveryState: document.getElementById('ovRecoveryState'),
    ovVerificationState: document.getElementById('ovVerificationState'),
    ovEvidenceTier: document.getElementById('ovEvidenceTier'),

    // Repo Intelligence (Screen 4)
    repoIndexStatusBadge: document.getElementById('repoIndexStatusBadge'),
    repoTotalFilesBadge: document.getElementById('repoTotalFilesBadge'),
    repoTotalSymbolsBadge: document.getElementById('repoTotalSymbolsBadge'),
    repoImpactTargetFile: document.getElementById('repoImpactTargetFile'),
    btnAnalyzeImpact: document.getElementById('btnAnalyzeImpact'),
    repoDirectDependentsCount: document.getElementById('repoDirectDependentsCount'),
    repoTransitiveDependentsCount: document.getElementById('repoTransitiveDependentsCount'),
    repoBlastRadiusScore: document.getElementById('repoBlastRadiusScore'),
    repoImpactedPathsList: document.getElementById('repoImpactedPathsList'),
    repoContextTargetFile: document.getElementById('repoContextTargetFile'),
    btnAnalyzeContext: document.getElementById('btnAnalyzeContext'),
    repoContextFilesCount: document.getElementById('repoContextFilesCount'),
    repoContextTokensCount: document.getElementById('repoContextTokensCount'),
    repoContextSnippets: document.getElementById('repoContextSnippets'),

    // Human Oversight / HITL (Screen 8)
    hitlPendingCountBadge: document.getElementById('hitlPendingCountBadge'),
    hitlClarificationsBadge: document.getElementById('hitlClarificationsBadge'),
    hitlClarificationsList: document.getElementById('hitlClarificationsList'),
    hitlInterveneForm: document.getElementById('hitlInterveneForm'),
    hitlInterveneAction: document.getElementById('hitlInterveneAction'),
    hitlInterveneOperator: document.getElementById('hitlInterveneOperator'),
    hitlInterveneReason: document.getElementById('hitlInterveneReason'),
    hitlIntervenePayload: document.getElementById('hitlIntervenePayload'),
    btnSubmitHitlIntervention: document.getElementById('btnSubmitHitlIntervention'),
    hitlFeedbackForm: document.getElementById('hitlFeedbackForm'),
    hitlFeedbackRating: document.getElementById('hitlFeedbackRating'),
    hitlFeedbackCorrections: document.getElementById('hitlFeedbackCorrections'),
    hitlFeedbackComments: document.getElementById('hitlFeedbackComments'),
    btnSubmitFeedback: document.getElementById('btnSubmitFeedback'),
    hitlHistoryList: document.getElementById('hitlHistoryList'),

    // Policy & Security (Screen 9)
    policyRulesCountBadge: document.getElementById('policyRulesCountBadge'),
    policyRulesList: document.getElementById('policyRulesList'),
    policyDecisionsCountBadge: document.getElementById('policyDecisionsCountBadge'),
    policyDecisionsList: document.getElementById('policyDecisionsList'),
    policySimForm: document.getElementById('policySimForm'),
    policySimSubject: document.getElementById('policySimSubject'),
    policySimAction: document.getElementById('policySimAction'),
    policySimResource: document.getElementById('policySimResource'),
    policySimRisk: document.getElementById('policySimRisk'),
    btnSimulatePolicy: document.getElementById('btnSimulatePolicy'),
    policySimResult: document.getElementById('policySimResult'),

    // Evaluation Lab (Screen 10)
    evalSuitesCountBadge: document.getElementById('evalSuitesCountBadge'),
    evalSuiteSelect: document.getElementById('evalSuiteSelect'),
    evalVersionTag: document.getElementById('evalVersionTag'),
    evalRunForm: document.getElementById('evalRunForm'),
    btnRunEvaluation: document.getElementById('btnRunEvaluation'),
    btnRefreshEvalRuns: document.getElementById('btnRefreshEvalRuns'),
    evalRunsList: document.getElementById('evalRunsList'),
    evalCompareBaseSelect: document.getElementById('evalCompareBaseSelect'),
    evalCompareTargetSelect: document.getElementById('evalCompareTargetSelect'),
    btnCompareExperiments: document.getElementById('btnCompareExperiments'),
    evalCompareResults: document.getElementById('evalCompareResults'),

    // Observability (Screen 11)
    obsTotalSpansBadge: document.getElementById('obsTotalSpansBadge'),
    obsP50Val: document.getElementById('obsP50Val'),
    obsP90Val: document.getElementById('obsP90Val'),
    obsP99Val: document.getElementById('obsP99Val'),
    obsPromptTokens: document.getElementById('obsPromptTokens'),
    obsCompletionTokens: document.getElementById('obsCompletionTokens'),
    obsTotalCost: document.getElementById('obsTotalCost'),
    btnRefreshSpans: document.getElementById('btnRefreshSpans'),
    obsTraceWaterfall: document.getElementById('obsTraceWaterfall'),
    obsBottlenecksList: document.getElementById('obsBottlenecksList'),
    obsRecommendationsList: document.getElementById('obsRecommendationsList'),

    // Intro Overlay & Brand
    orionIntroOverlay: document.getElementById('orionIntroOverlay'),
    btnEnterOrion: document.getElementById('btnEnterOrion'),
    brandLogoTrigger: document.getElementById('brandLogoTrigger'),
    introSysState: document.getElementById('introSysState'),
    introEngineState: document.getElementById('introEngineState'),
    introWorkspaceState: document.getElementById('introWorkspaceState'),
    introVerifState: document.getElementById('introVerifState'),

    // Demo Center & Scenarios
    tabBtnDemo: document.getElementById('tabBtnDemo'),
    tabCounterDemo: document.getElementById('tabCounterDemo'),
    demoCurrentScenarioBadge: document.getElementById('demoCurrentScenarioBadge'),
    btnDemoRunReal: document.getElementById('btnDemoRunReal'),
    demoScenariosGrid: document.getElementById('demoScenariosGrid'),
    btnDemoPlay: document.getElementById('btnDemoPlay'),
    demoPlayIcon: document.getElementById('demoPlayIcon'),
    demoPlayText: document.getElementById('demoPlayText'),
    btnDemoRestart: document.getElementById('btnDemoRestart'),
    btnDemoPrevStage: document.getElementById('btnDemoPrevStage'),
    btnDemoNextStage: document.getElementById('btnDemoNextStage'),
    demoActiveStageName: document.getElementById('demoActiveStageName'),
    demoSpeedSelect: document.getElementById('demoSpeedSelect'),
    demoTimelineTrack: document.getElementById('demoTimelineTrack'),
    demoScrubber: document.getElementById('demoScrubber'),
    demoStageViewport: document.getElementById('demoStageViewport'),

    // Mission Templates
    missionTemplatesBar: document.getElementById('missionTemplatesBar'),

    // Historical Replay
    timelineReplayBar: document.getElementById('timelineReplayBar'),
    replayStepCounter: document.getElementById('replayStepCounter'),
    btnReplayPrev: document.getElementById('btnReplayPrev'),
    timelineReplayScrubber: document.getElementById('timelineReplayScrubber'),
    btnReplayNext: document.getElementById('btnReplayNext'),
    btnReplayLive: document.getElementById('btnReplayLive'),

    // Architecture Explorer
    architectureModal: document.getElementById('architectureModal'),
    archModalWindow: document.getElementById('archModalWindow'),
    btnArchClose: document.getElementById('btnArchClose'),
    archPipelineFlow: document.getElementById('archPipelineFlow'),
    archDetailPanel: document.getElementById('archDetailPanel'),
    btnOpenArchitecture: document.getElementById('btnOpenArchitecture'),
    btnIntroArch: document.getElementById('btnIntroArch'),

    // Presentation Mode
    btnPresentationMode: document.getElementById('btnPresentationMode'),
    presentationBanner: document.getElementById('presentationBanner'),
    btnExitPresentation: document.getElementById('btnExitPresentation'),

    // Guided Product Tour
    btnHelpTour: document.getElementById('btnHelpTour'),
    productTourCard: document.getElementById('productTourCard'),
    tourStepBadge: document.getElementById('tourStepBadge'),
    tourTitle: document.getElementById('tourTitle'),
    tourDescription: document.getElementById('tourDescription'),
    btnTourClose: document.getElementById('btnTourClose'),
    btnTourSkip: document.getElementById('btnTourSkip'),
    btnTourPrev: document.getElementById('btnTourPrev'),
    btnTourNext: document.getElementById('btnTourNext'),

    // Landing Actions
    btnIntroDemo: document.getElementById('btnIntroDemo'),
    btnIntroMission: document.getElementById('btnIntroMission'),

    // Toasts
    toastContainer: document.getElementById('toastContainer'),

    // Command Palette
    btnOpenCommandPalette: document.getElementById('btnOpenCommandPalette'),
    commandPaletteBackdrop: document.getElementById('commandPaletteBackdrop'),
    commandPaletteModal: document.getElementById('commandPaletteModal'),
    commandPaletteInput: document.getElementById('commandPaletteInput'),
    commandPaletteList: document.getElementById('commandPaletteList'),
    cpCloseBadge: document.getElementById('cpCloseBadge'),

    // Breadcrumbs & Status Bar
    ideBreadcrumbs: document.getElementById('ideBreadcrumbs'),
    bcSection: document.getElementById('bcSection'),
    bcTarget: document.getElementById('bcTarget'),
    bcMissionTail: document.getElementById('bcMissionTail'),
    sbMissionText: document.getElementById('sbMissionText'),
    sbStageText: document.getElementById('sbStageText'),
    sbWorkspaceText: document.getElementById('sbWorkspaceText'),
    sbVerifText: document.getElementById('sbVerifText'),
    sbPolicyText: document.getElementById('sbPolicyText'),
  };

  const COMMAND_PALETTE_ITEMS = [
    { id: 'tab-overview', title: 'Mission Command Center', category: 'Operations', icon: '⚡' },
    { id: 'tab-demo', title: 'Interactive Demo Center & Player', category: 'Operations', icon: '▶️' },
    { id: 'tab-graph', title: 'Execution Graph (DAG Topology)', category: 'Operations', icon: '☍' },
    { id: 'tab-workforce', title: 'Workforce Roster & Work Units', category: 'Operations', icon: '👥' },
    { id: 'tab-repo', title: 'Repository Intelligence & Impact', category: 'Engineering', icon: '📁' },
    { id: 'tab-changes', title: 'Patch Intelligence & Diff Inspector', category: 'Engineering', icon: '📝' },
    { id: 'tab-tests', title: 'Controlled Tests Execution Runner', category: 'Engineering', icon: '🧪' },
    { id: 'tab-verification', title: 'Authoritative Verification Authority', category: 'Engineering', icon: '🛡️' },
    { id: 'tab-recovery', title: 'Bounded Self-Healing Recovery Forensic', category: 'Engineering', icon: '🔄' },
    { id: 'tab-hitl', title: 'Human Oversight & Interventions (HITL)', category: 'Governance', icon: '👁️' },
    { id: 'tab-policy', title: 'Policy Engine & Guardrail Rules', category: 'Governance', icon: '🔒' },
    { id: 'tab-evidence', title: 'Evidence Provenance Ledger Explorer', category: 'Governance', icon: '📜' },
    { id: 'tab-eval', title: 'Evaluation Lab & Benchmark Matrix', category: 'Intelligence', icon: '📊' },
    { id: 'tab-observability', title: 'Distributed Tracer & Span Waterfall', category: 'Intelligence', icon: '📈' },
    { id: 'tab-report', title: 'Certified SWE Mission Final Report', category: 'Intelligence', icon: '📋' },
    { id: 'action-architecture', title: 'Explore ORION System Architecture', category: 'Intelligence', icon: '🏛️' },
    { id: 'action-presentation', title: 'Toggle Presentation Mode (Key: P)', category: 'View', icon: '📽️' },
    { id: 'action-product-tour', title: 'Launch Guided Product Tour', category: 'Help', icon: '🧭' },
    { id: 'action-new-mission', title: 'Initialize New Autonomous SWE Mission', category: 'Action', icon: '➕' },
    { id: 'action-sync', title: 'Sync System Telemetry & Health', category: 'Action', icon: '🔄' },
  ];

  const TAB_METADATA = {
    'tab-overview': { section: 'OPERATIONS', target: 'MISSION COMMAND' },
    'tab-demo': { section: 'OPERATIONS', target: 'DEMO CENTER' },
    'tab-graph': { section: 'OPERATIONS', target: 'EXECUTION GRAPH' },
    'tab-workforce': { section: 'OPERATIONS', target: 'WORKFORCE' },
    'tab-repo': { section: 'ENGINEERING', target: 'REPOSITORY' },
    'tab-changes': { section: 'ENGINEERING', target: 'PATCH INTELLIGENCE' },
    'tab-tests': { section: 'ENGINEERING', target: 'TESTS RUNNER' },
    'tab-verification': { section: 'ENGINEERING', target: 'VERIFICATION' },
    'tab-recovery': { section: 'ENGINEERING', target: 'RECOVERY' },
    'tab-hitl': { section: 'GOVERNANCE', target: 'HUMAN OVERSIGHT' },
    'tab-policy': { section: 'GOVERNANCE', target: 'POLICY & SECURITY' },
    'tab-evidence': { section: 'GOVERNANCE', target: 'EVIDENCE LEDGER' },
    'tab-eval': { section: 'INTELLIGENCE', target: 'EVALUATION LAB' },
    'tab-observability': { section: 'INTELLIGENCE', target: 'OBSERVABILITY' },
    'tab-report': { section: 'INTELLIGENCE', target: 'CERTIFIED REPORT' },
  };

  let paletteSelectedIndex = 0;
  let filteredPaletteItems = [];

  function initIntroOverlay() {
    if (!dom.orionIntroOverlay) return;
    const dismissed = sessionStorage.getItem('orion_intro_dismissed');
    if (dismissed === 'true' || currentTaskId) {
      dom.orionIntroOverlay.classList.add('dismissed');
    }

    if (dom.btnEnterOrion) {
      dom.btnEnterOrion.addEventListener('click', dismissIntroOverlay);
    }
    if (dom.btnIntroDemo) {
      dom.btnIntroDemo.addEventListener('click', () => {
        dismissIntroOverlay();
        switchTab('tab-demo');
      });
    }
    if (dom.btnIntroArch) {
      dom.btnIntroArch.addEventListener('click', () => {
        dismissIntroOverlay();
        openArchitectureModal();
      });
    }
    if (dom.btnIntroMission) {
      dom.btnIntroMission.addEventListener('click', () => {
        dismissIntroOverlay();
        switchTab('tab-overview');
        if (dom.taskInputPrompt) dom.taskInputPrompt.focus();
      });
    }
    if (dom.brandLogoTrigger) {
      dom.brandLogoTrigger.addEventListener('click', openArchitectureModal);
    }
  }

  function dismissIntroOverlay() {
    if (!dom.orionIntroOverlay) return;
    dom.orionIntroOverlay.classList.add('dismissed');
    sessionStorage.setItem('orion_intro_dismissed', 'true');
  }

  function showIntroOverlay() {
    if (!dom.orionIntroOverlay) return;
    dom.orionIntroOverlay.classList.remove('dismissed');
  }

  function initCommandPalette() {
    if (!dom.commandPaletteBackdrop) return;

    if (dom.btnOpenCommandPalette) {
      dom.btnOpenCommandPalette.addEventListener('click', openCommandPalette);
    }
    if (dom.cpCloseBadge) {
      dom.cpCloseBadge.addEventListener('click', closeCommandPalette);
    }
    dom.commandPaletteBackdrop.addEventListener('click', (e) => {
      if (e.target === dom.commandPaletteBackdrop) closeCommandPalette();
    });

    if (dom.commandPaletteInput) {
      dom.commandPaletteInput.addEventListener('input', (e) => {
        renderCommandPalette(e.target.value.trim());
      });
      dom.commandPaletteInput.addEventListener('keydown', handleCommandPaletteKeydown);
    }

    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (dom.commandPaletteBackdrop.classList.contains('open')) {
          closeCommandPalette();
        } else {
          openCommandPalette();
        }
      } else if (e.key === 'Escape') {
        if (dom.commandPaletteBackdrop && dom.commandPaletteBackdrop.classList.contains('open')) {
          closeCommandPalette();
        } else if (dom.orionIntroOverlay && !dom.orionIntroOverlay.classList.contains('dismissed')) {
          dismissIntroOverlay();
        }
      } else if (e.key === 'Enter') {
        if (dom.orionIntroOverlay && !dom.orionIntroOverlay.classList.contains('dismissed')) {
          dismissIntroOverlay();
        }
      }
    });
  }

  function openCommandPalette() {
    if (!dom.commandPaletteBackdrop) return;
    dom.commandPaletteBackdrop.classList.add('open');
    if (dom.commandPaletteInput) {
      dom.commandPaletteInput.value = '';
      dom.commandPaletteInput.focus();
    }
    paletteSelectedIndex = 0;
    renderCommandPalette('');
  }

  function closeCommandPalette() {
    if (!dom.commandPaletteBackdrop) return;
    dom.commandPaletteBackdrop.classList.remove('open');
  }

  function renderCommandPalette(query) {
    if (!dom.commandPaletteList) return;
    const q = (query || '').toLowerCase();
    filteredPaletteItems = COMMAND_PALETTE_ITEMS.filter(it => (
      it.title.toLowerCase().includes(q) || it.category.toLowerCase().includes(q)
    ));

    if (filteredPaletteItems.length === 0) {
      dom.commandPaletteList.innerHTML = '<div class="empty-state">No matching commands or views found</div>';
      return;
    }

    if (paletteSelectedIndex >= filteredPaletteItems.length) {
      paletteSelectedIndex = 0;
    }

    dom.commandPaletteList.innerHTML = filteredPaletteItems.map((item, idx) => `
      <div class="cp-item ${idx === paletteSelectedIndex ? 'selected' : ''}" data-index="${idx}" data-id="${item.id}">
        <div class="cp-item-left">
          <span class="cp-item-icon">${item.icon}</span>
          <span class="cp-item-title">${escapeHtml(item.title)}</span>
        </div>
        <span class="cp-item-category">${escapeHtml(item.category)}</span>
      </div>
    `).join('');

    dom.commandPaletteList.querySelectorAll('.cp-item').forEach(el => {
      el.addEventListener('click', () => {
        const id = el.dataset.id;
        executePaletteItem(id);
      });
    });
  }

  function handleCommandPaletteKeydown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (filteredPaletteItems.length > 0) {
        paletteSelectedIndex = (paletteSelectedIndex + 1) % filteredPaletteItems.length;
        updatePaletteSelection();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (filteredPaletteItems.length > 0) {
        paletteSelectedIndex = (paletteSelectedIndex - 1 + filteredPaletteItems.length) % filteredPaletteItems.length;
        updatePaletteSelection();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredPaletteItems.length > 0 && filteredPaletteItems[paletteSelectedIndex]) {
        executePaletteItem(filteredPaletteItems[paletteSelectedIndex].id);
      }
    }
  }

  function updatePaletteSelection() {
    dom.commandPaletteList.querySelectorAll('.cp-item').forEach((el, idx) => {
      if (idx === paletteSelectedIndex) {
        el.classList.add('selected');
        el.scrollIntoView({ block: 'nearest' });
      } else {
        el.classList.remove('selected');
      }
    });
  }

  function executePaletteItem(id) {
    closeCommandPalette();
    if (!id) return;
    if (id.startsWith('tab-')) {
      switchTab(id);
    } else if (id === 'action-new-mission') {
      if (dom.modalBackdrop) dom.modalBackdrop.classList.add('open');
    } else if (id === 'action-sync') {
      if (dom.btnRefresh) dom.btnRefresh.click();
    } else if (id === 'action-architecture') {
      openArchitectureModal();
    } else if (id === 'action-presentation') {
      togglePresentationMode();
    } else if (id === 'action-product-tour') {
      startProductTour();
    }
  }

  // -------------------------------------------------------------
  // Toast Notifications Engine
  // -------------------------------------------------------------
  function showToast(title, message, type = 'info', duration = 3500) {
    if (!dom.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    toast.innerHTML = `
      <div class="toast-title">${escapeHtml(title)}</div>
      <div class="toast-message">${escapeHtml(message)}</div>
    `;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  // -------------------------------------------------------------
  // Deterministic Demo Center & Scenarios Engine
  // -------------------------------------------------------------
  const DEMO_SCENARIOS = [
    {
      id: 'SWE-BUG-001',
      title: '1. Repair Failing Test (Calculator Subtraction)',
      badge: 'EASY • ASSERTION',
      prompt: 'Analyze calc.py, repair off-by-one arithmetic subtraction in add(), execute tests/test_calc.py, and verify fix.',
      workspace: 'eval/calc_repo',
      stages: [
        {
          name: 'INSPECT REPOSITORY',
          num: '01',
          agent: 'Diagnostic-Agent',
          objective: 'Inspect workspace topology, index symbols, and discover test suites.',
          details: 'Discovered src/calc.py (2 functions: add, multiply) and tests/test_calc.py (3 tests). AST valid. Pytest collection discovered 3 test items.',
          code: `# Discovered workspace structure:
src/calc.py:
  - def add(a: int, b: int) -> int: return a - b  [SUSPECT: subtraction in add]
  - def multiply(a: int, b: int) -> int: return a * b
tests/test_calc.py:
  - test_add(), test_multiply()`,
          claimed: 'Discovered candidate defect in src/calc.py add() implementation.',
          observed: 'Static AST scan clean; 3 test cases registered in test runner.',
          verified: 'Workspace hash integrity sealed. Containment boundary verified.'
        },
        {
          name: 'ANALYZE FAILURE',
          num: '02',
          agent: 'Diagnostic-Agent',
          objective: 'Reproduce test failure in isolated test runner and classify failure root cause.',
          details: 'Executed tests/test_calc.py. AssertionError in test_add(): assert add(2, 3) == 5 failed (-1 != 5). Failure category: assertion_failure.',
          code: `============================= test session starts =============================
tests/test_calc.py:35: in test_add
    assert add(2, 3) == 5
E   AssertionError: assert -1 == 5
E    +  where -1 = add(2, 3)
========================= 1 failed, 2 passed in 0.04s =========================`,
          claimed: 'Test failure isolated to line 26 of src/calc.py.',
          observed: 'Process exit code 1; standard error matched AssertionError pattern.',
          verified: 'Failure taxonomy classified as assertion_failure; root cause confirmed.'
        },
        {
          name: 'FORMULATE FIX',
          num: '03',
          agent: 'Orion-SWE-Engineer',
          objective: 'Synthesize minimal bounded patch proposal to satisfy assertion criteria without regressions.',
          details: 'Patch Strategy: Replace subtraction operator with addition operator on line 26. Risk Tier: LOW. Blast Radius: 1 file, 1 function.',
          code: `Plan ID: PLAN-CALC-001
Target: src/calc.py
Operation: REPLACE_LINE
Line 26: 'return a - b' -> 'return a + b'
Pre-conditions: Python 3.10+ typing, arithmetic invariant
Post-conditions: add(2, 3) == 5, add(-1, 1) == 0`,
          claimed: 'Formulated bounded patch with zero side-effects to multiply().',
          observed: 'Risk classifier assigned tier LOW; dual-key approval auto-cleared.',
          verified: 'Patch proposal verified against repository AST schema.'
        },
        {
          name: 'IMPLEMENT CHANGE',
          num: '04',
          agent: 'Orion-SWE-Engineer',
          objective: 'Apply synthesized patch to repository workspace with transactional rollback safety.',
          details: 'Applied unified diff to src/calc.py. Checkpoint snapshot saved at checkpoint-calc-001.',
          code: `--- a/src/calc.py
+++ b/src/calc.py
@@ -23,6 +23,6 @@
 def add(a: int, b: int) -> int:
-    return a - b
+    return a + b

 def multiply(a: int, b: int) -> int:
     return a * b`,
          claimed: 'Applied 1 line addition, 1 line deletion in src/calc.py.',
          observed: 'File write succeeded with atomic file lock; AST validation passed.',
          verified: 'Patch application sha256 checksum matched cryptographic ledger.'
        },
        {
          name: 'RUN TESTS',
          num: '05',
          agent: 'Diagnostic-Agent',
          objective: 'Execute full controlled pytest test suite against modified workspace.',
          details: 'Executed pytest tests/test_calc.py in controlled container. 2 passed, 0 failed in 0.03s.',
          code: `============================= test session starts =============================
tests/test_calc.py::test_add PASSED                                      [ 50%]
tests/test_calc.py::test_multiply PASSED                                 [100%]

============================== 2 passed in 0.03s ==============================`,
          claimed: 'All test assertions in tests/test_calc.py satisfied.',
          observed: 'Process exit code 0; duration 0.034s; memory usage 18.2 MB.',
          verified: 'Test runner exit code 0 cryptographically signed.'
        },
        {
          name: 'VERIFY FIX',
          num: '06',
          agent: 'Authoritative-Verifier',
          objective: 'VerificationEngine independently confirms test ground truth and invariant compliance.',
          details: 'Core Verification Principle: EXECUTION != SUCCESS; VERIFIED EXECUTION = SUCCESS. VerificationEngine evaluated raw test outputs and AST consistency.',
          code: `[VERIFICATION CERTIFICATE]
Task ID: SWE-BUG-001
Ground Truth Evaluated: SATISFIED
Verification Engine: CONFIRMED
Exit Code Verified: 0 (MATCH)
Controlled Tests Passed: 2/2 (100.0%)
AST Health: 100% CLEAN
Tamper Proof Seal: SHA256:7f83b165...
Status: AUTHORITATIVE_VERIFIED_SUCCESS`,
          claimed: 'SWE Agent asserted task completion.',
          observed: 'Subprocess exited normally with green tests.',
          verified: 'Authoritative VerificationEngine ground truth independently confirmed.'
        },
        {
          name: 'GENERATE REPORT',
          num: '07',
          agent: 'Authoritative-Verifier',
          objective: 'Synthesize certified, tamper-resistant mission report with complete evidence ledger.',
          details: 'Certified SWE Mission Report generated. Status: SATISFIED. All 7 stages satisfied with authoritative proof.',
          code: `================================================================================
ORION CERTIFIED SWE MISSION REPORT // STAMP: VERIFIED_SUCCESS
================================================================================
Mission: SWE-BUG-001 (Fix Calculator Addition Offset)
Final Outcome: SATISFIED
All 7 Stages Completed: SATISFIED
Controlled Tests Passed: SATISFIED (2/2)
Authoritative VerificationEngine: SATISFIED
Evidence Provenance Ledger: SATISFIED (7 records)
Code Modifications Traceable: SATISFIED (src/calc.py)
Recovery Transparency: SATISFIED (0 recovery attempts needed)
================================================================================`,
          claimed: 'Mission concluded with verified resolution.',
          observed: 'Final status SATISFIED recorded in mission memory.',
          verified: 'Cryptographic mission report certificate sealed.'
        }
      ]
    },
    {
      id: 'SWE-SYN-001',
      title: '2. Syntax AST Failure (Validator Missing Colon)',
      badge: 'EASY • AST SYNTAX',
      prompt: 'Analyze validator.py, resolve missing syntax colon in validate_email regex definition, execute tests/test_validator.py, and verify fix.',
      workspace: 'eval/validator_repo',
      stages: [
        {
          name: 'INSPECT REPOSITORY',
          num: '01',
          agent: 'Diagnostic-Agent',
          objective: 'Inspect workspace files and validate python AST syntax across modules.',
          details: 'Discovered src/validator.py and tests/test_validator.py. Static analyzer flagged syntax exception.',
          code: `Workspace: eval/validator_repo
Files: src/validator.py, tests/test_validator.py
AST Validation: SyntaxError detected in src/validator.py at line 134`,
          claimed: 'Suspected syntax error in src/validator.py.',
          observed: 'AST parse failed at byte offset 28.',
          verified: 'Pre-execution syntax inspection confirmed failure.'
        },
        {
          name: 'ANALYZE FAILURE',
          num: '02',
          agent: 'Diagnostic-Agent',
          objective: 'Diagnose syntax AST error token and trace expected grammar token.',
          details: 'SyntaxError: expected ":" at line 134. "if not email or \'@\' not in email" missing trailing colon.',
          code: `File "src/validator.py", line 134
    if not email or '@' not in email
                                    ^
SyntaxError: expected ':'`,
          claimed: 'Grammar token ":" missing at end of compound if statement.',
          observed: 'Python compiler raised SyntaxError before test execution.',
          verified: 'Failure taxonomy classified as syntax_failure.'
        },
        {
          name: 'FORMULATE FIX',
          num: '03',
          agent: 'Orion-SWE-Engineer',
          objective: 'Synthesize minimal AST-compliant syntax repair.',
          details: 'Append ":" to statement line. Risk: LOW. Code validity guaranteed by parser.',
          code: `Plan ID: PLAN-SYN-001
Target: src/validator.py:134
Action: Append terminal colon
Validation: py_compile and ast.parse`,
          claimed: 'Grammar-compliant repair formulated.',
          observed: 'AST parser simulation verified grammar resolution.',
          verified: 'Repair strategy validated.'
        },
        {
          name: 'IMPLEMENT CHANGE',
          num: '04',
          agent: 'Orion-SWE-Engineer',
          objective: 'Apply syntax fix to src/validator.py.',
          details: 'Patched line 134 to restore valid Python grammar.',
          code: `--- a/src/validator.py
+++ b/src/validator.py
@@ -133,3 +133,3 @@
 def validate_email(email: str) -> bool:
-    if not email or '@' not in email
+    if not email or '@' not in email:
         return False`,
          claimed: 'Applied syntax fix to src/validator.py.',
          observed: 'File updated; ast.parse(src) executed without error.',
          verified: 'AST syntax validity confirmed.'
        },
        {
          name: 'RUN TESTS',
          num: '05',
          agent: 'Diagnostic-Agent',
          objective: 'Run pytest test suite against repaired module.',
          details: 'Ran pytest tests/test_validator.py. 2 passed in 0.04s.',
          code: `tests/test_validator.py::test_email PASSED [100%]
============================== 2 passed in 0.04s ==============================`,
          claimed: 'Email validator tests pass with valid and invalid inputs.',
          observed: 'Exit code 0; 2 tests passed.',
          verified: 'Controlled test execution recorded.'
        },
        {
          name: 'VERIFY FIX',
          num: '06',
          agent: 'Authoritative-Verifier',
          objective: 'Verify AST ground truth and zero regression in verification engine.',
          details: 'VerificationEngine confirmed zero syntax warnings and 100% test pass rate.',
          code: `[VERIFICATION CERTIFICATE]
Task ID: SWE-SYN-001
AST Status: VALID (0 errors)
Controlled Tests: PASSED (2/2)
Authoritative Decision: VERIFIED_SUCCESS`,
          claimed: 'Syntax fix satisfies all criteria.',
          observed: 'Compiler and test runner output 0 errors.',
          verified: 'VerificationEngine confirmed ground truth.'
        },
        {
          name: 'GENERATE REPORT',
          num: '07',
          agent: 'Authoritative-Verifier',
          objective: 'Generate certified SWE report.',
          details: 'Report issued confirming successful syntax repair and verification.',
          code: `ORION CERTIFIED SWE MISSION REPORT // SWE-SYN-001
Outcome: SATISFIED
Stages: 7/7 COMPLETE
Verification Authority: CONFIRMED`,
          claimed: 'Mission complete.',
          observed: 'Report created.',
          verified: 'Signed with immutable seal.'
        }
      ]
    },
    {
      id: 'SWE-REG-001',
      title: '3. Regression Repair (Cache TTL Expiration)',
      badge: 'MEDIUM • REGRESSION',
      prompt: 'Diagnose SimpleCache TTL expiration regression in cache.py, synthesize TTL fix, execute regression test suite, and verify authoritative status.',
      workspace: 'eval/cache_repo',
      stages: [
        {
          name: 'INSPECT REPOSITORY',
          num: '01',
          agent: 'Diagnostic-Agent',
          objective: 'Inspect SimpleCache implementation and regression test fixtures.',
          details: 'Inspected src/cache.py and tests/test_cache.py. SimpleCache uses time-based eviction.',
          code: `src/cache.py: SimpleCache class with set(k, v) and get(k) methods.
tests/test_cache.py: test_cache_retrieval() asserts immediate retrieval succeeds.`,
          claimed: 'Target module src/cache.py inspected.',
          observed: '2 source files cataloged.',
          verified: 'Topology mapped.'
        },
        {
          name: 'ANALYZE FAILURE',
          num: '02',
          agent: 'Diagnostic-Agent',
          objective: 'Diagnose cache eviction regression.',
          details: 'AssertionError: test_cache_retrieval failed: c.get(\'session\') was None, expected \'xyz123\'. set() stored expired timestamp: time.time() - self.ttl - 1.',
          code: `tests/test_cache.py:114: in test_cache_retrieval
    assert c.get('session') == 'xyz123'
E   AssertionError: assert None == 'xyz123'`,
          claimed: 'Items are invalidated immediately on insertion.',
          observed: 'Timestamp offset subtracted TTL rather than recording current time.',
          verified: 'Regression taxonomy: test_regression.'
        },
        {
          name: 'FORMULATE FIX',
          num: '03',
          agent: 'Orion-SWE-Engineer',
          objective: 'Formulate TTL timestamp correction.',
          details: 'Store current timestamp time.time() in set(). Compare against time.time() - ts in get().',
          code: `Plan ID: PLAN-REG-001
Fix: self._store[k] = (v, time.time())
Preserve: TTL eviction semantics when time.time() - ts > self.ttl`,
          claimed: 'Correct timestamp on write restores expected cache retention.',
          observed: 'Formulation verified by analysis engine.',
          verified: 'Plan approved.'
        },
        {
          name: 'IMPLEMENT CHANGE',
          num: '04',
          agent: 'Orion-SWE-Engineer',
          objective: 'Apply patch to cache.py.',
          details: 'Removed premature expiration subtraction in set().',
          code: `--- a/src/cache.py
+++ b/src/cache.py
@@ -97,3 +97,3 @@
     def set(self, k: str, v: str) -> None:
-        self._store[k] = (v, time.time() - self.ttl - 1)
+        self._store[k] = (v, time.time())`,
          claimed: 'Replaced negative timestamp offset with current time.',
          observed: 'File patched cleanly.',
          verified: 'Diff checksum verified.'
        },
        {
          name: 'RUN TESTS',
          num: '05',
          agent: 'Diagnostic-Agent',
          objective: 'Run cache regression test suite.',
          details: 'Executed tests/test_cache.py. Cache item successfully retrieved within TTL window.',
          code: `tests/test_cache.py::test_cache_retrieval PASSED [100%]
============================== 1 passed in 0.05s ==============================`,
          claimed: 'Cache retrieval passes test assertions.',
          observed: 'Exit code 0.',
          verified: 'Regression test execution confirmed.'
        },
        {
          name: 'VERIFY FIX',
          num: '06',
          agent: 'Authoritative-Verifier',
          objective: 'Run authoritative verification against both retrieval and expiration boundaries.',
          details: 'Verified retrieval passes and TTL eviction works as designed after timeout.',
          code: `[VERIFICATION CERTIFICATE]
Task ID: SWE-REG-001
Regression Status: ZERO REGRESSIONS
Boundary Check: PASS
Verification Engine: AUTHORITATIVE_VERIFIED_SUCCESS`,
          claimed: 'No remaining regressions in caching subsystem.',
          observed: 'All boundary checks passed.',
          verified: 'Ground truth confirmed.'
        },
        {
          name: 'GENERATE REPORT',
          num: '07',
          agent: 'Authoritative-Verifier',
          objective: 'Generate certified mission report.',
          details: 'Certified report confirmed regression resolved.',
          code: `ORION CERTIFIED SWE MISSION REPORT // SWE-REG-001
Outcome: SATISFIED
Regression Resolved: YES
Verification Status: VERIFIED_SUCCESS`,
          claimed: 'Mission concluded successfully.',
          observed: 'Report archived.',
          verified: 'Final report verified.'
        }
      ]
    },
    {
      id: 'SWE-SEC-001',
      title: '4. Security Boundary (Path Traversal Guard & Policy)',
      badge: 'HARD • POLICY GATE',
      prompt: 'Audit sanitize_path in storage.py, enforce strict boundary guard against directory traversal attacks, require policy approval, and verify.',
      workspace: 'eval/storage_repo',
      stages: [
        {
          name: 'INSPECT REPOSITORY',
          num: '01',
          agent: 'Diagnostic-Agent',
          objective: 'Audit filesystem storage path sanitation routines.',
          details: 'Inspected src/storage.py. Found sanitize_path resolves relative user paths without strict workspace root boundary checks.',
          code: `src/storage.py:
def sanitize_path(base_dir: str, user_path: str) -> Path:
    # VULNERABLE: allows ../ traversal outside base_dir
    return Path(base_dir) / user_path`,
          claimed: 'Potential path traversal vulnerability in sanitize_path.',
          observed: 'Static audit detected unconstrained path joining.',
          verified: 'Security perimeter mapped.'
        },
        {
          name: 'ANALYZE FAILURE',
          num: '02',
          agent: 'Diagnostic-Agent',
          objective: 'Evaluate security risk tier with PolicyEngine.',
          details: 'PolicyEngine evaluated traversal exploit vector. Action classified as HIGH RISK tier requiring Operator Authorization.',
          code: `[POLICY ENGINE EVALUATION]
Action: FILE_SYSTEM_ACCESS
Resource: ../../etc/passwd
Risk Tier: HIGH
Rule Triggered: POLICY_GUARD_FILESYSTEM_CONTAINMENT
Decision: REQUIRE_OPERATOR_APPROVAL`,
          claimed: 'Unconstrained path traversal violates system containment invariant.',
          observed: 'Policy evaluation returned REQUIRE_APPROVAL.',
          verified: 'Security risk classification confirmed.'
        },
        {
          name: 'FORMULATE FIX',
          num: '03',
          agent: 'Orion-SWE-Engineer',
          objective: 'Formulate canonical path resolution and strict boundary guard.',
          details: 'Resolve absolute path, verify is_relative_to(base_dir). Raise PermissionError on boundary escape.',
          code: `Plan ID: PLAN-SEC-001
Implementation:
resolved = (Path(base_dir) / user_path).resolve()
if not resolved.is_relative_to(Path(base_dir).resolve()):
    raise PermissionError("Directory traversal detected")`,
          claimed: 'Formulated canonical path containment boundary.',
          observed: 'Policy rule satisfied by boundary check.',
          verified: 'Security architecture compliant.'
        },
        {
          name: 'IMPLEMENT CHANGE',
          num: '04',
          agent: 'Orion-SWE-Engineer',
          objective: 'Operator authorizes patch via Dual-Key Approval; apply change.',
          details: 'Operator authorized apply_patch under LeadSecurityOfficer identity. Patch applied.',
          code: `--- a/src/storage.py
+++ b/src/storage.py
@@ -12,4 +12,7 @@
 def sanitize_path(base_dir: str, user_path: str) -> Path:
-    return Path(base_dir) / user_path
+    resolved = (Path(base_dir) / user_path).resolve()
+    if not resolved.is_relative_to(Path(base_dir).resolve()):
+        raise PermissionError("Directory traversal detected")
+    return resolved`,
          claimed: 'Applied boundary guard to sanitize_path.',
          observed: 'Dual-key authorization recorded in security audit log.',
          verified: 'Signed by LeadSecurityOfficer.'
        },
        {
          name: 'RUN TESTS',
          num: '05',
          agent: 'Diagnostic-Agent',
          objective: 'Execute security test suite including traversal attack vectors.',
          details: 'Executed tests/test_storage.py. Traversal attempts correctly raised PermissionError; valid subpaths allowed.',
          code: `tests/test_storage.py::test_normal_path PASSED                     [ 50%]
tests/test_storage.py::test_traversal_blocked PASSED                 [100%]
============================== 2 passed in 0.04s ==============================`,
          claimed: 'Traversal vectors blocked; legitimate paths preserved.',
          observed: 'Exit code 0.',
          verified: 'Security tests passed.'
        },
        {
          name: 'VERIFY FIX',
          num: '06',
          agent: 'Authoritative-Verifier',
          objective: 'Authoritative verification of boundary containment and policy compliance.',
          details: 'VerificationEngine confirmed complete boundary containment and immutable policy audit trail.',
          code: `[VERIFICATION CERTIFICATE]
Task ID: SWE-SEC-001
Containment Invariant: PRESERVED
Policy Status: DUAL_KEY_AUTHORIZED
Authoritative Decision: VERIFIED_SUCCESS`,
          claimed: 'Security boundary enforced.',
          observed: 'Zero escape vectors observed in test suite.',
          verified: 'VerificationEngine confirmed security compliance.'
        },
        {
          name: 'GENERATE REPORT',
          num: '07',
          agent: 'Authoritative-Verifier',
          objective: 'Generate certified mission security report.',
          details: 'Certified report issued with dual-key approval cryptographic stamp.',
          code: `ORION CERTIFIED SWE MISSION REPORT // SWE-SEC-001
Outcome: SATISFIED (SECURITY HARDENED)
Policy Evaluation: AUTHORIZED
Verification: VERIFIED_SUCCESS`,
          claimed: 'Mission completed with verified security boundary.',
          observed: 'Security ledger sealed.',
          verified: 'Immutable report generated.'
        }
      ]
    },
    {
      id: 'SWE-REC-001',
      title: '5. Failure + Bounded Self-Healing Recovery',
      badge: 'MEDIUM • SELF-HEAL',
      prompt: 'Execute self-healing task with bounded retries: parse_config whitespace bug, isolate assertion failure, trigger recovery retry, and verify.',
      workspace: 'eval/parser_repo',
      stages: [
        {
          name: 'INSPECT REPOSITORY',
          num: '01',
          agent: 'Diagnostic-Agent',
          objective: 'Inspect parse_config implementation in src/parser.py.',
          details: 'Discovered src/parser.py and tests/test_parser.py. Config parser splits on "=" delimiter.',
          code: `src/parser.py:
def parse_config(raw: str) -> dict[str, str]:
    # Initial implementation does not strip whitespace around key/value
    result = {}
    for line in raw.strip().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            result[k] = v
    return result`,
          claimed: 'Cataloged parse_config implementation.',
          observed: 'Parser and test files discovered.',
          verified: 'Repository indexed.'
        },
        {
          name: 'ANALYZE FAILURE',
          num: '02',
          agent: 'Recovery-Coordinator',
          objective: 'First execution attempt failed: analyze failure and trigger Bounded Self-Healing Recovery.',
          details: 'Attempt 1 failed: AssertionError: {\'host \': \' 127.0.0.1\'} != {\'host\': \'127.0.0.1\'}. RecoveryEngine engaged: classified as assertion_failure, budget 2/3 attempts remaining.',
          code: `[RECOVERY FORENSIC // ATTEMPT 1 FAILED]
Failure Type: assertion_failure
Error: AssertionError in test_parse_clean
Reason: Unstripped whitespace in keys/values
Recovery Decision: RETRY_WITH_REPLAN
Allocated Budget: Attempt 2 of 3 | Time remaining: 48.2s`,
          claimed: 'Initial patch failed test assertion.',
          observed: 'Test runner exited with code 1.',
          verified: 'RecoveryCoordinator engaged with transparent audit.'
        },
        {
          name: 'FORMULATE FIX',
          num: '03',
          agent: 'Orion-SWE-Engineer',
          objective: 'Synthesize revised repair plan incorporating whitespace stripping.',
          details: 'Revised formulation: strip whitespace from both key and value: result[k.strip()] = v.strip().',
          code: `Plan ID: PLAN-REC-002 (Revision 2)
Strategy: Whitespace normalization on split components
Target: src/parser.py:62
Operation: result[k.strip()] = v.strip()`,
          claimed: 'Revised plan addresses whitespace normalization.',
          observed: 'Diagnostic agent verified logic.',
          verified: 'Revision 2 approved by coordinator.'
        },
        {
          name: 'IMPLEMENT CHANGE',
          num: '04',
          agent: 'Orion-SWE-Engineer',
          objective: 'Apply revised self-healing patch to workspace.',
          details: 'Applied revised patch. Rollback checkpoint from Attempt 1 preserved for forensic audit.',
          code: `--- a/src/parser.py
+++ b/src/parser.py
@@ -60,4 +60,4 @@
         if '=' in line:
             k, v = line.split('=', 1)
-            result[k] = v
+            result[k.strip()] = v.strip()
     return result`,
          claimed: 'Applied whitespace stripping patch.',
          observed: 'File patched without syntax errors.',
          verified: 'Patch hash verified.'
        },
        {
          name: 'RUN TESTS',
          num: '05',
          agent: 'Diagnostic-Agent',
          objective: 'Re-run test suite to evaluate self-healing attempt.',
          details: 'Executed tests/test_parser.py on Attempt 2. Test passed with clean key/value mappings.',
          code: `tests/test_parser.py::test_parse_clean PASSED                         [100%]
============================== 1 passed in 0.04s ==============================`,
          claimed: 'Test assertions pass after recovery iteration.',
          observed: 'Exit code 0 on Attempt 2.',
          verified: 'Test pass recorded.'
        },
        {
          name: 'VERIFY FIX',
          num: '06',
          agent: 'Authoritative-Verifier',
          objective: 'Authoritative verification of self-healing resolution and budget audit.',
          details: 'VerificationEngine confirmed resolution within allocated budget: 2 attempts used (budget 3), 1.8s execution time (budget 60s).',
          code: `[VERIFICATION CERTIFICATE // SELF-HEALED]
Task ID: SWE-REC-001
Initial Attempt: FAILED (assertion_failure)
Recovery Status: RECOVERED_AND_VERIFIED
Attempts Used: 2 / 3 (WITHIN BUDGET)
Verification Engine: AUTHORITATIVE_VERIFIED_SUCCESS`,
          claimed: 'Self-healing recovery succeeded within budget.',
          observed: 'All test assertions passed on attempt 2.',
          verified: 'Recovery audit trail sealed.'
        },
        {
          name: 'GENERATE REPORT',
          num: '07',
          agent: 'Authoritative-Verifier',
          objective: 'Generate final mission report preserving recovery transparency.',
          details: 'Report issued documenting the initial failure, recovery classification, retry action, and final verified success.',
          code: `ORION CERTIFIED SWE MISSION REPORT // SWE-REC-001
Outcome: SATISFIED (RECOVERED)
Initial Failure Recorded: YES (TRANSPARENT)
Recovery Iterations: 1 retry
Verification: VERIFIED_SUCCESS`,
          claimed: 'Mission concluded with full transparency.',
          observed: 'Failure and recovery preserved in ledger.',
          verified: 'Final certified report issued.'
        }
      ]
    }
  ];

  let demoState = {
    scenarioIdx: 0,
    stageIdx: 0,
    isPlaying: false,
    speed: 1,
    timer: null,
  };

  function initDemoCenter() {
    if (!dom.demoScenariosGrid) return;
    dom.demoScenariosGrid.querySelectorAll('.demo-scenario-card').forEach(card => {
      card.addEventListener('click', () => {
        const idx = parseInt(card.dataset.scenario, 10);
        selectDemoScenario(idx);
      });
    });

    if (dom.demoTimelineTrack) {
      dom.demoTimelineTrack.querySelectorAll('.demo-track-step').forEach(step => {
        step.addEventListener('click', () => {
          const stage = parseInt(step.dataset.stage, 10);
          renderDemoStage(stage);
        });
      });
    }

    renderDemoScenario(0);
  }

  function selectDemoScenario(idx) {
    if (idx < 0 || idx >= DEMO_SCENARIOS.length) return;
    demoState.scenarioIdx = idx;
    demoState.stageIdx = 0;
    stopDemoTimer();

    if (dom.demoScenariosGrid) {
      dom.demoScenariosGrid.querySelectorAll('.demo-scenario-card').forEach((c, i) => {
        if (i === idx) c.classList.add('active');
        else c.classList.remove('active');
      });
    }

    renderDemoScenario(idx);
    showToast('Demo Scenario Loaded', `${DEMO_SCENARIOS[idx].id}: ${DEMO_SCENARIOS[idx].title}`, 'info');
  }

  function renderDemoScenario(idx) {
    const sc = DEMO_SCENARIOS[idx];
    if (!sc) return;
    if (dom.demoCurrentScenarioBadge) {
      dom.demoCurrentScenarioBadge.textContent = `SCENARIO: ${sc.id}`;
    }
    renderDemoStage(demoState.stageIdx || 0);
  }

  function renderDemoStage(stageIdx) {
    const sc = DEMO_SCENARIOS[demoState.scenarioIdx];
    if (!sc) return;
    demoState.stageIdx = Math.max(0, Math.min(6, stageIdx));
    if (dom.demoScrubber) dom.demoScrubber.value = demoState.stageIdx;

    const st = sc.stages[demoState.stageIdx];
    if (dom.demoActiveStageName) {
      dom.demoActiveStageName.textContent = `STAGE ${demoState.stageIdx + 1}/7: ${st.name}`;
    }

    if (dom.demoTimelineTrack) {
      dom.demoTimelineTrack.querySelectorAll('.demo-track-step').forEach(el => {
        const s = parseInt(el.dataset.stage, 10);
        el.classList.remove('active', 'completed');
        if (s === demoState.stageIdx) el.classList.add('active');
        else if (s < demoState.stageIdx) el.classList.add('completed');
      });
    }

    if (!dom.demoStageViewport) return;

    dom.demoStageViewport.innerHTML = `
      <div class="stage-evidence-card card">
        <div class="stage-card-header">
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="badge badge-cyan">STAGE ${st.num} // ${escapeHtml(st.name)}</span>
            <span class="badge badge-outline">SPECIALIST: ${escapeHtml(st.agent)}</span>
          </div>
          <span class="badge badge-amber frozen-demo-badge">FROZEN DEMONSTRATION DATA</span>
        </div>

        <div class="stage-objective-box">
          <strong class="text-cyan">Objective:</strong> ${escapeHtml(st.objective)}
          <div style="margin-top:4px; color:var(--text-main); font-size:12px;">${escapeHtml(st.details)}</div>
        </div>

        <div class="stage-code-container">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-family:var(--font-mono); font-size:10.5px; color:var(--text-dim); font-weight:700;">
              ${demoState.stageIdx === 3 ? 'SYNTHESIZED UNIFIED PATCH DIFF' : (demoState.stageIdx === 4 ? 'CONTROLLED TEST RUNNER LOG' : 'ENGINEERING ARTIFACT & TELEMETRY')}
            </span>
            <span class="code-val" style="font-size:10.5px;">Workspace: ${escapeHtml(sc.workspace)}</span>
          </div>
          <pre class="diff-pre-modal" style="max-height:220px; overflow:auto;"><code>${escapeHtml(st.code)}</code></pre>
        </div>

        <div class="stage-proof-grid">
          <div class="proof-column">
            <span class="proof-col-label text-purple">1. CLAIMED HYPOTHESIS</span>
            <span style="font-size:11.5px; color:var(--text-secondary);">${escapeHtml(st.claimed)}</span>
          </div>
          <div class="proof-column">
            <span class="proof-col-label text-cyan">2. OBSERVED EXECUTION</span>
            <span style="font-size:11.5px; color:var(--text-secondary);">${escapeHtml(st.observed)}</span>
          </div>
          <div class="proof-column" style="border-color: rgba(16, 185, 129, 0.4);">
            <span class="proof-col-label text-emerald">3. VERIFIED GROUND TRUTH</span>
            <span style="font-size:11.5px; color:var(--text-main); font-weight:500;">${escapeHtml(st.verified)}</span>
          </div>
        </div>
      </div>
    `;
  }

  function stepDemoNext() {
    if (demoState.stageIdx < 6) {
      renderDemoStage(demoState.stageIdx + 1);
    } else {
      stopDemoTimer();
      showToast('Demo Playback Finished', 'Reached Stage 7 (Certified Report). Click Restart to replay or Run as Real Mission.', 'info');
    }
  }

  function stepDemoPrev() {
    if (demoState.stageIdx > 0) {
      renderDemoStage(demoState.stageIdx - 1);
    }
  }

  function toggleDemoPlay() {
    if (demoState.isPlaying) {
      stopDemoTimer();
    } else {
      if (demoState.stageIdx >= 6) {
        demoState.stageIdx = 0;
        renderDemoStage(0);
      }
      startDemoTimer();
    }
  }

  function startDemoTimer() {
    demoState.isPlaying = true;
    if (dom.demoPlayText) dom.demoPlayText.textContent = 'Pause';
    if (dom.demoPlayIcon) {
      dom.demoPlayIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
    }
    const intervalMs = Math.round(2400 / (demoState.speed || 1));
    demoState.timer = setInterval(() => {
      stepDemoNext();
    }, intervalMs);
  }

  function stopDemoTimer() {
    demoState.isPlaying = false;
    if (demoState.timer) {
      clearInterval(demoState.timer);
      demoState.timer = null;
    }
    if (dom.demoPlayText) dom.demoPlayText.textContent = 'Play Demo';
    if (dom.demoPlayIcon) {
      dom.demoPlayIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
    }
  }

  function restartDemo() {
    stopDemoTimer();
    renderDemoStage(0);
    showToast('Demo Reset', 'Reset scenario to Stage 1 (Inspect Repository).', 'info');
  }

  function handleDemoRunAsRealMission() {
    const sc = DEMO_SCENARIOS[demoState.scenarioIdx];
    if (!sc) return;
    if (dom.taskInputPrompt) dom.taskInputPrompt.value = sc.prompt;
    if (dom.workspaceInputPath) dom.workspaceInputPath.value = 'C:/Users/LIKITH/ORION';
    if (dom.executionModeSelect) dom.executionModeSelect.value = 'controlled';
    switchTab('tab-overview');
    showToast('Demo Transition Loaded', `Loaded "${sc.id}: ${sc.title}" into Command Center. Click "Launch Mission" to execute live with backend.`, 'success', 5000);
    if (dom.taskInputPrompt) {
      dom.taskInputPrompt.scrollIntoView({ behavior: 'smooth', block: 'center' });
      dom.taskInputPrompt.focus();
    }
  }

  // -------------------------------------------------------------
  // Architecture Explorer Subsystem Engine
  // -------------------------------------------------------------
  const SUBSYSTEM_SPECS = {
    user_task: {
      name: 'User Task & Directive Intake',
      badge: 'DIRECTIVE INTAKE',
      desc: 'The initial ingestion boundary that receives natural-language engineering directives, workspace paths, and execution safety modes from operators or automated triggers.',
      why: 'Prevents arbitrary or uncontained execution by establishing explicit workspace boundaries and security modes before any agent operations occur.',
      api: 'POST /api/tasks, GET /api/tasks',
      status: 'PRODUCTION READY'
    },
    planning: {
      name: 'MissionPlanner & Cognitive Decomposition',
      badge: 'MISSION PLANNER',
      desc: 'Decomposes complex engineering objectives into a structured 7-stage software engineering lifecycle, calculating resource budgets and candidate tool permissions.',
      why: 'Guarantees execution predictability and prevents unbounded recursion by enforcing finite resource budgets and explicit stage prerequisites.',
      api: 'POST /api/tasks (auto-planned), GET /api/tasks/{id}/graph',
      status: 'DETERMINISTIC'
    },
    dag: {
      name: 'Directed Acyclic Graph (DAG) Execution Topology',
      badge: '7-STAGE TOPOLOGY',
      desc: 'Enforces strictly monotonic state progression through 7 discrete engineering stages: Inspect -> Analyze -> Formulate -> Implement -> Test -> Verify -> Report.',
      why: 'Prevents circular dependencies, skips, or premature completion claims. Nodes cannot transition to completed without ground-truth evidence.',
      api: 'GET /api/tasks/{id}/graph',
      status: 'AUTHORITATIVE'
    },
    workforce: {
      name: 'Specialist Workforce Roster',
      badge: 'INDEPENDENT AGENTS',
      desc: 'A coordinated roster of specialized autonomous agents: Orion-SWE-Engineer (code modifications), Diagnostic-Agent (root cause isolation), Authoritative-Verifier (ground truth evaluation), and Recovery-Coordinator (bounded healing).',
      why: 'Separation of duties prevents conflicting incentives (the engineer who writes the patch cannot verify their own fix without independent confirmation).',
      api: 'GET /api/tasks/{id}/agents',
      status: 'ACTIVE ROSTER'
    },
    sync: {
      name: 'Real-Time State Synchronization',
      badge: 'SSE EVENT BUS',
      desc: 'Server-Sent Events (SSE) stream broadcasting real-time lifecycle transitions, tool executions, approval gates, and telemetry spans directly to the workstation UI.',
      why: 'Maintains live operator visibility into agent cognitive steps without requiring high-latency polling.',
      api: 'GET /api/tasks/{id}/events',
      status: 'CONNECTED'
    },
    verification: {
      name: 'Authoritative VerificationEngine',
      badge: 'GROUND TRUTH ENGINE',
      desc: 'The central validation authority. Evaluates raw subprocess test outputs, exit codes, AST structural integrity, and invariant constraints. Reenforces: EXECUTION != SUCCESS; VERIFIED EXECUTION = SUCCESS.',
      why: 'A running process or synthesized patch is not proof of resolution. Ground-truth verification eliminates hallucinations and unverified claims.',
      api: 'GET /api/tasks/{id}/verification',
      status: 'AUTHORITATIVE'
    },
    recovery: {
      name: 'Bounded Self-Healing RecoveryCoordinator',
      badge: 'BOUNDED RETRY',
      desc: 'Detects test failures and execution anomalies, classifies root causes via failure taxonomy, and orchestrates bounded replans within strict attempt and time budgets.',
      why: 'Provides automated self-healing without infinite retry loops or runaway costs. Every failure and retry attempt is permanently recorded.',
      api: 'GET /api/tasks/{id}/recovery',
      status: 'BOUNDED ACTIVE'
    },
    evidence: {
      name: 'Immutable Evidence & Provenance Ledger',
      badge: 'CRYPTOGRAPHIC PROVENANCE',
      desc: 'Maintains an immutable, chronologically ordered ledger distinguishing CLAIMED hypotheses, OBSERVED runtime events, and VERIFIED proof.',
      why: 'Enables complete post-mission forensics and regulatory auditability. Allows operators to answer "Why does ORION believe this mission succeeded?".',
      api: 'GET /api/tasks/{id}/evidence',
      status: 'TAMPER-PROOF'
    },
    report: {
      name: 'Certified SWE Mission Report',
      badge: 'CERTIFIED OUTCOME',
      desc: 'Synthesizes the comprehensive, tamper-resistant mission certificate documenting directive resolution, code diffs, test outputs, and verification signatures.',
      why: 'Provides a single authoritative artifact that certifies software engineering correctness for stakeholders and downstream CI/CD pipelines.',
      api: 'GET /api/tasks/{id}/report',
      status: 'CERTIFIED'
    }
  };

  function initArchitectureExplorer() {
    if (!dom.archPipelineFlow) return;
    dom.archPipelineFlow.querySelectorAll('.arch-node-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const sub = chip.dataset.subsystem;
        selectArchitectureSubsystem(sub);
      });
    });
  }

  function openArchitectureModal() {
    if (!dom.architectureModal) return;
    dom.architectureModal.classList.add('open');
    selectArchitectureSubsystem('user_task');
  }

  function closeArchitectureModal() {
    if (!dom.architectureModal) return;
    dom.architectureModal.classList.remove('open');
  }

  function selectArchitectureSubsystem(subsystemId) {
    const spec = SUBSYSTEM_SPECS[subsystemId];
    if (!spec || !dom.archDetailPanel) return;

    if (dom.archPipelineFlow) {
      dom.archPipelineFlow.querySelectorAll('.arch-node-chip').forEach(chip => {
        if (chip.dataset.subsystem === subsystemId) chip.classList.add('active');
        else chip.classList.remove('active');
      });
    }

    dom.archDetailPanel.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
        <div>
          <span class="badge badge-cyan" style="margin-bottom:4px;">${escapeHtml(spec.badge)}</span>
          <h4 style="font-size:14px; font-weight:700; color:var(--text-main); margin:0;">${escapeHtml(spec.name)}</h4>
        </div>
        <span class="badge badge-emerald">${escapeHtml(spec.status)}</span>
      </div>

      <div style="display:flex; flex-direction:column; gap:10px;">
        <div>
          <strong class="text-cyan" style="font-family:var(--font-mono); font-size:11px; text-transform:uppercase;">1. Core Subsystem Responsibility:</strong>
          <p style="font-size:12px; color:var(--text-secondary); margin:4px 0 0 0; line-height:1.45;">${escapeHtml(spec.desc)}</p>
        </div>
        <div>
          <strong class="text-purple" style="font-family:var(--font-mono); font-size:11px; text-transform:uppercase;">2. Architectural Rationale:</strong>
          <p style="font-size:12px; color:var(--text-secondary); margin:4px 0 0 0; line-height:1.45;">${escapeHtml(spec.why)}</p>
        </div>
        <div style="padding-top:6px; border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
          <span style="font-family:var(--font-mono); font-size:11px; color:var(--text-dim);">Active REST / SSE Surface:</span>
          <code class="code-val text-cyan" style="font-size:11px;">${escapeHtml(spec.api)}</code>
        </div>
      </div>
    `;
  }

  // -------------------------------------------------------------
  // Guided Product Tour Engine
  // -------------------------------------------------------------
  const TOUR_STEPS = [
    {
      step: 1,
      title: 'Mission Command Center',
      tab: 'tab-overview',
      target: '#commandInputSection',
      desc: 'The central directive entry console. Submit natural-language software engineering tasks, select controlled or autonomous mode, or pick from quick-start templates.'
    },
    {
      step: 2,
      title: 'Interactive Demonstration Center',
      tab: 'tab-demo',
      target: '#tab-demo',
      desc: 'Explore ORION\'s capabilities with 5 deterministic, truth-grounded engineering scenarios. Use the 7-stage scrubber player to inspect real evidence at every stage.'
    },
    {
      step: 3,
      title: 'Execution Graph (DAG Topology)',
      tab: 'tab-graph',
      target: '#tab-graph',
      desc: 'Deterministic 7-stage execution graph with strictly monotonic state transitions. Visualizes work nodes, dependencies, and approval gates.'
    },
    {
      step: 4,
      title: 'Specialist Workforce Roster',
      tab: 'tab-workforce',
      target: '#tab-workforce',
      desc: 'Separation of duties across specialized agents: SWE-Engineer, Diagnostics, Authoritative-Verifier, and Recovery-Coordinator.'
    },
    {
      step: 5,
      title: 'Repository Intelligence',
      tab: 'tab-repo',
      target: '#tab-repo',
      desc: 'Static analysis of repository topology, AST cross-file call graphs, change blast radius calculation, and token-bounded context assembly.'
    },
    {
      step: 6,
      title: 'Patch Intelligence & Diff Inspector',
      tab: 'tab-changes',
      target: '#tab-changes',
      desc: 'Syntax-aware unified diff preview with line numbers and file statistics. Inspect exact additions and deletions before and after execution.'
    },
    {
      step: 7,
      title: 'Controlled Tests Runner',
      tab: 'tab-tests',
      target: '#tab-tests',
      desc: 'Real-time test execution terminal output with process exit codes, execution duration, and test assertion breakdown.'
    },
    {
      step: 8,
      title: 'Authoritative Verification Authority',
      tab: 'tab-verification',
      target: '#tab-verification',
      desc: 'The foundation of ORION: EXECUTION ≠ SUCCESS, VERIFIED EXECUTION = SUCCESS. VerificationEngine evaluates ground truth proof.'
    },
    {
      step: 9,
      title: 'Bounded Self-Healing Recovery',
      tab: 'tab-recovery',
      target: '#tab-recovery',
      desc: 'Automated recovery loop with failure taxonomy classification, retry budget enforcement, and transparent failure records.'
    },
    {
      step: 10,
      title: 'Evidence Ledger & Certified Report',
      tab: 'tab-evidence',
      target: '#tab-evidence',
      desc: 'Cryptographically verifiable evidence ledger categorizing CLAIMED, OBSERVED, and VERIFIED proof, culminating in the Certified SWE Mission Report.'
    }
  ];

  let currentTourStep = 0;

  function initProductTour() {
    // Initialized ready for trigger
  }

  function startProductTour() {
    currentTourStep = 0;
    renderTourStep(0);
    if (dom.productTourCard) dom.productTourCard.style.display = 'flex';
  }

  function endProductTour() {
    if (dom.productTourCard) dom.productTourCard.style.display = 'none';
  }

  function renderTourStep(stepIdx) {
    const s = TOUR_STEPS[stepIdx];
    if (!s) return;
    currentTourStep = stepIdx;
    switchTab(s.tab);
    if (dom.tourStepBadge) dom.tourStepBadge.textContent = `STEP ${s.step} OF ${TOUR_STEPS.length}`;
    if (dom.tourTitle) dom.tourTitle.textContent = s.title;
    if (dom.tourDescription) dom.tourDescription.textContent = s.desc;
    if (dom.btnTourPrev) dom.btnTourPrev.disabled = (stepIdx === 0);
    if (dom.btnTourNext) dom.btnTourNext.textContent = (stepIdx === TOUR_STEPS.length - 1) ? 'Finish Tour' : 'Next →';
  }

  function stepTourNext() {
    if (currentTourStep >= TOUR_STEPS.length - 1) {
      endProductTour();
      showToast('Tour Completed', 'You can restart the tour anytime via Tour button or Ctrl+K.', 'info');
    } else {
      renderTourStep(currentTourStep + 1);
    }
  }

  function stepTourPrev() {
    if (currentTourStep > 0) {
      renderTourStep(currentTourStep - 1);
    }
  }

  // -------------------------------------------------------------
  // Presentation Mode Engine
  // -------------------------------------------------------------
  function togglePresentationMode() {
    const isPres = document.body.classList.toggle('presentation-mode');
    if (dom.presentationBanner) dom.presentationBanner.style.display = isPres ? 'flex' : 'none';
    showToast(isPres ? 'Presentation Mode Active' : 'Presentation Mode Exited',
              isPres ? 'High-legibility presentation display enabled. Press [P] or Esc to exit.' : 'Restored workstation view.',
              'info');
  }

  function exitPresentationMode() {
    document.body.classList.remove('presentation-mode');
    if (dom.presentationBanner) dom.presentationBanner.style.display = 'none';
  }

  function initPresentationMode() {
    window.addEventListener('keydown', (e) => {
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') return;
      if (e.key === 'p' || e.key === 'P') {
        if (!e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          togglePresentationMode();
        }
      } else if (e.key === 'Escape') {
        if (document.body.classList.contains('presentation-mode')) {
          exitPresentationMode();
        }
      }
    });
  }

  // -------------------------------------------------------------
  // Mission Templates Engine
  // -------------------------------------------------------------
  function initMissionTemplates() {
    if (!dom.missionTemplatesBar) return;
    dom.missionTemplatesBar.querySelectorAll('.template-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        const mode = chip.dataset.mode || 'controlled';
        const taskName = chip.dataset.task || 'Template Task';
        if (dom.taskInputPrompt) dom.taskInputPrompt.value = prompt;
        if (dom.executionModeSelect) dom.executionModeSelect.value = mode;
        if (dom.workspaceInputPath) dom.workspaceInputPath.value = 'C:/Users/LIKITH/ORION';
        showToast('Template Applied', `Applied template: "${taskName}". Ready to launch.`, 'info');
        if (dom.taskInputPrompt) dom.taskInputPrompt.focus();
      });
    });
  }

  // -------------------------------------------------------------
  // Timeline Replay Scrubber Engine
  // -------------------------------------------------------------
  let recordedTimelineEvents = [];
  let isReplayModeActive = false;

  function initTimelineReplay() {
    if (dom.timelineReplayScrubber) {
      dom.timelineReplayScrubber.addEventListener('input', (e) => {
        handleReplayScrub(parseInt(e.target.value, 10));
      });
    }
    if (dom.btnReplayPrev) {
      dom.btnReplayPrev.addEventListener('click', () => {
        if (dom.timelineReplayScrubber) {
          const val = Math.max(0, parseInt(dom.timelineReplayScrubber.value, 10) - 1);
          dom.timelineReplayScrubber.value = val;
          handleReplayScrub(val);
        }
      });
    }
    if (dom.btnReplayNext) {
      dom.btnReplayNext.addEventListener('click', () => {
        if (dom.timelineReplayScrubber) {
          const max = parseInt(dom.timelineReplayScrubber.max, 10);
          const val = Math.min(max, parseInt(dom.timelineReplayScrubber.value, 10) + 1);
          dom.timelineReplayScrubber.value = val;
          handleReplayScrub(val);
        }
      });
    }
    if (dom.btnReplayLive) {
      dom.btnReplayLive.addEventListener('click', returnToLiveStream);
    }
  }

  function handleReplayScrub(stepIndex) {
    if (recordedTimelineEvents.length === 0) return;
    isReplayModeActive = (stepIndex < recordedTimelineEvents.length - 1);
    if (dom.replayStepCounter) {
      dom.replayStepCounter.textContent = `${stepIndex + 1} / ${recordedTimelineEvents.length}`;
    }
    const sliced = recordedTimelineEvents.slice(0, stepIndex + 1);
    dom.timelineStream.innerHTML = sliced.slice().reverse().map(e => `
      <div class="timeline-entry ${isReplayModeActive ? 'replay-item' : ''}">
        <span class="entry-time">${formatTime(e.timestamp)}</span>
        <div class="entry-body">
          <div class="entry-title">${escapeHtml(e.title)}</div>
          <div class="entry-detail">${escapeHtml(e.detail)}</div>
        </div>
      </div>
    `).join('');
  }

  function returnToLiveStream() {
    isReplayModeActive = false;
    if (dom.timelineReplayScrubber) {
      dom.timelineReplayScrubber.value = recordedTimelineEvents.length - 1;
    }
    if (dom.replayStepCounter) {
      dom.replayStepCounter.textContent = `${recordedTimelineEvents.length} / ${recordedTimelineEvents.length}`;
    }
    renderTimeline(recordedTimelineEvents);
    showToast('Live View Restored', 'Synchronized timeline with real-time stream.', 'info');
  }

  // -------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------
  async function init() {
    bindEvents();
    initIntroOverlay();
    initCommandPalette();
    initDemoCenter();
    initArchitectureExplorer();
    initProductTour();
    initPresentationMode();
    initMissionTemplates();
    initTimelineReplay();
    await syncHealth();
    await loadInitialTasks();
    await loadPolicyData();
    await loadEvalData();
    startFallbackPolling();
  }

  function bindEvents() {
    // Navigation Tabs
    dom.commandTabBar.addEventListener('click', (e) => {
      const btn = e.target.closest('.tab-btn');
      if (btn && btn.dataset.tab) {
        switchTab(btn.dataset.tab);
      }
    });

    // Evidence Filters
    dom.evidenceFilterGroup.addEventListener('click', (e) => {
      if (e.target.classList.contains('filter-btn')) {
        dom.evidenceFilterGroup.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentEvidenceFilter = e.target.dataset.filter;
        renderEvidenceList();
      }
    });

    // Primary Command Center Task Submission
    dom.commandCenterForm.addEventListener('submit', handleTaskDirectiveSubmit);

    // New Task Modal
    dom.btnNewMission.addEventListener('click', () => dom.modalBackdrop.classList.add('open'));
    dom.modalCloseBtn.addEventListener('click', () => dom.modalBackdrop.classList.remove('open'));
    dom.btnCancelModal.addEventListener('click', () => dom.modalBackdrop.classList.remove('open'));
    dom.createMissionForm.addEventListener('submit', handleCreateMissionSubmit);

    // Approval Modal Controls
    dom.btnInspectApprovalDiff.addEventListener('click', openApprovalModal);
    dom.modalApprovalCloseBtn.addEventListener('click', closeApprovalModal);
    dom.btnQuickApprove.addEventListener('click', () => submitApprovalDecision('approve'));
    dom.btnQuickDeny.addEventListener('click', () => submitApprovalDecision('deny'));
    dom.btnModalDeny.addEventListener('click', () => submitApprovalDecision('deny'));
    dom.approvalDecisionForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitApprovalDecision('approve');
    });

    // Mission Controls
    dom.btnRefresh.addEventListener('click', async () => {
      await syncHealth();
      if (currentTaskId) await refreshTaskData(currentTaskId);
      await loadPolicyData();
      await loadEvalData();
    });

    dom.btnRunPipeline.addEventListener('click', handleRunPipelineClick);
    dom.btnAdvanceStage.addEventListener('click', handleAdvanceStageClick);
    if (dom.btnCancelMission) {
      dom.btnCancelMission.addEventListener('click', handleCancelMissionClick);
    }
    if (dom.btnReconnectNow) {
      dom.btnReconnectNow.addEventListener('click', () => {
        if (currentTaskId) connectEventStream(currentTaskId);
      });
    }
    dom.btnGenReportNow.addEventListener('click', handleGenerateReportClick);
    dom.btnCopyDiff.addEventListener('click', handleCopyDiffClick);

    // Quick Operator Interventions (Screen 1 & 8)
    if (dom.btnQuickPause) dom.btnQuickPause.addEventListener('click', () => handleIntervention('pause', 'Manual operator pause from Mission Command Center'));
    if (dom.btnQuickResume) dom.btnQuickResume.addEventListener('click', () => handleIntervention('resume', 'Manual operator resume from Mission Command Center'));
    if (dom.btnQuickSteer) dom.btnQuickSteer.addEventListener('click', handleQuickSteerPrompt);
    if (dom.btnQuickForceFail) dom.btnQuickForceFail.addEventListener('click', () => handleIntervention('force_fail', 'Manual operator emergency termination'));

    // Repo Intelligence (Screen 4)
    if (dom.btnAnalyzeImpact) dom.btnAnalyzeImpact.addEventListener('click', handleAnalyzeImpact);
    if (dom.btnAnalyzeContext) dom.btnAnalyzeContext.addEventListener('click', handleAnalyzeContext);

    // Human Oversight (Screen 8)
    if (dom.hitlInterveneForm) {
      dom.hitlInterveneForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const action = dom.hitlInterveneAction ? dom.hitlInterveneAction.value : 'pause';
        const reason = dom.hitlInterveneReason ? dom.hitlInterveneReason.value : 'Operator directive';
        const payload = dom.hitlIntervenePayload ? dom.hitlIntervenePayload.value : '';
        handleIntervention(action, reason, payload);
      });
    }
    if (dom.hitlFeedbackForm) {
      dom.hitlFeedbackForm.addEventListener('submit', handleFeedbackSubmit);
    }

    // Policy Simulator (Screen 9)
    if (dom.policySimForm) {
      dom.policySimForm.addEventListener('submit', handlePolicySimulate);
    }

    // Evaluation Lab (Screen 10)
    if (dom.evalRunForm) {
      dom.evalRunForm.addEventListener('submit', handleEvalRunSubmit);
    }
    if (dom.btnRefreshEvalRuns) {
      dom.btnRefreshEvalRuns.addEventListener('click', loadEvalData);
    }
    if (dom.btnCompareExperiments) {
      dom.btnCompareExperiments.addEventListener('click', handleEvalCompareClick);
    }

    // Observability (Screen 11)
    if (dom.btnRefreshSpans) {
      dom.btnRefreshSpans.addEventListener('click', () => {
        if (currentTaskId) loadObsData(currentTaskId);
      });
    }

    // Demo Center Controls
    if (dom.btnDemoPlay) dom.btnDemoPlay.addEventListener('click', toggleDemoPlay);
    if (dom.btnDemoRestart) dom.btnDemoRestart.addEventListener('click', restartDemo);
    if (dom.btnDemoPrevStage) dom.btnDemoPrevStage.addEventListener('click', stepDemoPrev);
    if (dom.btnDemoNextStage) dom.btnDemoNextStage.addEventListener('click', stepDemoNext);
    if (dom.btnDemoRunReal) dom.btnDemoRunReal.addEventListener('click', handleDemoRunAsRealMission);
    if (dom.demoSpeedSelect) {
      dom.demoSpeedSelect.addEventListener('change', (e) => {
        demoState.speed = parseInt(e.target.value, 10) || 1;
        if (demoState.isPlaying) {
          stopDemoTimer();
          startDemoTimer();
        }
      });
    }
    if (dom.demoScrubber) {
      dom.demoScrubber.addEventListener('input', (e) => {
        const stage = parseInt(e.target.value, 10);
        renderDemoStage(stage);
      });
    }

    // Architecture Modal Controls
    if (dom.btnOpenArchitecture) dom.btnOpenArchitecture.addEventListener('click', openArchitectureModal);
    if (dom.btnArchClose) dom.btnArchClose.addEventListener('click', closeArchitectureModal);
    if (dom.architectureModal) {
      dom.architectureModal.addEventListener('click', (e) => {
        if (e.target === dom.architectureModal) closeArchitectureModal();
      });
    }

    // Presentation Mode Controls
    if (dom.btnPresentationMode) dom.btnPresentationMode.addEventListener('click', togglePresentationMode);
    if (dom.btnExitPresentation) dom.btnExitPresentation.addEventListener('click', exitPresentationMode);

    // Product Tour Controls
    if (dom.btnHelpTour) dom.btnHelpTour.addEventListener('click', startProductTour);
    if (dom.btnTourClose) dom.btnTourClose.addEventListener('click', endProductTour);
    if (dom.btnTourSkip) dom.btnTourSkip.addEventListener('click', endProductTour);
    if (dom.btnTourPrev) dom.btnTourPrev.addEventListener('click', stepTourPrev);
    if (dom.btnTourNext) dom.btnTourNext.addEventListener('click', stepTourNext);
  }

  function switchTab(tabId) {
    dom.commandTabBar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    const panel = document.getElementById(tabId);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');

    // Update IDE breadcrumbs
    if (dom.bcSection && dom.bcTarget && TAB_METADATA[tabId]) {
      dom.bcSection.textContent = TAB_METADATA[tabId].section;
      dom.bcTarget.textContent = TAB_METADATA[tabId].target;
    }

    // Trigger tab-specific refresh
    if (currentTaskId) {
      if (tabId === 'tab-overview' || tabId === 'tab-graph' || tabId === 'tab-workforce' ||
          tabId === 'tab-changes' || tabId === 'tab-tests' || tabId === 'tab-verification' ||
          tabId === 'tab-recovery' || tabId === 'tab-evidence') {
        refreshTaskData(currentTaskId);
      }
    }
    if (tabId === 'tab-repo') loadRepoData();
    if (tabId === 'tab-hitl') loadHitlData(currentTaskId);
    if (tabId === 'tab-policy') loadPolicyData();
    if (tabId === 'tab-eval') loadEvalData();
    if (tabId === 'tab-observability') loadObsData(currentTaskId);
  }

  // -------------------------------------------------------------
  // Real-Time SSE Stream Management
  // -------------------------------------------------------------
  function connectEventStream(taskId) {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    dom.sseStatusDot.className = 'status-dot pulsing-cyan';
    dom.sseStatusText.textContent = 'CONNECTING...';

    const sseUrl = `/api/tasks/${taskId}/events`;
    eventSource = new EventSource(sseUrl);

    eventSource.onopen = function () {
      dom.sseStatusDot.className = 'status-dot online';
      dom.sseStatusText.textContent = 'SSE LIVE';
      if (dom.connectionLostBanner) dom.connectionLostBanner.style.display = 'none';
    };

    eventSource.onerror = function () {
      dom.sseStatusDot.className = 'status-dot pulsing-amber';
      dom.sseStatusText.textContent = 'RETRYING...';
      if (dom.connectionLostBanner) dom.connectionLostBanner.style.display = 'flex';
    };

    eventSource.onmessage = function (e) {
      try {
        const payload = JSON.parse(e.data);
        handleIncomingEvent(payload);
      } catch (err) {
        // Ping comment or raw string
      }
    };

    // Explicit Event Listeners
    const eventTypes = [
      'CONNECTED',
      'TASK_CREATED',
      'PLAN_CREATED',
      'AGENT_STARTED',
      'AGENT_COMPLETED',
      'FILE_INSPECTED',
      'PATCH_PROPOSED',
      'APPROVAL_REQUIRED',
      'PATCH_APPROVED',
      'PATCH_DENIED',
      'PATCH_APPLIED',
      'TEST_STARTED',
      'TEST_COMPLETED',
      'VERIFICATION_STARTED',
      'VERIFICATION_COMPLETED',
      'FAILURE_DETECTED',
      'RECOVERY_PLANNED',
      'RECOVERY_STARTED',
      'RECOVERY_COMPLETED',
      'ROLLBACK_STARTED',
      'ROLLBACK_COMPLETED',
      'STAGE_STARTED',
      'STAGE_COMPLETED',
      'TOOL_EXECUTED',
      'TASK_COMPLETED',
      'TASK_CANCELLED',
      'TASK_TERMINATED',
    ];

    eventTypes.forEach(ev => {
      eventSource.addEventListener(ev, (e) => {
        try {
          const payload = JSON.parse(e.data);
          handleIncomingEvent(payload);
        } catch (err) {
          console.warn('Could not parse event payload:', e.data);
        }
      });
    });
  }

  function handleIncomingEvent(payload) {
    const evName = payload.event;
    const data = payload.data || {};

    // Append to live timeline
    appendTimelineEvent({
      title: evName ? evName.replace(/_/g, ' ') : 'System Event',
      detail: data.summary || data.detail || evName,
      timestamp: payload.timestamp || new Date().toISOString(),
      level: data.level || (evName.includes('FAIL') || evName.includes('DENIED') || evName.includes('CANCEL') ? 'error' : (evName.includes('APPROVED') || evName.includes('COMPLETED') ? 'success' : 'info')),
    });

    // Update active agent based on AGENT_STARTED
    if (evName === 'AGENT_STARTED') {
      highlightActiveAgent(data.agent, data.stage);
    } else if (evName === 'AGENT_COMPLETED') {
      resetAgentHighlight();
    }

    // Handle APPROVAL_REQUIRED: show banner & update pending approval package
    if (evName === 'APPROVAL_REQUIRED') {
      activePendingApproval = data;
      showApprovalAlert(data);
      dom.tabRecoveryPulse.style.display = 'inline-block';
      showToast('Dual-Key Approval Required', data.summary || 'A synthesized patch requires operator authorization.', 'warning', 6000);
    } else if (evName === 'PATCH_APPROVED' || evName === 'PATCH_DENIED') {
      hideApprovalAlert();
      closeApprovalModal();
      showToast(evName === 'PATCH_APPROVED' ? 'Patch Authorized' : 'Patch Denied', evName === 'PATCH_APPROVED' ? 'Applied patch to workspace with transactional rollback safety.' : 'Patch denied by operator.', evName === 'PATCH_APPROVED' ? 'success' : 'warning');
    } else if (evName === 'VERIFICATION_COMPLETED') {
      const isSuccess = data.decision === 'AUTHORITATIVE_VERIFIED_SUCCESS' || data.status === 'SATISFIED';
      showToast('Verification Authority', isSuccess ? 'Authoritative Verification confirmed task ground truth.' : 'VerificationEngine evaluated result: Unverified/Failed.', isSuccess ? 'success' : 'error', 5000);
    } else if (evName === 'TASK_COMPLETED') {
      showToast('Mission Completed', data.summary || 'Engineering pipeline execution completed.', 'success', 5000);
    } else if (evName === 'RECOVERY_STARTED') {
      showToast('Self-Healing Recovery', data.summary || 'Bounded recovery loop triggered after failure detection.', 'warning', 4500);
    }

    // Handle TASK_CANCELLED
    if (evName === 'TASK_CANCELLED') {
      dom.missionStatusBadge.textContent = 'CANCELLED';
      dom.missionStatusBadge.className = 'badge badge-rose';
      dom.missionLifecycleBadge.textContent = 'STATE: CANCELLED';
      dom.btnRunPipeline.disabled = true;
      dom.btnAdvanceStage.disabled = true;
      if (dom.btnCancelMission) dom.btnCancelMission.disabled = true;
    }

    // Refresh telemetry components asynchronously
    if (currentTaskId) {
      refreshTaskData(currentTaskId);
    }
  }

  function highlightActiveAgent(agentName, stage) {
    dom.agentSWE.classList.remove('active-agent');
    dom.agentDiagnostics.classList.remove('active-agent');
    dom.agentVerifier.classList.remove('active-agent');
    dom.agentRecovery.classList.remove('active-agent');

    if (stage === 'analyze_failure') {
      dom.agentDiagnostics.classList.add('active-agent');
      dom.badgeAgentDiagnostics.textContent = 'ACTIVE';
      dom.badgeAgentDiagnostics.className = 'agent-state-badge badge-active';
    } else if (stage === 'verify') {
      dom.agentVerifier.classList.add('active-agent');
      dom.badgeAgentVerifier.textContent = 'ACTIVE';
      dom.badgeAgentVerifier.className = 'agent-state-badge badge-active';
    } else if (stage === 'recovery' || stage === 'recovering') {
      dom.agentRecovery.classList.add('active-agent');
      dom.badgeAgentRecovery.textContent = 'ACTIVE';
      dom.badgeAgentRecovery.className = 'agent-state-badge badge-active';
    } else {
      dom.agentSWE.classList.add('active-agent');
      dom.badgeAgentSWE.textContent = 'ACTIVE';
      dom.badgeAgentSWE.className = 'agent-state-badge badge-active';
    }
  }

  function resetAgentHighlight() {
    dom.badgeAgentSWE.textContent = 'STANDBY';
    dom.badgeAgentSWE.className = 'agent-state-badge badge-idle';
    dom.badgeAgentDiagnostics.textContent = 'STANDBY';
    dom.badgeAgentDiagnostics.className = 'agent-state-badge badge-idle';
    dom.badgeAgentVerifier.textContent = 'STANDBY';
    dom.badgeAgentVerifier.className = 'agent-state-badge badge-idle';
    dom.badgeAgentRecovery.textContent = 'STANDBY';
    dom.badgeAgentRecovery.className = 'agent-state-badge badge-idle';
  }

  // -------------------------------------------------------------
  // Approval UI Management
  // -------------------------------------------------------------
  function showApprovalAlert(data) {
    dom.approvalAlertBanner.style.display = 'flex';
    dom.approvalToolBadge.textContent = `TOOL: ${data.action || 'apply_change'}`;
    dom.approvalRiskBadge.textContent = `RISK: ${data.risk_level || 'HIGH'}`;
    dom.approvalRationaleText.textContent = data.rationale || data.summary || 'Code modification requires explicit authorization.';
    dom.ovApprovalStatus.innerHTML = '<span class="badge badge-amber pulsing-amber">AWAITING OPERATOR DECISION</span>';
  }

  function hideApprovalAlert() {
    dom.approvalAlertBanner.style.display = 'none';
  }

  function openApprovalModal() {
    if (activePendingApproval) {
      dom.modalApprovalReqId.textContent = activePendingApproval.request_id || '--';
      dom.modalApprovalAction.textContent = `${activePendingApproval.action || 'apply_change'}`;
      dom.modalApprovalFiles.textContent = (activePendingApproval.affected_files || []).join(', ') || 'Repository files';
      dom.modalApprovalRationale.textContent = activePendingApproval.rationale || 'Authorized patch proposal';
      dom.modalApprovalDiff.textContent = activePendingApproval.diff || activePendingApproval.diff_summary || 'No diff available';
    }
    dom.approvalModalBackdrop.classList.add('open');
  }

  function closeApprovalModal() {
    dom.approvalModalBackdrop.classList.remove('open');
  }

  async function submitApprovalDecision(decision) {
    if (!currentTaskId) return;

    const approver = dom.inputApproverName.value || 'LeadSecurityOfficer';
    const reason = dom.inputApprovalReason.value || `${decision} authorized by operator`;
    const reqId = activePendingApproval ? activePendingApproval.request_id : null;

    try {
      const res = await fetch(`/api/tasks/${currentTaskId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision: decision,
          approver: approver,
          reason: reason,
          request_id: reqId,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        showToast('Approval Action Failed', err.error || 'Server error', 'error');
        return;
      }

      hideApprovalAlert();
      closeApprovalModal();
      showToast('Decision Recorded', `Security approval action: ${decision}`, 'success');
      await refreshTaskData(currentTaskId);
    } catch (err) {
      showToast('Network Error', `Network error submitting approval: ${err}`, 'error');
    }
  }

  // -------------------------------------------------------------
  // Data Fetching & Sync
  // -------------------------------------------------------------
  async function syncHealth() {
    try {
      const res = await fetch('/api/v1/health');
      if (!res.ok) return;
      const data = await res.json();
      if (dom.engineUptime) dom.engineUptime.textContent = `${data.uptime_seconds}s`;
      if (dom.activeMissionsCount) dom.activeMissionsCount.textContent = data.missions_count;
      if (dom.coreStatusText) dom.coreStatusText.textContent = 'DETERMINISTIC // ONLINE';
      if (dom.coreStatusDot) dom.coreStatusDot.className = 'status-dot online';

      // Update intro system states from real backend health
      if (dom.introSysState) dom.introSysState.textContent = 'ONLINE';
      if (dom.introEngineState) dom.introEngineState.textContent = 'READY';
      if (dom.introWorkspaceState) dom.introWorkspaceState.textContent = 'CONTAINED';
      if (dom.introVerifState) dom.introVerifState.textContent = 'AUTHORITATIVE';

      // Update footer status bar
      const coreFooter = document.getElementById('coreStatusTextFooter');
      if (coreFooter) coreFooter.textContent = 'ONLINE';
    } catch (err) {
      if (dom.coreStatusText) dom.coreStatusText.textContent = 'STANDALONE // OFFLINE';
      if (dom.coreStatusDot) dom.coreStatusDot.className = 'status-dot pulsing-amber';
    }
  }

  async function loadInitialTasks() {
    try {
      const res = await fetch('/api/tasks');
      if (res.ok) {
        const data = await res.json();
        const list = data.tasks || data.missions || [];
        if (list.length > 0) {
          const first = list[0];
          currentTaskId = first.task_id || first.mission_id;
          connectEventStream(currentTaskId);
          await refreshTaskData(currentTaskId);
        }
      }
    } catch (err) {
      console.warn('Initial task loading deferred:', err);
    }
  }

  const refreshMissionData = refreshTaskData;

  async function refreshTaskData(taskId) {
    try {
      // 1. Core Task Details
      const tRes = await fetch(`/api/tasks/${taskId}`);
      if (!tRes.ok) return;
      const task = await tRes.json();
      renderTaskHeader(task);

      // 2. Execution Telemetry
      const exRes = await fetch(`/api/tasks/${taskId}/execution`);
      if (exRes.ok) {
        const exec = await exRes.json();
        renderExecutionState(exec);
      }

      // 3. Code Changes
      const chRes = await fetch(`/api/tasks/${taskId}/changes`);
      if (chRes.ok) {
        const ch = await chRes.json();
        renderCodeChanges(ch);
      }

      // 4. Controlled Tests
      const testRes = await fetch(`/api/tasks/${taskId}/tests`);
      if (testRes.ok) {
        const tests = await testRes.json();
        renderTestResults(tests);
      }

      // 5. Recovery Observatory
      const recRes = await fetch(`/api/tasks/${taskId}/recovery`);
      if (recRes.ok) {
        const rec = await recRes.json();
        renderRecoveryObservatory(rec);
      }

      // 6. Verification
      const verRes = await fetch(`/api/tasks/${taskId}/verification`);
      if (verRes.ok) {
        const ver = await verRes.json();
        renderVerification(ver);
      }

      // 7. Evidence
      const evRes = await fetch(`/api/tasks/${taskId}/evidence`);
      if (evRes.ok) {
        const evData = await evRes.json();
        cachedEvidence = evData.evidence || [];
        renderEvidenceList();
      }

      // 8. Timeline
      const timeRes = await fetch(`/api/tasks/${taskId}/timeline`);
      if (timeRes.ok) {
        const timeData = await timeRes.json();
        renderTimeline(timeData.timeline || []);
      }

      // 9. Execution Graph (DAG)
      const grRes = await fetch(`/api/tasks/${taskId}/graph`);
      if (grRes.ok) {
        const grData = await grRes.json();
        renderExecutionGraph(grData);
      }

      // 10. Workforce Roster
      const agRes = await fetch(`/api/tasks/${taskId}/agents`);
      if (agRes.ok) {
        const agData = await agRes.json();
        renderWorkforceRoster(agData);
      }
    } catch (err) {
      console.error('Error refreshing task data:', err);
    }
  }

  // -------------------------------------------------------------
  // Renderers
  // -------------------------------------------------------------
  function renderTaskHeader(task) {
    dom.missionObjective.textContent = task.objective || 'Autonomous SWE Task';
    dom.missionIdBadge.textContent = `TASK: ${String(task.task_id || '').slice(0, 8)}`;
    dom.missionStatusBadge.textContent = (task.status || 'STANDBY').toUpperCase();
    dom.missionLifecycleBadge.textContent = `STATE: ${task.lifecycle_state || 'RECEIVED'}`;
    dom.missionWorkspaceBadge.textContent = `WORKSPACE: ${task.workspace_root ? task.workspace_root.split(/[\\/]/).pop() : 'LOCALHOST'}`;

    const missionShort = task.task_id ? String(task.task_id).slice(0, 8) : 'STANDBY';
    const missionLabel = task.task_id ? `MISSION-${String(task.task_id).slice(0, 8).toUpperCase()}` : 'STANDBY';
    const stageStr = task.current_stage ? task.current_stage.toUpperCase() : 'IDLE';

    if (dom.navMissionId) dom.navMissionId.textContent = missionShort;
    if (dom.navMissionStage) dom.navMissionStage.textContent = task.current_stage ? `STAGE: ${task.current_stage.toUpperCase()}` : 'STAGE: IDLE';
    if (dom.sbMissionText) dom.sbMissionText.textContent = missionLabel;
    if (dom.sbStageText) dom.sbStageText.textContent = stageStr;
    if (dom.bcMissionTail) dom.bcMissionTail.textContent = missionLabel;

    if (dom.navMissionPill) {
      if (task.status === 'running' || task.status === 'RUNNING') {
        dom.navMissionPill.classList.add('active');
      } else {
        dom.navMissionPill.classList.remove('active');
      }
    }

    if (task.cancelled) {
      dom.missionStatusBadge.textContent = 'CANCELLED';
      dom.missionStatusBadge.className = 'badge badge-rose';
      dom.missionLifecycleBadge.textContent = 'STATE: CANCELLED';
      dom.btnRunPipeline.disabled = true;
      dom.btnAdvanceStage.disabled = true;
      if (dom.btnCancelMission) dom.btnCancelMission.disabled = true;
    } else {
      dom.btnRunPipeline.disabled = false;
      dom.btnAdvanceStage.disabled = false;
      if (dom.btnCancelMission) dom.btnCancelMission.disabled = false;
    }

    // Overview panel
    dom.ovTaskId.textContent = task.task_id || 'None';
    dom.ovExecutionId.textContent = task.execution_id || 'None';
    dom.ovWorkspaceRoot.textContent = task.workspace_root || 'None';
    dom.ovLifecycleState.innerHTML = `<span class="badge badge-lifecycle">${task.lifecycle_state || 'RECEIVED'}</span>`;
    dom.ovCurrentStage.innerHTML = `<span class="badge badge-accent">${task.current_stage || 'None'}</span>`;
    dom.ovStagesCompleted.textContent = `${task.stages_completed_count || 0} / ${task.stages_total || 7}`;

    if (task.approval_required) {
      dom.ovApprovalStatus.innerHTML = '<span class="badge badge-amber pulsing-amber">APPROVAL REQUIRED</span>';
    } else {
      dom.ovApprovalStatus.innerHTML = '<span class="badge badge-emerald">CLEAN // PERMITTED</span>';
    }

    if (dom.ovBlockerStatus) {
      if (task.approval_required) {
        dom.ovBlockerStatus.innerHTML = '<span class="badge badge-amber">OPERATOR APPROVAL GATE</span>';
      } else if (task.status === 'paused') {
        dom.ovBlockerStatus.innerHTML = '<span class="badge badge-amber">OPERATOR PAUSED</span>';
      } else if (task.status === 'failed') {
        dom.ovBlockerStatus.innerHTML = '<span class="badge badge-rose">EXECUTION FAILURE</span>';
      } else {
        dom.ovBlockerStatus.innerHTML = '<span class="badge badge-emerald">UNBLOCKED</span>';
      }
    }

    if (dom.ovRecoveryState) {
      const isRec = task.status === 'recovering' || task.status === 'RECOVERING';
      dom.ovRecoveryState.innerHTML = `<span class="badge ${isRec ? 'badge-amber' : 'badge-idle'}">${isRec ? 'ACTIVE' : 'IDLE'}</span>`;
    }

    if (dom.ovVerificationState) {
      const isVer = task.completed_stages && task.completed_stages.includes('verify');
      dom.ovVerificationState.innerHTML = `<span class="badge ${isVer ? 'badge-emerald' : 'badge-idle'}">${isVer ? 'CERTIFIED' : 'PENDING'}</span>`;
    }

    if (dom.ovEvidenceTier && task.evidence_counts) {
      dom.ovEvidenceTier.innerHTML = `<span class="badge badge-cyan">${task.evidence_counts.total || 0} RECORDS</span>`;
    }

    // Stepper
    updateStepper(task.completed_stages || [], task.current_stage, task.approval_required);

    // Evidence counter
    if (task.evidence_counts) {
      dom.metricEvidenceCount.textContent = `${task.evidence_counts.total || 0} Evidence`;
    }
  }

  function renderExecutionState(exec) {
    if (exec.approval_required && exec.pending_approval) {
      activePendingApproval = exec.pending_approval;
      showApprovalAlert(exec.pending_approval);
    } else {
      hideApprovalAlert();
    }
  }

  function updateStepper(completedStages, currentStage, approvalRequired) {
    const total = STAGES.length;
    const completedCount = completedStages.length;
    const pct = Math.min(100, Math.round(((completedCount) / total) * 100));
    dom.stepperFill.style.width = `${Math.max(12, pct)}%`;

    STAGES.forEach((stage) => {
      const node = document.getElementById(`step-${stage}`);
      if (!node) return;
      node.classList.remove('active', 'completed');

      if (completedStages.includes(stage)) {
        node.classList.add('completed');
        node.querySelector('.node-circle').innerHTML = '&check;';
      } else if (stage === currentStage) {
        node.classList.add('active');
      }
    });

    const gateNode = document.getElementById('step-approval_gate');
    if (gateNode) {
      gateNode.classList.remove('active', 'completed');
      if (approvalRequired) {
        gateNode.classList.add('active');
      } else if (completedStages.includes('implement_change')) {
        gateNode.classList.add('completed');
        gateNode.querySelector('.node-circle').innerHTML = '&check;';
      }
    }
  }

  function renderCodeChanges(ch) {
    const files = ch.affected_files || [];
    dom.modifiedFilesCount.textContent = `${files.length} Files`;
    dom.diffLinesAdded.textContent = `+${ch.total_lines_added || 0} lines`;
    dom.diffLinesRemoved.textContent = `-${ch.total_lines_removed || 0} lines`;
    dom.tabCounterChanges.textContent = String(files.length);

    dom.diffValidationBadge.textContent = `VALIDATION: ${ch.validation_status || 'PENDING'}`;
    dom.diffApprovalBadge.textContent = `APPROVAL: ${ch.approval_status || 'NONE'}`;
    dom.diffApplicationBadge.textContent = `APPLICATION: ${ch.application_status || 'PENDING'}`;

    if (ch.unified_diff && ch.unified_diff.trim()) {
      dom.diffFileLabel.textContent = files.length > 0 ? files.join(', ') : 'Unified Diff';
      dom.diffCodeBlock.innerHTML = formatUnifiedDiff(ch.unified_diff);
    } else {
      dom.diffCodeBlock.innerHTML = '<code>No patch proposals or modifications generated yet.</code>';
    }
  }

  function formatUnifiedDiff(diffText) {
    const lines = diffText.split('\n');
    return lines.map((line, idx) => {
      const escaped = escapeHtml(line);
      const gutter = `<span class="diff-line-gutter">${idx + 1}</span>`;
      if (line.startsWith('+') && !line.startsWith('+++')) {
        return `<span class="diff-line-add">${gutter}${escaped}</span>`;
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        return `<span class="diff-line-del">${gutter}${escaped}</span>`;
      } else if (line.startsWith('@@')) {
        return `<span class="diff-line-info"><span class="diff-line-gutter">--</span>${escaped}</span>`;
      }
      return `<span>${gutter}${escaped}</span>`;
    }).join('\n');
  }

  function renderTestResults(tests) {
    if (tests.executed) {
      dom.testTargetVal.textContent = tests.target || 'pytest';
      dom.testExitCodeBadge.textContent = `EXIT CODE: ${tests.exit_code !== null ? tests.exit_code : '--'}`;
      dom.testExitCodeBadge.className = tests.passed ? 'badge badge-emerald' : 'badge badge-rose';
      dom.testOutcomeBadge.textContent = tests.passed ? 'STATUS: PASSED' : 'STATUS: FAILED';
      dom.testOutcomeBadge.className = tests.passed ? 'badge badge-emerald' : 'badge badge-rose';
      dom.testDurationBadge.textContent = `DURATION: ${tests.duration}s`;

      dom.metricTestsPassed.textContent = tests.passed ? '1' : '0';
      dom.metricTestsFailed.textContent = tests.passed ? '0' : '1';

      const combined = [tests.stdout, tests.stderr].filter(Boolean).join('\n') || tests.output_summary;
      dom.testOutputContent.textContent = combined || 'Tests completed with exit code ' + tests.exit_code;
    } else {
      dom.testOutcomeBadge.textContent = 'STATUS: NOT RUN';
      dom.testOutcomeBadge.className = 'badge badge-idle';
      dom.testOutputContent.textContent = 'Controlled tests have not been executed yet.';
    }
  }

  function renderRecoveryObservatory(rec) {
    dom.recFailureCatVal.textContent = rec.failure_category || 'NONE DETECTED';
    dom.recStrategyVal.textContent = rec.recovery_strategy || 'NONE';
    dom.recAttemptVal.textContent = `${rec.attempt_number || 0} / 3`;
    dom.recLifecycleStateVal.textContent = rec.recovery_state || 'IDLE';

    dom.metricRecoveryAttempts.textContent = String(rec.attempt_number || 0);

    const b = rec.remaining_budget || {};
    const attRem = b.attempts_remaining !== undefined ? b.attempts_remaining : 3;
    dom.budgetValAttempts.textContent = `${attRem} / 3`;
    dom.budgetBarAttempts.style.width = `${Math.min(100, Math.round((attRem / 3) * 100))}%`;

    const timeRem = b.execution_seconds_remaining !== undefined ? b.execution_seconds_remaining : 120.0;
    dom.budgetValTime.textContent = `${timeRem}s`;
    dom.budgetBarTime.style.width = `${Math.min(100, Math.round((timeRem / 120.0) * 100))}%`;

    const patchRem = b.patch_regenerations_remaining !== undefined ? b.patch_regenerations_remaining : 2;
    dom.budgetValPatch.textContent = `${patchRem} / 2`;
    dom.budgetBarPatch.style.width = `${Math.min(100, Math.round((patchRem / 2) * 100))}%`;

    const testRem = b.test_retries_remaining !== undefined ? b.test_retries_remaining : 3;
    dom.budgetValTests.textContent = `${testRem} / 3`;
    dom.budgetBarTests.style.width = `${Math.min(100, Math.round((testRem / 3) * 100))}%`;

    if (rec.rollback_performed) {
      dom.rollbackAuditBadge.textContent = 'ROLLBACK: EXECUTED // ATTEMPTS ROLLED BACK CLEANLY';
      dom.rollbackAuditBadge.className = 'badge badge-amber';
    } else {
      dom.rollbackAuditBadge.textContent = 'ROLLBACK: CLEAN // NO UNVERIFIED MUTATIONS';
      dom.rollbackAuditBadge.className = 'badge badge-emerald';
    }

    // Render history
    const history = rec.history || [];
    if (history.length === 0) {
      dom.recoveryEventsList.innerHTML = '<div class="empty-state">No recovery events occurred. Clean pipeline execution.</div>';
    } else {
      dom.recoveryEventsList.innerHTML = history.map(item => `
        <div class="recovery-event-card">
          <div>
            <strong class="text-amber">Attempt #${item.attempt_number || 1} &bull; Strategy: ${item.strategy || 'TARGETED_REWRITE'}</strong>
            <p style="font-size: 11.5px; color: var(--text-muted); margin-top: 3px;">${escapeHtml(item.action || item.summary || 'Recovery attempt')}</p>
          </div>
          <span class="badge ${item.success ? 'badge-emerald' : 'badge-rose'}">${item.success ? 'RESOLVED' : 'FAILED'}</span>
        </div>
      `).join('');
    }
  }

  function renderVerification(ver) {
    dom.metricVerifPassed.textContent = ver.passed ? '1' : '0';

    if (ver.status === 'passed') {
      dom.verifStatusBox.innerHTML = `
        <span class="verif-icon" style="border-color: var(--accent-emerald); color: var(--accent-emerald);">&check;</span>
        <div>
          <h3 class="verif-heading text-emerald">Authoritative Verification Passed</h3>
          <p class="verif-sub">${escapeHtml(ver.reason || 'VerificationEngine ground-truth confirmed.')}</p>
        </div>
      `;
      dom.critExitCode.className = 'criterion-item passed';
      dom.critRequirements.className = 'criterion-item passed';
      dom.critEvidenceLedger.className = 'criterion-item passed';
    } else if (ver.status === 'failed') {
      dom.verifStatusBox.innerHTML = `
        <span class="verif-icon" style="border-color: var(--accent-rose); color: var(--accent-rose);">&times;</span>
        <div>
          <h3 class="verif-heading text-rose">Verification Failed</h3>
          <p class="verif-sub">${escapeHtml(ver.reason || 'VerificationEngine criteria not satisfied.')}</p>
        </div>
      `;
    } else {
      dom.verifStatusBox.innerHTML = `
        <span class="verif-icon">?</span>
        <div>
          <h3 class="verif-heading">Authoritative Verification Pending</h3>
          <p class="verif-sub">VerificationEngine runs during stage 6 (VERIFY).</p>
        </div>
      `;
    }
  }

  function renderEvidenceList() {
    let items = cachedEvidence;
    if (currentEvidenceFilter !== 'all') {
      items = cachedEvidence.filter(item => item.level.toLowerCase() === currentEvidenceFilter.toLowerCase());
    }

    dom.evidenceFilteredCount.textContent = `Showing ${items.length} of ${cachedEvidence.length} entries`;

    if (items.length === 0) {
      dom.evidenceFeed.innerHTML = '<div class="empty-state">No evidence records matching current filter.</div>';
      return;
    }

    dom.evidenceFeed.innerHTML = items.map(item => {
      const levelClass = item.level === 'verified' ? 'badge-emerald' : (item.level === 'observed' ? 'badge-cyan' : 'badge-purple');
      return `
        <div class="evidence-card">
          <div class="evidence-card-header">
            <div class="evidence-badges">
              <span class="badge ${levelClass}">${item.level.toUpperCase()}</span>
              <span class="badge badge-outline">${item.category}</span>
              <span class="badge badge-outline">stage: ${item.stage}</span>
            </div>
            <span class="evidence-time">${formatTime(item.timestamp)}</span>
          </div>
          <div class="evidence-summary">${escapeHtml(item.summary)}</div>
          <pre class="evidence-content"><code>${escapeHtml(item.content)}</code></pre>
          <div class="evidence-provenance">
            <span>SOURCE: ${escapeHtml(item.source)}</span>
            <span>TASK: ${item.task_id ? String(item.task_id).slice(0, 8) : '--'}</span>
            <span>TOOL: ${item.tool_name || 'none'}</span>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderTimeline(events) {
    if (events && Array.isArray(events)) {
      recordedTimelineEvents = [...events];
      if (dom.timelineReplayScrubber) {
        dom.timelineReplayScrubber.max = Math.max(0, recordedTimelineEvents.length - 1);
        if (!isReplayModeActive) {
          dom.timelineReplayScrubber.value = Math.max(0, recordedTimelineEvents.length - 1);
        }
      }
      if (dom.replayStepCounter) {
        const curr = isReplayModeActive ? (parseInt(dom.timelineReplayScrubber?.value || '0', 10) + 1) : recordedTimelineEvents.length;
        dom.replayStepCounter.textContent = `${curr} / ${recordedTimelineEvents.length}`;
      }
    }

    if (!events || events.length === 0) {
      dom.timelineStream.innerHTML = '<div class="timeline-empty">Awaiting real-time execution stream...</div>';
      return;
    }

    dom.timelineStream.innerHTML = events.slice().reverse().map(e => `
      <div class="timeline-entry">
        <span class="entry-time">${formatTime(e.timestamp)}</span>
        <div class="entry-body">
          <div class="entry-title">${escapeHtml(e.title)}</div>
          <div class="entry-detail">${escapeHtml(e.detail)}</div>
        </div>
      </div>
    `).join('');
  }

  function appendTimelineEvent(e) {
    recordedTimelineEvents.push(e);
    if (dom.timelineReplayScrubber) {
      dom.timelineReplayScrubber.max = Math.max(0, recordedTimelineEvents.length - 1);
      if (!isReplayModeActive) {
        dom.timelineReplayScrubber.value = recordedTimelineEvents.length - 1;
      }
    }
    if (dom.replayStepCounter && !isReplayModeActive) {
      dom.replayStepCounter.textContent = `${recordedTimelineEvents.length} / ${recordedTimelineEvents.length}`;
    }
    if (isReplayModeActive) {
      return;
    }
    const entry = document.createElement('div');
    entry.className = 'timeline-entry';
    entry.innerHTML = `
      <span class="entry-time">${formatTime(e.timestamp)}</span>
      <div class="entry-body">
        <div class="entry-title">${escapeHtml(e.title)}</div>
        <div class="entry-detail">${escapeHtml(e.detail)}</div>
      </div>
    `;
    if (dom.timelineStream.querySelector('.timeline-empty')) {
      dom.timelineStream.innerHTML = '';
    }
    dom.timelineStream.insertBefore(entry, dom.timelineStream.firstChild);
  }

  // -------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------
  async function handleTaskDirectiveSubmit(e) {
    e.preventDefault();
    const task = dom.taskInputPrompt.value.trim();
    const workspace = dom.workspaceInputPath.value.trim();
    const execution_mode = dom.executionModeSelect.value;

    if (!task || !workspace) {
      showToast('Missing Parameters', 'Please provide both task directive and workspace root.', 'warning');
      return;
    }

    dom.btnSubmitTask.disabled = true;
    dom.btnSubmitTask.textContent = 'Launching...';

    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, workspace, execution_mode }),
      });

      if (!res.ok) {
        const err = await res.json();
        showToast('Launch Failed', `Failed to launch task: ${err.error || 'Server error'}`, 'error');
        return;
      }

      const created = await res.json();
      currentTaskId = created.task_id || created.mission_id;
      showToast('Mission Launched', `Mission ${currentTaskId.slice(0, 8)} started in ${execution_mode} mode.`, 'success');
      connectEventStream(currentTaskId);
      await refreshTaskData(currentTaskId);

      // Trigger execution pipeline immediately
      await fetch(`/api/tasks/${currentTaskId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: execution_mode === 'autonomous', background: true }),
      });
    } catch (err) {
      showToast('Network Error', `Network error submitting task: ${err}`, 'error');
    } finally {
      dom.btnSubmitTask.disabled = false;
      dom.btnSubmitTask.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Launch Mission';
    }
  }

  async function handleCreateMissionSubmit(e) {
    e.preventDefault();
    const objective = document.getElementById('inputObjective').value.trim();
    const workspace_path = document.getElementById('inputWorkspace').value.trim();
    const execution_mode = document.getElementById('inputExecutionMode').value;

    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: objective, workspace: workspace_path, execution_mode }),
      });

      if (!res.ok) {
        const err = await res.json();
        showToast('Creation Failed', `Error: ${err.error || 'Unknown error'}`, 'error');
        return;
      }

      const created = await res.json();
      currentTaskId = created.task_id || created.mission_id;
      dom.modalBackdrop.classList.remove('open');
      showToast('Mission Created', `Task ${currentTaskId.slice(0, 8)} initialized.`, 'success');
      connectEventStream(currentTaskId);
      await refreshTaskData(currentTaskId);
    } catch (err) {
      showToast('Network Error', `Error creating task: ${err}`, 'error');
    }
  }

  async function handleRunPipelineClick() {
    if (!currentTaskId) return;
    dom.btnRunPipeline.disabled = true;
    dom.btnRunPipeline.textContent = 'Running Pipeline...';

    try {
      const res = await fetch(`/api/tasks/${currentTaskId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: false, background: true }),
      });

      if (res.ok) {
        showToast('Pipeline Triggered', 'Mission execution sequence initiated.', 'info');
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        showToast('Pipeline Error', `Cannot run pipeline: ${err.error || 'Execution blocked'}`, 'error');
      }
    } catch (err) {
      console.error('Run pipeline error:', err);
    } finally {
      dom.btnRunPipeline.disabled = false;
      dom.btnRunPipeline.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Execute Pipeline';
    }
  }

  async function handleAdvanceStageClick() {
    if (!currentTaskId) return;

    try {
      const tRes = await fetch(`/api/tasks/${currentTaskId}`);
      if (!tRes.ok) return;
      const t = await tRes.json();

      const nextIdx = (t.completed_stages || []).length;
      if (nextIdx >= STAGES.length) {
        showToast('Workflow Complete', 'All 7 workflow stages are already completed.', 'info');
        return;
      }

      const nextStage = STAGES[nextIdx];
      const res = await fetch(`/api/v1/missions/${currentTaskId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: nextStage }),
      });

      if (res.ok) {
        showToast('Stage Advanced', `Advanced to stage: ${nextStage.toUpperCase()}`, 'success');
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        showToast('Advance Failed', `Cannot advance stage: ${err.error || 'Request failed'}`, 'error');
      }
    } catch (err) {
      console.error('Advance stage failed:', err);
    }
  }

  async function handleGenerateReportClick() {
    if (!currentTaskId) return;
    try {
      const res = await fetch(`/api/v1/missions/${currentTaskId}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: 'Authoritative certified SWE mission report' }),
      });

      if (res.ok) {
        const rep = await res.json();
        renderReportContent(rep);
        switchTab('tab-report');
        showToast('Report Generated', 'Authoritative Certified SWE Report compiled.', 'success');
      } else {
        const err = await res.json();
        showToast('Report Error', `Cannot generate report: ${err.error || 'Request failed'}`, 'error');
      }
    } catch (err) {
      console.error(err);
    }
  }

  function renderReportContent(rep) {
    dom.reportEmptyState.style.display = 'none';
    dom.reportContent.style.display = 'block';

    const statusBadge = rep.status === 'verified_success' ? '<span class="badge badge-emerald">VERIFIED SUCCESS</span>' : '<span class="badge badge-amber">PARTIAL / FAILED</span>';

    dom.reportContent.innerHTML = `
      <div class="report-box">
        <div class="report-header">
          <div>
            <h3 style="font-size: 16px; margin-bottom: 4px;">Certified SWE Task Report</h3>
            <span class="code-val">TASK ID: ${escapeHtml(rep.task_id)}</span>
          </div>
          ${statusBadge}
        </div>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">${escapeHtml(rep.summary)}</p>
        <div class="criteria-list">
          ${renderReportCritRow('All 7 Stages Completed', rep.evaluation.criteria.workflow_completed)}
          ${renderReportCritRow('Controlled Tests Passed', rep.evaluation.criteria.test_passed)}
          ${renderReportCritRow('Authoritative VerificationEngine Confirmed', rep.evaluation.criteria.verification_passed)}
          ${renderReportCritRow('Evidence Provenance Ledger Complete', rep.evaluation.criteria.evidence_complete)}
          ${renderReportCritRow('Code Modifications Traceable', rep.evaluation.criteria.changes_traceable)}
          ${renderReportCritRow('Recovery Transparency Preserved', rep.evaluation.criteria.recovery_transparent)}
        </div>
      </div>
    `;
  }

  function renderReportCritRow(label, passed) {
    return `
      <div class="criterion-item ${passed ? 'passed' : ''}">
        <span class="crit-icon">${passed ? '&check;' : '&times;'}</span>
        <span>${label}: <strong>${passed ? 'SATISFIED' : 'UNMET'}</strong></span>
      </div>
    `;
  }

  // -------------------------------------------------------------
  // Cancel Mission Handler
  // -------------------------------------------------------------
  async function handleCancelMissionClick() {
    if (!currentTaskId) return;
    if (!confirm('Are you sure you want to halt and cancel this active mission?')) return;

    try {
      const res = await fetch(`/api/tasks/${currentTaskId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Operator requested mission cancellation' }),
      });

      if (res.ok) {
        dom.missionStatusBadge.textContent = 'CANCELLED';
        dom.missionStatusBadge.className = 'badge badge-rose';
        dom.missionLifecycleBadge.textContent = 'STATE: CANCELLED';
        dom.btnRunPipeline.disabled = true;
        dom.btnAdvanceStage.disabled = true;
        if (dom.btnCancelMission) dom.btnCancelMission.disabled = true;
        showToast('Mission Cancelled', 'Mission execution halted by operator.', 'warning');
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        showToast('Cancel Failed', `Failed to cancel mission: ${err.error || 'Request failed'}`, 'error');
      }
    } catch (err) {
      showToast('Network Error', `Network error cancelling mission: ${err}`, 'error');
    }
  }

  // -------------------------------------------------------------
  // Execution Graph (DAG) Renderer
  // -------------------------------------------------------------
  function renderExecutionGraph(graph) {
    if (!graph || !graph.nodes || !dom.dagNodesGrid) return;

    if (dom.graphNodeCountBadge) {
      dom.graphNodeCountBadge.textContent = `${graph.total_nodes} Work Nodes`;
    }
    if (dom.tabCounterNodes) {
      dom.tabCounterNodes.textContent = graph.total_nodes;
    }
    if (dom.graphActiveNodeBadge) {
      dom.graphActiveNodeBadge.textContent = `CURRENT: ${(graph.active_node_id || 'STANDBY').toUpperCase()}`;
    }

    dom.dagNodesGrid.innerHTML = '';
    graph.nodes.forEach((node) => {
      const card = document.createElement('div');
      const stateClass = `state-${node.state.toLowerCase()}`;
      card.className = `dag-node-card ${stateClass}`;
      card.id = `node-${node.node_id}`;

      const durationStr = node.duration_seconds !== null ? `${node.duration_seconds.toFixed(2)}s` : '--';
      const depsHtml = (node.dependencies || []).map(d => `<span class="dep-chip">&larr; ${escapeHtml(d)}</span>`).join('');

      card.innerHTML = `
        <div class="dag-node-header">
          <span class="dag-node-id">STAGE ${escapeHtml(node.stage_id)}</span>
          <span class="badge ${getNodeBadgeClass(node.state)}">${escapeHtml(node.state)}</span>
        </div>
        <div class="dag-node-name">${escapeHtml(node.title)}</div>
        <div class="dag-node-agent">Agent: <strong>${escapeHtml(node.assigned_agent || 'Unassigned')}</strong></div>
        ${node.error ? `<div class="code-val text-rose" style="font-size:11px; margin-top:4px;">${escapeHtml(node.error)}</div>` : ''}
        <div class="dag-node-header" style="margin-top:6px;">
          <span class="diff-file-label" style="font-size:10px;">DURATION: ${durationStr}</span>
        </div>
        ${depsHtml ? `<div class="dag-node-deps">${depsHtml}</div>` : ''}
      `;

      card.addEventListener('click', () => showNodeDetail(node));
      dom.dagNodesGrid.appendChild(card);
    });
  }

  function getNodeBadgeClass(state) {
    switch (state) {
      case 'RUNNING': return 'badge-cyan pulsing-cyan';
      case 'WAITING_APPROVAL': return 'badge-amber pulsing-amber';
      case 'COMPLETED': return 'badge-purple';
      case 'VERIFIED': return 'badge-emerald';
      case 'FAILED': return 'badge-rose';
      case 'RECOVERING': return 'badge-amber';
      case 'READY': return 'badge-cyan';
      case 'CANCELLED': return 'badge-rose';
      default: return 'badge-idle';
    }
  }

  function showNodeDetail(node) {
    if (!dom.dagNodeDetailPanel) return;
    dom.dagNodeDetailPanel.style.display = 'block';
    dom.dagDetailNodeTitle.textContent = `Node: ${node.title} (${node.node_id})`;

    const startTime = node.start_time ? formatTime(node.start_time) : '--';
    const endTime = node.end_time ? formatTime(node.end_time) : '--';
    const dur = node.duration_seconds !== null ? `${node.duration_seconds.toFixed(2)}s` : '--';

    dom.dagDetailMetaGrid.innerHTML = `
      <div><strong>State:</strong> <span class="badge ${getNodeBadgeClass(node.state)}">${node.state}</span></div>
      <div><strong>Assigned Agent:</strong> ${escapeHtml(node.assigned_agent || 'None')}</div>
      <div><strong>Duration:</strong> ${dur}</div>
      <div><strong>Started:</strong> ${startTime}</div>
      <div><strong>Ended:</strong> ${endTime}</div>
      <div><strong>Dependencies:</strong> ${(node.dependencies || []).join(', ') || 'Root'}</div>
      ${node.error ? `<div style="grid-column: 1 / -1;"><strong>Error:</strong> <span class="text-rose">${escapeHtml(node.error)}</span></div>` : ''}
    `;
  }

  // -------------------------------------------------------------
  // Workforce Observatory Renderer
  // -------------------------------------------------------------
  function renderWorkforceRoster(roster) {
    if (!roster || !roster.agents || !dom.workforceCardsGrid) return;

    if (dom.workforceTotalBadge) {
      dom.workforceTotalBadge.textContent = `${roster.total_agents} Autonomous Agents`;
    }
    if (dom.tabCounterAgents) {
      dom.tabCounterAgents.textContent = roster.total_agents;
    }
    if (dom.workforceActiveBadge) {
      dom.workforceActiveBadge.textContent = `${roster.active_agents} Active`;
    }

    dom.workforceCardsGrid.innerHTML = '';
    roster.agents.forEach((ag) => {
      const card = document.createElement('div');
      card.className = 'agent-roster-card';
      card.id = `roster-${ag.agent_id}`;

      const avatarClass = getAgentAvatarClass(ag.role);
      const avatarLetters = ag.role.slice(0, 2).toUpperCase();
      const isActive = ag.status === 'ACTIVE' || ag.status === 'RECOVERING';
      const statusBadgeClass = isActive ? 'badge-active' : 'badge-idle';

      const capsHtml = (ag.capabilities || []).map(c => `<span class="cap-pill">${escapeHtml(c)}</span>`).join('');
      const permsHtml = (ag.permissions || []).map(p => `<span class="perm-pill">${escapeHtml(p)}</span>`).join('');

      card.innerHTML = `
        <div class="agent-roster-header">
          <div class="agent-roster-id-block">
            <div class="agent-roster-avatar ${avatarClass}">${avatarLetters}</div>
            <div>
              <div class="agent-roster-name">${escapeHtml(ag.name)}</div>
              <div class="agent-roster-role">${escapeHtml(ag.role)} &bull; ${escapeHtml(ag.agent_id)}</div>
            </div>
          </div>
          <span class="agent-state-badge ${statusBadgeClass}">${escapeHtml(ag.status)}</span>
        </div>

        <div class="agent-current-task">
          <div class="agent-task-label">CURRENT WORK OBJECTIVE</div>
          <div>${escapeHtml(ag.current_task || 'Awaiting assignment')}</div>
          ${ag.current_stage ? `<div style="margin-top:4px; font-size:11px; color:var(--accent-cyan);">Active Stage: ${escapeHtml(ag.current_stage)}</div>` : ''}
        </div>

        <div class="agent-caps-section">
          <div class="caps-label">Specialist Capabilities</div>
          <div class="caps-tags-row">${capsHtml || '<span class="text-dim">Standard execution</span>'}</div>
        </div>

        <div class="agent-caps-section">
          <div class="caps-label">Permission Boundaries</div>
          <div class="caps-tags-row">${permsHtml || '<span class="text-dim">Guarded read-only</span>'}</div>
        </div>
      `;
      dom.workforceCardsGrid.appendChild(card);
    });
  }

  function getAgentAvatarClass(role) {
    if (role.includes('SWE') || role.includes('ENGINEER')) return 'avatar-cyan';
    if (role.includes('DIAG') || role.includes('DIAGNOSTICS')) return 'avatar-purple';
    if (role.includes('VERIF') || role.includes('VERIFIER')) return 'avatar-emerald';
    if (role.includes('RECOV') || role.includes('RECOVERY')) return 'avatar-amber';
    return 'avatar-cyan';
  }

  function handleCopyDiffClick() {
    const text = dom.diffCodeBlock.innerText;
    navigator.clipboard.writeText(text).then(() => {
      dom.btnCopyDiff.textContent = 'Copied!';
      setTimeout(() => { dom.btnCopyDiff.textContent = 'Copy Diff'; }, 2000);
    });
  }

  function startFallbackPolling() {
    if (pollFallbackInterval) clearInterval(pollFallbackInterval);
    pollFallbackInterval = setInterval(async () => {
      await syncHealth();
      if (currentTaskId && (!eventSource || eventSource.readyState === EventSource.CLOSED)) {
        await refreshTaskData(currentTaskId);
      }
    }, 4000);
  }

  function formatTime(isoStr) {
    if (!isoStr) return '--:--:--';
    try {
      const d = new Date(isoStr);
      return d.toTimeString().split(' ')[0];
    } catch {
      return isoStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // =============================================================
  // V10 FLAGSHIP OBSERVATORIES HANDLERS & LOGIC
  // =============================================================

  // -------------------------------------------------------------
  // Screen 4: Repository Intelligence
  // -------------------------------------------------------------
  async function loadRepoData() {
    try {
      const res = await fetch('/api/v1/repo/index');
      if (res.ok) {
        const data = await res.json();
        if (dom.repoTotalFilesBadge) dom.repoTotalFilesBadge.textContent = `FILES: ${data.total_files || data.file_count || Object.keys(data.files || {}).length || 0}`;
        if (dom.repoTotalSymbolsBadge) dom.repoTotalSymbolsBadge.textContent = `SYMBOLS: ${data.total_symbols || data.symbol_count || 0}`;
        if (dom.repoIndexStatusBadge) dom.repoIndexStatusBadge.textContent = 'GRAPH: INDEXED';
      }
    } catch (e) {
      console.warn('Failed to load repo index:', e);
    }
  }

  async function handleAnalyzeImpact() {
    const targetFile = (dom.repoImpactTargetFile ? dom.repoImpactTargetFile.value.trim() : '') || 'src/orion/api/service.py';
    try {
      const res = await fetch('/api/v1/repo/impact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_file: targetFile }),
      });
      if (res.ok) {
        const report = await res.json();
        if (dom.repoDirectDependentsCount) dom.repoDirectDependentsCount.textContent = (report.direct_dependents || []).length;
        if (dom.repoTransitiveDependentsCount) dom.repoTransitiveDependentsCount.textContent = (report.transitive_dependents || []).length;
        if (dom.repoBlastRadiusScore) dom.repoBlastRadiusScore.textContent = (report.blast_radius_score !== undefined ? report.blast_radius_score.toFixed(2) : '0.00');
        if (dom.repoImpactedPathsList) {
          const list = (report.transitive_dependents || []).map(p => `<div>&bull; ${escapeHtml(p)}</div>`).join('');
          dom.repoImpactedPathsList.innerHTML = list || '<span class="text-emerald">No transitive dependents affected. Low blast radius.</span>';
        }
      }
    } catch (err) {
      console.error('Impact analysis error:', err);
    }
  }

  async function handleAnalyzeContext() {
    const targetFile = (dom.repoContextTargetFile ? dom.repoContextTargetFile.value.trim() : '') || 'src/orion/core/tools/executor.py';
    try {
      const res = await fetch('/api/v1/repo/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_file: targetFile, max_tokens: 4000 }),
      });
      if (res.ok) {
        const ctx = await res.json();
        const files = ctx.included_files || [];
        if (dom.repoContextFilesCount) dom.repoContextFilesCount.textContent = files.length;
        if (dom.repoContextTokensCount) dom.repoContextTokensCount.textContent = ctx.total_tokens || ctx.estimated_tokens || 0;
        if (dom.repoContextSnippets) {
          const items = files.map(f => `<div><strong>${escapeHtml(f.file_path || f)}</strong> (${f.token_count || '--'} tokens)</div>`).join('');
          dom.repoContextSnippets.innerHTML = items || '<span class="text-dim">No neighborhood files included.</span>';
        }
      }
    } catch (err) {
      console.error('Context analysis error:', err);
    }
  }

  // -------------------------------------------------------------
  // Screen 8: Human Oversight (HITL)
  // -------------------------------------------------------------
  function handleQuickSteerPrompt() {
    const directive = prompt('Enter steering guidance or architectural constraints for ORION:');
    if (directive && directive.trim()) {
      handleIntervention('steer', 'Manual steering guidance', directive.trim());
    }
  }

  async function handleIntervention(action, reason, payload) {
    if (!currentTaskId) {
      showToast('No Active Mission', 'Please create or select an active mission first.', 'warning');
      return;
    }
    try {
      const res = await fetch('/api/v1/hitl/intervene', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mission_id: currentTaskId,
          action: action,
          operator: (dom.hitlInterveneOperator ? dom.hitlInterveneOperator.value.trim() : 'Operator') || 'Operator',
          reason: reason || 'Operator directive',
          payload: payload ? { directive: payload } : null,
        }),
      });
      if (res.ok) {
        showToast('Intervention Executed', `Directive applied: ${action}`, 'info');
        await refreshTaskData(currentTaskId);
        await loadHitlData(currentTaskId);
      }
    } catch (err) {
      console.error('Intervention error:', err);
    }
  }

  async function handleFeedbackSubmit(e) {
    e.preventDefault();
    if (!currentTaskId) {
      showToast('No Active Mission', 'Please create or select an active mission before submitting feedback.', 'warning');
      return;
    }
    try {
      const res = await fetch('/api/v1/hitl/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mission_id: currentTaskId,
          operator: (dom.hitlInterveneOperator ? dom.hitlInterveneOperator.value.trim() : 'LeadReviewer') || 'LeadReviewer',
          rating: parseInt(dom.hitlFeedbackRating ? dom.hitlFeedbackRating.value : '5', 10),
          comments: dom.hitlFeedbackComments ? dom.hitlFeedbackComments.value.trim() : '',
          corrections: dom.hitlFeedbackCorrections && dom.hitlFeedbackCorrections.value.trim() ? dom.hitlFeedbackCorrections.value.split(',').map(s => s.trim()) : [],
        }),
      });
      if (res.ok) {
        showToast('Feedback Certified', 'Operator review and feedback successfully certified.', 'success');
        await loadHitlData(currentTaskId);
      }
    } catch (err) {
      console.error('Feedback submit error:', err);
    }
  }

  async function loadHitlData(missionId) {
    try {
      const url = missionId ? `/api/v1/hitl/clarifications?mission_id=${missionId}` : '/api/v1/hitl/clarifications';
      const res = await fetch(url);
      if (res.ok) {
        const clarifications = await res.json();
        renderClarifications(clarifications);
      }

      if (missionId) {
        const intRes = await fetch(`/api/v1/hitl/interventions/${missionId}`);
        if (intRes.ok) {
          const intervs = await intRes.json();
          renderHitlHistory(intervs);
        }
      }
    } catch (e) {
      console.warn('Failed to load HITL data:', e);
    }
  }

  function renderClarifications(clarifications) {
    if (!dom.hitlClarificationsList) return;
    const list = Array.isArray(clarifications) ? clarifications : (clarifications.clarifications || []);
    if (dom.hitlPendingCountBadge) {
      dom.hitlPendingCountBadge.textContent = `${list.filter(c => c.status === 'PENDING').length} Pending Clarifications`;
    }

    if (list.length === 0) {
      dom.hitlClarificationsList.innerHTML = '<div class="empty-state">No pending clarification requests. Autonomous execution unblocked.</div>';
      return;
    }

    dom.hitlClarificationsList.innerHTML = '';
    list.forEach(c => {
      const item = document.createElement('div');
      item.className = 'clarification-item';
      const isPending = c.status === 'PENDING';
      const chips = (c.options || []).map(opt => `<button type="button" class="clarification-chip" data-choice="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`).join('');

      item.innerHTML = `
        <div class="clarification-question">${escapeHtml(c.question)}</div>
        <div class="clarification-context">${escapeHtml(c.context || '')}</div>
        ${chips ? `<div class="clarification-chips">${chips}</div>` : ''}
        ${isPending ? `
          <div class="form-group-inline" style="margin-top:6px;">
            <input type="text" class="input-field clarif-input" placeholder="Type resolution or click choice chip above" style="font-size:12px; padding:4px 8px;">
            <button type="button" class="btn btn-amber btn-xs btn-respond-clarif" data-id="${c.request_id}">Resolve</button>
          </div>
        ` : `<div class="badge badge-emerald" style="align-self:flex-start;">RESOLVED: ${escapeHtml(c.response || '')}</div>`}
      `;

      item.querySelectorAll('.clarification-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const input = item.querySelector('.clarif-input');
          if (input) input.value = btn.dataset.choice;
        });
      });

      const submitBtn = item.querySelector('.btn-respond-clarif');
      if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
          const input = item.querySelector('.clarif-input');
          const respText = input ? input.value.trim() : '';
          if (!respText) return;
          await respondClarification(c.request_id, respText);
        });
      }

      dom.hitlClarificationsList.appendChild(item);
    });
  }

  async function respondClarification(reqId, responseText) {
    try {
      const res = await fetch(`/api/v1/hitl/clarifications/${reqId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response_text: responseText, operator: 'Operator' }),
      });
      if (res.ok) {
        if (currentTaskId) await loadHitlData(currentTaskId);
      }
    } catch (e) {
      console.error('Clarification response error:', e);
    }
  }

  function renderHitlHistory(interventions) {
    if (!dom.hitlHistoryList) return;
    const list = Array.isArray(interventions) ? interventions : (interventions.interventions || []);
    if (list.length === 0) {
      dom.hitlHistoryList.innerHTML = '<div class="empty-state">No manual interventions recorded for active mission.</div>';
      return;
    }
    dom.hitlHistoryList.innerHTML = '';
    list.forEach(i => {
      const item = document.createElement('div');
      item.className = 'hitl-history-item';
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
          <strong class="text-cyan">${escapeHtml((i.intervention_type || '').toUpperCase())}</strong>
          <span class="text-dim" style="font-size:10px;">${formatTime(i.timestamp)}</span>
        </div>
        <div style="font-size:11.5px; color:var(--text-main);">${escapeHtml(i.reason || '')}</div>
        <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">Operator: ${escapeHtml(i.operator || 'Unknown')}</div>
      `;
      dom.hitlHistoryList.appendChild(item);
    });
  }

  // -------------------------------------------------------------
  // Screen 9: Policy & Security
  // -------------------------------------------------------------
  async function loadPolicyData() {
    try {
      const [rulesRes, decRes] = await Promise.all([
        fetch('/api/v1/policy/rules'),
        fetch('/api/v1/policy/decisions?limit=25'),
      ]);

      if (rulesRes.ok) {
        const rules = await rulesRes.json();
        renderPolicyRules(rules.rules || rules);
      }

      if (decRes.ok) {
        const decData = await decRes.json();
        renderPolicyDecisions(decData.decisions || []);
      }
    } catch (e) {
      console.warn('Failed to load policy data:', e);
    }
  }

  function renderPolicyRules(rules) {
    if (!dom.policyRulesList) return;
    const list = Array.isArray(rules) ? rules : [];
    if (dom.policyRulesCountBadge) {
      dom.policyRulesCountBadge.textContent = `${list.length} Guardrails Active`;
    }
    dom.policyRulesList.innerHTML = '';
    list.forEach(r => {
      const row = document.createElement('tr');
      const effectClass = r.effect === 'ALLOW' ? 'badge-emerald' : (r.effect === 'DENY' ? 'badge-rose' : 'badge-amber');
      const patterns = [...(r.actions || []), ...(r.resource_patterns || [])].join(', ');
      row.innerHTML = `
        <td class="code-val"><strong>${escapeHtml(r.rule_id)}</strong></td>
        <td>${escapeHtml(r.name)}</td>
        <td><span class="badge ${effectClass}">${escapeHtml(r.effect)}</span></td>
        <td>${r.priority}</td>
        <td class="text-dim" style="font-size:11px;">${escapeHtml(patterns || 'All')}</td>
      `;
      dom.policyRulesList.appendChild(row);
    });
  }

  function renderPolicyDecisions(decisions) {
    if (!dom.policyDecisionsList) return;
    if (decisions.length === 0) {
      dom.policyDecisionsList.innerHTML = '<div class="empty-state">No policy evaluation events recorded yet.</div>';
      return;
    }
    dom.policyDecisionsList.innerHTML = '';
    decisions.slice(0, 20).forEach(d => {
      const item = document.createElement('div');
      item.className = 'policy-decision-row';
      const effectClass = d.decision === 'ALLOW' ? 'text-emerald' : (d.decision === 'DENY' ? 'text-rose' : 'text-amber');
      item.innerHTML = `
        <div>
          <span class="${effectClass}" style="font-weight:700;">${escapeHtml(d.decision)}</span>
          <span style="margin: 0 8px; color:var(--text-muted);">&bull;</span>
          <span>${escapeHtml(d.action || '')} &rarr; <span class="text-cyan">${escapeHtml(d.resource || '')}</span></span>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="badge badge-outline" style="font-size:9.5px;">${escapeHtml(d.risk_tier || 'LOW')}</span>
          <span class="text-dim">${formatTime(d.timestamp)}</span>
        </div>
      `;
      dom.policyDecisionsList.appendChild(item);
    });
  }

  async function handlePolicySimulate(e) {
    e.preventDefault();
    if (!dom.policySimResult) return;
    try {
      const res = await fetch('/api/v1/policy/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject: dom.policySimSubject.value.trim(),
          action: dom.policySimAction.value.trim(),
          resource: dom.policySimResource.value.trim(),
          risk_tier: dom.policySimRisk.value,
        }),
      });
      if (res.ok) {
        const dec = await res.json();
        dom.policySimResult.style.display = 'block';
        const effBadge = dec.decision === 'ALLOW' ? 'badge-emerald' : (dec.decision === 'DENY' ? 'badge-rose' : 'badge-amber');
        dom.policySimResult.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span>EVALUATION RESULT:</span>
            <span class="badge ${effBadge}">${escapeHtml(dec.decision)}</span>
          </div>
          <div><strong>Triggered Rule:</strong> ${escapeHtml(dec.rule_id || 'DEFAULT_DENY')}</div>
          <div><strong>Rationale:</strong> ${escapeHtml(dec.reason || 'Standard policy evaluation')}</div>
        `;
        await loadPolicyData();
      }
    } catch (err) {
      console.error('Policy evaluation simulator error:', err);
    }
  }

  // -------------------------------------------------------------
  // Screen 10: Evaluation Lab
  // -------------------------------------------------------------
  async function loadEvalData() {
    try {
      const [benchRes, runsRes] = await Promise.all([
        fetch('/api/v1/evaluation/benchmarks'),
        fetch('/api/v1/evaluation/runs'),
      ]);

      if (benchRes.ok) {
        const benchData = await benchRes.json();
        if (dom.evalSuiteSelect && benchData.suites) {
          dom.evalSuiteSelect.innerHTML = benchData.suites.map(s => `<option value="${escapeHtml(s.name || s)}">${escapeHtml(s.name || s)}</option>`).join('');
        }
      }

      if (runsRes.ok) {
        const runs = await runsRes.json();
        renderEvalRuns(runs.runs || runs);
      }
    } catch (e) {
      console.warn('Failed to load eval data:', e);
    }
  }

  function renderEvalRuns(runs) {
    if (!dom.evalRunsList) return;
    const list = Array.isArray(runs) ? runs : [];
    if (dom.evalRunsList) {
      if (list.length === 0) {
        dom.evalRunsList.innerHTML = '<tr><td colspan="8" class="text-dim" style="text-align:center; padding:16px;">No recorded benchmark runs. Execute suite above to run experiments.</td></tr>';
      } else {
        dom.evalRunsList.innerHTML = '';
        list.forEach(r => {
          const m = r.metrics || {};
          const row = document.createElement('tr');
          const succRate = m.mission_success_rate !== undefined ? `${(m.mission_success_rate * 100).toFixed(1)}%` : '--';
          const recRate = m.recovery_success_rate !== undefined ? `${(m.recovery_success_rate * 100).toFixed(1)}%` : '--';
          const safeRate = m.safe_termination_rate !== undefined ? `${(m.safe_termination_rate * 100).toFixed(1)}%` : '--';
          const p90 = m.latency_p90_seconds !== undefined ? `${m.latency_p90_seconds.toFixed(2)}s` : '--';
          const cost = m.total_cost_usd !== undefined ? `$${m.total_cost_usd.toFixed(4)}` : '$0.0000';

          row.innerHTML = `
            <td class="code-val">${escapeHtml(String(r.experiment_id || '').slice(0, 8))}</td>
            <td><span class="badge badge-outline">${escapeHtml(r.suite || 'standard')}</span></td>
            <td>${escapeHtml(r.orion_version || '10.0.0')}</td>
            <td class="text-emerald" style="font-weight:600;">${succRate}</td>
            <td class="text-cyan">${recRate}</td>
            <td class="text-purple">${safeRate}</td>
            <td class="text-dim">${p90}</td>
            <td class="text-emerald">${cost}</td>
          `;
          dom.evalRunsList.appendChild(row);
        });
      }
    }

    // Populate comparison dropdowns
    if (dom.evalCompareBaseSelect && dom.evalCompareTargetSelect) {
      const opts = list.map(r => `<option value="${r.experiment_id}">${escapeHtml(r.suite || 'suite')} [${String(r.experiment_id).slice(0, 8)}] (${r.orion_version || 'v10'})</option>`).join('');
      dom.evalCompareBaseSelect.innerHTML = opts || '<option value="">No experiments</option>';
      dom.evalCompareTargetSelect.innerHTML = opts || '<option value="">No experiments</option>';
      if (list.length > 1) {
        dom.evalCompareTargetSelect.selectedIndex = 1;
      }
    }
  }

  async function handleEvalRunSubmit(e) {
    e.preventDefault();
    if (!dom.btnRunEvaluation) return;
    dom.btnRunEvaluation.disabled = true;
    dom.btnRunEvaluation.textContent = 'Running Benchmark...';
    try {
      const res = await fetch('/api/v1/evaluation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          suite_name: dom.evalSuiteSelect ? dom.evalSuiteSelect.value : 'standard',
          orion_version: (dom.evalVersionTag ? dom.evalVersionTag.value.trim() : '10.0.0-rc1') || '10.0.0-rc1',
          auto_repair: true,
        }),
      });
      if (res.ok) {
        await loadEvalData();
      }
    } catch (err) {
      console.error('Benchmark run error:', err);
    } finally {
      dom.btnRunEvaluation.disabled = false;
      dom.btnRunEvaluation.textContent = 'Execute Benchmark Suite';
    }
  }

  async function handleEvalCompareClick() {
    if (!dom.evalCompareBaseSelect || !dom.evalCompareTargetSelect || !dom.evalCompareResults) return;
    const baseId = dom.evalCompareBaseSelect.value;
    const targetId = dom.evalCompareTargetSelect.value;
    if (!baseId || !targetId) return;

    try {
      const res = await fetch('/api/v1/evaluation/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_id: baseId, target_id: targetId }),
      });
      if (res.ok) {
        const comp = await res.json();
        dom.evalCompareResults.style.display = 'block';
        const dSucc = comp.delta_success_rate !== undefined ? `${comp.delta_success_rate > 0 ? '+' : ''}${(comp.delta_success_rate * 100).toFixed(1)}%` : '--';
        const dPass = comp.delta_pass_rate !== undefined ? `${comp.delta_pass_rate > 0 ? '+' : ''}${(comp.delta_pass_rate * 100).toFixed(1)}%` : '--';
        const dLatency = comp.delta_latency_p90 !== undefined ? `${comp.delta_latency_p90 > 0 ? '+' : ''}${comp.delta_latency_p90.toFixed(2)}s` : '--';
        const regrCount = (comp.regressed_benchmarks || []).length;

        dom.evalCompareResults.innerHTML = `
          <div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
            <div>&Delta; Success Rate: <strong class="${comp.delta_success_rate >= 0 ? 'text-emerald' : 'text-rose'}">${dSucc}</strong></div>
            <div>&Delta; Pass@1: <strong class="${comp.delta_pass_rate >= 0 ? 'text-emerald' : 'text-rose'}">${dPass}</strong></div>
            <div>&Delta; P90 Latency: <strong class="text-cyan">${dLatency}</strong></div>
            <div>Regressions: <strong class="${regrCount === 0 ? 'text-emerald' : 'text-rose'}">${regrCount} detected</strong></div>
          </div>
        `;
      }
    } catch (err) {
      console.error('Experiment comparison error:', err);
    }
  }

  // -------------------------------------------------------------
  // Screen 11: Observability
  // -------------------------------------------------------------
  async function loadObsData(missionId) {
    try {
      const [costRes, bottleRes, optRes] = await Promise.all([
        fetch(missionId ? `/api/v1/observability/metrics/cost?mission_id=${missionId}` : '/api/v1/observability/metrics/cost'),
        fetch(missionId ? `/api/v1/observability/bottlenecks?mission_id=${missionId}` : '/api/v1/observability/bottlenecks'),
        fetch(missionId ? `/api/v1/observability/optimize?mission_id=${missionId}` : '/api/v1/observability/optimize'),
      ]);

      if (costRes.ok) {
        const costData = await costRes.json();
        if (dom.obsPromptTokens) dom.obsPromptTokens.textContent = costData.prompt_tokens || 0;
        if (dom.obsCompletionTokens) dom.obsCompletionTokens.textContent = costData.completion_tokens || 0;
        if (dom.obsTotalCost) dom.obsTotalCost.textContent = `$${(costData.total_cost_usd || 0).toFixed(4)}`;
      }

      if (bottleRes.ok) {
        const bottleData = await bottleRes.json();
        if (dom.obsP50Val) dom.obsP50Val.textContent = `${(bottleData.p50_ms || 0).toFixed(1)} ms`;
        if (dom.obsP90Val) dom.obsP90Val.textContent = `${(bottleData.p90_ms || 0).toFixed(1)} ms`;
        if (dom.obsP99Val) dom.obsP99Val.textContent = `${(bottleData.p99_ms || 0).toFixed(1)} ms`;
        renderBottlenecks(bottleData.slowest_spans || []);
      }

      if (optRes.ok) {
        const optData = await optRes.json();
        renderRecommendations(Array.isArray(optData) ? optData : (optData.recommendations || []));
      }

      if (missionId) {
        const spansRes = await fetch(`/api/v1/observability/spans/${missionId}`);
        if (spansRes.ok) {
          const spansData = await spansRes.json();
          renderTraceWaterfall(spansData.spans || []);
        }
      }
    } catch (e) {
      console.warn('Failed to load observability data:', e);
    }
  }

  function renderTraceWaterfall(spans) {
    if (!dom.obsTraceWaterfall) return;
    if (dom.obsTotalSpansBadge) dom.obsTotalSpansBadge.textContent = `${spans.length} Spans`;
    if (spans.length === 0) {
      dom.obsTraceWaterfall.innerHTML = '<div class="empty-state">No execution trace spans recorded for current mission. Execute pipeline to view waterfall.</div>';
      return;
    }

    const maxDuration = Math.max(...spans.map(s => s.duration_ms || 1), 10);
    dom.obsTraceWaterfall.innerHTML = '';
    spans.forEach(s => {
      const row = document.createElement('div');
      row.className = 'waterfall-row';
      const pct = Math.max(4, Math.min(100, Math.round(((s.duration_ms || 1) / maxDuration) * 100)));
      const isErr = s.status === 'error';
      const barClass = isErr ? 'error' : 'ok';

      row.innerHTML = `
        <div class="waterfall-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
        <div class="waterfall-track">
          <div class="waterfall-bar ${barClass}" style="width: ${pct}%;"></div>
        </div>
        <div class="waterfall-meta">
          <span style="font-weight:600;">${(s.duration_ms || 0).toFixed(1)}ms</span>
          <span class="badge ${isErr ? 'badge-rose' : 'badge-outline'}" style="font-size:8.5px; padding:1px 4px; margin-left:4px;">${escapeHtml(s.kind || 'internal')}</span>
        </div>
      `;
      dom.obsTraceWaterfall.appendChild(row);
    });
  }

  function renderBottlenecks(bottlenecks) {
    if (!dom.obsBottlenecksList) return;
    if (bottlenecks.length === 0) {
      dom.obsBottlenecksList.innerHTML = '<div class="empty-state">No execution bottlenecks detected.</div>';
      return;
    }
    dom.obsBottlenecksList.innerHTML = '';
    bottlenecks.slice(0, 5).forEach(b => {
      const item = document.createElement('div');
      item.className = 'bottleneck-item';
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
          <strong class="text-amber">${escapeHtml(b.name || 'Span')}</strong>
          <span class="code-val">${(b.duration_ms || 0).toFixed(1)}ms</span>
        </div>
        <div class="text-dim" style="font-size:11px;">Status: ${escapeHtml(b.status || 'ok')} &bull; Kind: ${escapeHtml(b.kind || 'internal')}</div>
      `;
      dom.obsBottlenecksList.appendChild(item);
    });
  }

  function renderRecommendations(recs) {
    if (!dom.obsRecommendationsList) return;
    if (recs.length === 0) {
      dom.obsRecommendationsList.innerHTML = '<div class="empty-state">No performance recommendations needed. Pipeline operating at optimal latency.</div>';
      return;
    }
    dom.obsRecommendationsList.innerHTML = '';
    recs.forEach(r => {
      const item = document.createElement('div');
      item.className = 'recommendation-item';
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
          <strong class="text-emerald">${escapeHtml(r.title || 'Optimization Insight')}</strong>
          <span class="badge badge-outline">${escapeHtml(r.category || 'PERF')}</span>
        </div>
        <div style="font-size:11.5px; color:var(--text-muted);">${escapeHtml(r.description || r.rationale || '')}</div>
      `;
      dom.obsRecommendationsList.appendChild(item);
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();

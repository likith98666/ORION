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
  };

  // -------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------
  async function init() {
    bindEvents();
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
  }

  function switchTab(tabId) {
    dom.commandTabBar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    const panel = document.getElementById(tabId);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');

    // Trigger tab-specific refresh
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
    } else if (evName === 'PATCH_APPROVED' || evName === 'PATCH_DENIED') {
      hideApprovalAlert();
      closeApprovalModal();
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
        alert(`Approval action failed: ${err.error}`);
        return;
      }

      hideApprovalAlert();
      closeApprovalModal();
      await refreshTaskData(currentTaskId);
    } catch (err) {
      alert(`Network error submitting approval: ${err}`);
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
      dom.engineUptime.textContent = `${data.uptime_seconds}s`;
      dom.activeMissionsCount.textContent = data.missions_count;
      dom.coreStatusText.textContent = 'DETERMINISTIC // ONLINE';
      dom.coreStatusDot.className = 'status-dot online';
    } catch (err) {
      dom.coreStatusText.textContent = 'STANDALONE // OFFLINE';
      dom.coreStatusDot.className = 'status-dot pulsing-amber';
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
    return lines.map(line => {
      const escaped = escapeHtml(line);
      if (line.startsWith('+') && !line.startsWith('+++')) {
        return `<span class="diff-line-add">${escaped}</span>`;
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        return `<span class="diff-line-del">${escaped}</span>`;
      } else if (line.startsWith('@@')) {
        return `<span class="diff-line-info">${escaped}</span>`;
      }
      return `<span>${escaped}</span>`;
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
    if (events.length === 0) {
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
      alert('Please provide both task directive and workspace root.');
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
        alert(`Failed to launch task: ${err.error}`);
        return;
      }

      const created = await res.json();
      currentTaskId = created.task_id || created.mission_id;
      connectEventStream(currentTaskId);
      await refreshTaskData(currentTaskId);

      // Trigger execution pipeline immediately
      await fetch(`/api/tasks/${currentTaskId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: execution_mode === 'autonomous', background: true }),
      });
    } catch (err) {
      alert(`Network error submitting task: ${err}`);
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
        alert(`Error: ${err.error}`);
        return;
      }

      const created = await res.json();
      currentTaskId = created.task_id || created.mission_id;
      dom.modalBackdrop.classList.remove('open');
      connectEventStream(currentTaskId);
      await refreshTaskData(currentTaskId);
    } catch (err) {
      alert(`Error creating task: ${err}`);
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
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        alert(`Cannot run pipeline: ${err.error}`);
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
        alert('All stages already completed!');
        return;
      }

      const nextStage = STAGES[nextIdx];
      const res = await fetch(`/api/v1/missions/${currentTaskId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: nextStage }),
      });

      if (res.ok) {
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        alert(`Cannot advance stage: ${err.error}`);
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
      } else {
        const err = await res.json();
        alert(`Cannot generate report: ${err.error}`);
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
        await refreshTaskData(currentTaskId);
      } else {
        const err = await res.json();
        alert(`Failed to cancel mission: ${err.error}`);
      }
    } catch (err) {
      alert(`Network error cancelling mission: ${err}`);
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
      alert('Please create or select an active mission first.');
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
      alert('Please create or select an active mission before submitting feedback.');
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
        alert('Operator review and feedback successfully certified.');
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

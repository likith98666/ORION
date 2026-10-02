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
  };

  // -------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------
  async function init() {
    bindEvents();
    await syncHealth();
    await loadInitialTasks();
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
    });

    dom.btnRunPipeline.addEventListener('click', handleRunPipelineClick);
    dom.btnAdvanceStage.addEventListener('click', handleAdvanceStageClick);
    dom.btnGenReportNow.addEventListener('click', handleGenerateReportClick);
    dom.btnCopyDiff.addEventListener('click', handleCopyDiffClick);
  }

  function switchTab(tabId) {
    dom.commandTabBar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    const panel = document.getElementById(tabId);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');
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
    };

    eventSource.onerror = function () {
      dom.sseStatusDot.className = 'status-dot pulsing-amber';
      dom.sseStatusText.textContent = 'RETRYING...';
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
      level: data.level || (evName.includes('FAIL') || evName.includes('DENIED') ? 'error' : (evName.includes('APPROVED') || evName.includes('COMPLETED') ? 'success' : 'info')),
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

  document.addEventListener('DOMContentLoaded', init);
})();

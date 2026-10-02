/**
 * ORION — Mission Command Center Client Application
 * Communicates with Orion REST API at /api/v1/
 */

(function () {
  'use strict';

  let currentMissionId = null;
  let pollInterval = null;
  let currentEvidenceFilter = 'all';
  let cachedEvidence = [];

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
    engineStatusText: document.getElementById('engineStatusText'),
    engineUptime: document.getElementById('engineUptime'),
    activeMissionsCount: document.getElementById('activeMissionsCount'),
    btnRefresh: document.getElementById('btnRefresh'),
    btnNewMission: document.getElementById('btnNewMission'),
    missionIdBadge: document.getElementById('missionIdBadge'),
    missionStatusBadge: document.getElementById('missionStatusBadge'),
    missionWorkspaceBadge: document.getElementById('missionWorkspaceBadge'),
    missionObjective: document.getElementById('missionObjective'),
    stepperFill: document.getElementById('stepperFill'),
    btnRunDemo: document.getElementById('btnRunDemo'),
    btnAdvanceStage: document.getElementById('btnAdvanceStage'),
    agentList: document.getElementById('agentList'),
    metricTestsPassed: document.getElementById('metricTestsPassed'),
    metricTestsFailed: document.getElementById('metricTestsFailed'),
    metricVerifPassed: document.getElementById('metricVerifPassed'),
    metricRecoveryAttempts: document.getElementById('metricRecoveryAttempts'),
    metricEvidenceCount: document.getElementById('metricEvidenceCount'),
    timelineStream: document.getElementById('timelineStream'),
    commandTabBar: document.getElementById('commandTabBar'),
    ovMissionId: document.getElementById('ovMissionId'),
    ovTaskId: document.getElementById('ovTaskId'),
    ovWorkspaceRoot: document.getElementById('ovWorkspaceRoot'),
    ovCurrentStage: document.getElementById('ovCurrentStage'),
    ovStagesCompleted: document.getElementById('ovStagesCompleted'),
    evidenceFilterGroup: document.getElementById('evidenceFilterGroup'),
    evidenceFilteredCount: document.getElementById('evidenceFilteredCount'),
    evidenceFeed: document.getElementById('evidenceFeed'),
    verifStatusBox: document.getElementById('verifStatusBox'),
    verifIcon: document.getElementById('verifIcon'),
    verifHeading: document.getElementById('verifHeading'),
    verifReason: document.getElementById('verifReason'),
    verifCriteriaList: document.getElementById('verifCriteriaList'),
    recCountVal: document.getElementById('recCountVal'),
    recoveryEventsList: document.getElementById('recoveryEventsList'),
    modifiedFilesCount: document.getElementById('modifiedFilesCount'),
    diffViewer: document.getElementById('diffViewer'),
    reportContainer: document.getElementById('reportContainer'),
    reportEmptyState: document.getElementById('reportEmptyState'),
    reportContent: document.getElementById('reportContent'),
    btnGenReportNow: document.getElementById('btnGenReportNow'),
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
    await loadInitialMissions();
    startPolling();
  }

  function bindEvents() {
    // Navigation Tabs
    dom.commandTabBar.addEventListener('click', (e) => {
      if (e.target.classList.contains('tab-btn')) {
        switchTab(e.target.dataset.tab);
      }
    });

    // Evidence Filters
    dom.evidenceFilterGroup.addEventListener('click', (e) => {
      if (e.target.classList.contains('filter-btn')) {
        dom.evidenceFilterGroup.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        e.target.classList.add('active');
        currentEvidenceFilter = e.target.dataset.filter;
        renderEvidenceList();
      }
    });

    // Modals
    dom.btnNewMission.addEventListener('click', () => dom.modalBackdrop.classList.add('open'));
    dom.modalCloseBtn.addEventListener('click', () => dom.modalBackdrop.classList.remove('open'));
    dom.btnCancelModal.addEventListener('click', () => dom.modalBackdrop.classList.remove('open'));
    dom.createMissionForm.addEventListener('submit', handleCreateMissionSubmit);

    // Controls
    dom.btnRefresh.addEventListener('click', async () => {
      await syncHealth();
      if (currentMissionId) await refreshMissionData(currentMissionId);
    });

    dom.btnAdvanceStage.addEventListener('click', handleAdvanceStageClick);
    dom.btnRunDemo.addEventListener('click', handleRunPipelineDemo);
    dom.btnGenReportNow.addEventListener('click', handleGenerateReportClick);
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
  // API Calls
  // -------------------------------------------------------------
  async function syncHealth() {
    try {
      const res = await fetch('/api/v1/health');
      if (!res.ok) return;
      const data = await res.json();
      dom.engineUptime.textContent = `${data.uptime_seconds}s`;
      dom.activeMissionsCount.textContent = data.missions_count;
    } catch (err) {
      dom.engineStatusText.textContent = 'DETERMINISTIC // STANDALONE';
    }
  }

  async function loadInitialMissions() {
    try {
      const res = await fetch('/api/v1/missions');
      if (res.ok) {
        const data = await res.json();
        if (data.missions && data.missions.length > 0) {
          currentMissionId = data.missions[0].mission_id;
          await refreshMissionData(currentMissionId);
          return;
        }
      }
    } catch (err) {
      console.warn('API unavailable or empty missions list.');
    }

    // If no active mission, create sample mission for immediate demonstration
    await createDefaultSampleMission();
  }

  async function createDefaultSampleMission() {
    try {
      const res = await fetch('/api/v1/missions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          objective: 'Analyze and repair calculator bug with verified test execution',
          workspace_path: 'C:/Users/LIKITH/ORION',
          target_files: ['src/math_lib.py'],
        }),
      });
      if (res.ok) {
        const mission = await res.json();
        currentMissionId = mission.mission_id;
        await refreshMissionData(currentMissionId);
      }
    } catch (err) {
      console.error('Failed to create sample mission:', err);
    }
  }

  async function refreshMissionData(missionId) {
    try {
      const [mRes, tlRes, evRes, verRes, recRes, evlRes, repRes] = await Promise.all([
        fetch(`/api/v1/missions/${missionId}`),
        fetch(`/api/v1/missions/${missionId}/timeline`),
        fetch(`/api/v1/missions/${missionId}/evidence`),
        fetch(`/api/v1/missions/${missionId}/verification`),
        fetch(`/api/v1/missions/${missionId}/recovery`),
        fetch(`/api/v1/missions/${missionId}/evaluation`),
        fetch(`/api/v1/missions/${missionId}/report`),
      ]);

      if (mRes.ok) updateMissionOverview(await mRes.json());
      if (tlRes.ok) updateTimeline(await tlRes.json());
      if (evRes.ok) {
        const evData = await evRes.json();
        cachedEvidence = evData.evidence || [];
        renderEvidenceList();
      }
      if (verRes.ok) updateVerification(await verRes.json());
      if (recRes.ok) updateRecovery(await recRes.json());
      if (evlRes.ok) updateEvaluation(await evlRes.json());
      if (repRes.ok) updateReport(await repRes.json());
    } catch (err) {
      console.error('Error refreshing mission data:', err);
    }
  }

  // -------------------------------------------------------------
  // UI Renderers
  // -------------------------------------------------------------
  function updateMissionOverview(m) {
    dom.missionIdBadge.textContent = `ID: ${m.mission_id.slice(0, 8)}...`;
    dom.missionStatusBadge.textContent = m.status.toUpperCase();
    dom.missionObjective.textContent = m.objective;
    dom.missionWorkspaceBadge.textContent = `REPO: ${m.workspace_root.split(/[\\/]/).pop()}`;

    // Status Pill color
    if (m.status === 'verified_success') {
      dom.missionStatusBadge.className = 'badge badge-emerald';
    } else if (m.status === 'failed') {
      dom.missionStatusBadge.className = 'badge badge-rose';
    } else {
      dom.missionStatusBadge.className = 'badge badge-status';
    }

    dom.ovMissionId.textContent = m.mission_id;
    dom.ovTaskId.textContent = m.task_id;
    dom.ovWorkspaceRoot.textContent = m.workspace_root;
    dom.ovCurrentStage.innerHTML = `<span class="badge badge-accent">${(m.current_stage || 'none').toUpperCase()}</span>`;
    dom.ovStagesCompleted.textContent = `${m.stages_completed_count} / ${m.stages_total}`;

    // Stepper updates
    const currentIdx = m.current_stage ? STAGES.indexOf(m.current_stage) : -1;
    STAGES.forEach((stage, idx) => {
      const node = document.getElementById(`step-${stage}`);
      if (!node) return;
      node.classList.remove('active', 'completed');
      if (m.completed_stages.includes(stage)) {
        node.classList.add('completed');
      } else if (stage === m.current_stage) {
        node.classList.add('active');
      }
    });

    const pct = Math.max(14, Math.round(((m.stages_completed_count + (m.current_stage ? 1 : 0)) / STAGES.length) * 100));
    dom.stepperFill.style.width = `${pct}%`;

    // Metrics
    if (m.evidence_counts) {
      dom.metricEvidenceCount.textContent = `${m.evidence_counts.total || 0} Evidence`;
    }
  }

  function updateTimeline(data) {
    const list = data.timeline || [];
    if (list.length === 0) {
      dom.timelineStream.innerHTML = '<div class="timeline-empty">Waiting for execution stream...</div>';
      return;
    }

    dom.timelineStream.innerHTML = list.slice().reverse().map(e => `
      <div class="timeline-event-item">
        <div class="tl-header">
          <span class="tl-title">${escapeHtml(e.title)}</span>
          <span class="tl-time">${new Date(e.timestamp).toLocaleTimeString()}</span>
        </div>
        <div class="tl-detail">${escapeHtml(e.detail)}</div>
      </div>
    `).join('');
  }

  function renderEvidenceList() {
    let items = cachedEvidence;
    if (currentEvidenceFilter !== 'all') {
      items = items.filter(i => i.level.toLowerCase() === currentEvidenceFilter);
    }

    dom.evidenceFilteredCount.textContent = `Showing ${items.length} of ${cachedEvidence.length} entries`;

    if (items.length === 0) {
      dom.evidenceFeed.innerHTML = '<div class="empty-state">No matching evidence items found.</div>';
      return;
    }

    dom.evidenceFeed.innerHTML = items.map(i => `
      <div class="evidence-card">
        <div class="evidence-card-header">
          <div class="evidence-badges">
            <span class="badge ev-level-${i.level}">${i.level.toUpperCase()}</span>
            <span class="badge badge-purple">${i.category}</span>
            <span class="badge badge-workspace">${i.stage}</span>
          </div>
          <span class="ev-provenance">${new Date(i.timestamp).toLocaleTimeString()}</span>
        </div>
        <div class="ev-summary">${escapeHtml(i.summary || 'Evidence Entry')}</div>
        <div class="ev-content">${escapeHtml(i.content)}</div>
        <div class="ev-provenance">
          <span>Source: ${escapeHtml(i.source)}</span>
          ${i.tool_name ? `<span>Tool: ${escapeHtml(i.tool_name)}</span>` : ''}
          ${i.execution_id ? `<span>Exec: ${i.execution_id.slice(0, 8)}</span>` : ''}
        </div>
      </div>
    `).join('');
  }

  function updateVerification(v) {
    if (v.status === 'passed') {
      dom.verifStatusBox.className = 'verif-status-box passed';
      dom.verifIcon.textContent = '✓';
      dom.verifHeading.textContent = 'Verification PASSED (Authoritative)';
      dom.verifReason.textContent = v.reason;
    } else if (v.status === 'failed') {
      dom.verifStatusBox.className = 'verif-status-box';
      dom.verifStatusBox.style.borderColor = 'var(--accent-rose)';
      dom.verifIcon.textContent = '✕';
      dom.verifIcon.style.color = 'var(--accent-rose)';
      dom.verifHeading.textContent = 'Verification FAILED';
      dom.verifReason.textContent = v.reason;
    } else {
      dom.verifStatusBox.className = 'verif-status-box';
      dom.verifIcon.textContent = '?';
      dom.verifHeading.textContent = 'Verification Pending';
      dom.verifReason.textContent = 'Awaiting stage 6 verification execution.';
    }
  }

  function updateRecovery(r) {
    dom.recCountVal.textContent = r.recovery_attempts || 0;
    const events = r.recovery_events || [];

    if (events.length === 0) {
      dom.recoveryEventsList.innerHTML = '<div class="empty-state">No failure events occurred. Clean deterministic execution.</div>';
      return;
    }

    dom.recoveryEventsList.innerHTML = events.map(e => `
      <div class="recovery-event-card">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <strong class="text-amber">Recovery Event #${e.id.slice(0, 6)}</strong>
          <span class="code-val">${new Date(e.timestamp).toLocaleTimeString()}</span>
        </div>
        <div style="font-size:13px; color:#fff; margin-bottom:4px;">${escapeHtml(e.summary)}</div>
        <div style="font-size:11px; color:var(--text-muted);">
          <span>Strategy: <strong>${escapeHtml(e.strategy)}</strong></span> &bull; 
          <span>Action: <strong>${escapeHtml(e.action)}</strong></span> &bull; 
          <span>Type: <strong>${escapeHtml(e.failure_type)}</strong></span>
        </div>
      </div>
    `).join('');
  }

  function updateEvaluation(ev) {
    if (ev.metrics) {
      dom.metricTestsPassed.textContent = ev.metrics.tests_passed || 0;
      dom.metricTestsFailed.textContent = ev.metrics.tests_failed || 0;
      dom.metricVerifPassed.textContent = ev.metrics.verification_passed || 0;
      dom.metricRecoveryAttempts.textContent = ev.metrics.recovery_attempts || 0;
    }
  }

  function updateReport(rep) {
    if (!rep || !rep.mission) {
      dom.reportEmptyState.style.display = 'block';
      dom.reportContent.style.display = 'none';
      return;
    }

    dom.reportEmptyState.style.display = 'none';
    dom.reportContent.style.display = 'block';

    const isVerified = rep.final_outcome === 'verified_success';

    dom.reportContent.innerHTML = `
      <div class="report-certificate">
        <div class="cert-badge">${isVerified ? '✓' : '!'}</div>
        <div>
          <h3 style="color:${isVerified ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-size:18px;">
            ${isVerified ? 'CERTIFIED VERIFIED SUCCESS' : 'MISSION OUTCOME: ' + rep.final_outcome.toUpperCase()}
          </h3>
          <p style="color:var(--text-muted); font-size:13px;">${escapeHtml(rep.mission.summary || 'Certified SWE Execution Outcome')}</p>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:20px;">
        <div class="metric-box">
          <span class="metric-number text-cyan">${rep.evidence_summary.total_items}</span>
          <span class="metric-name">Total Evidence Items (Claimed: ${rep.evidence_summary.claimed_count}, Observed: ${rep.evidence_summary.observed_count}, Verified: ${rep.evidence_summary.verified_count})</span>
        </div>
        <div class="metric-box">
          <span class="metric-number text-emerald">${rep.changes.total_files_modified}</span>
          <span class="metric-name">Files Modified With Full Traceability</span>
        </div>
      </div>

      <h4 class="block-title">Deterministic Evaluation Criteria</h4>
      <div class="criteria-list">
        ${renderCritRow('Workflow Completed', rep.evaluation.criteria.workflow_completed)}
        ${renderCritRow('Validation Tests Passed', rep.evaluation.criteria.test_passed)}
        ${renderCritRow('VerificationEngine Passed', rep.evaluation.criteria.verification_passed)}
        ${renderCritRow('Evidence Audit Complete', rep.evaluation.criteria.evidence_complete)}
        ${renderCritRow('Changes Fully Traceable', rep.evaluation.criteria.changes_traceable)}
        ${renderCritRow('Recovery Audit Transparent', rep.evaluation.criteria.recovery_transparent)}
      </div>
    `;
  }

  function renderCritRow(label, passed) {
    return `
      <div class="criterion-item ${passed ? 'passed' : ''}">
        <span class="crit-icon">${passed ? '✓' : '✕'}</span>
        <span>${label}: <strong>${passed ? 'SATISFIED' : 'UNMET'}</strong></span>
      </div>
    `;
  }

  // -------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------
  async function handleCreateMissionSubmit(e) {
    e.preventDefault();
    const objective = document.getElementById('inputObjective').value;
    const workspace_path = document.getElementById('inputWorkspace').value;

    try {
      const res = await fetch('/api/v1/missions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective, workspace_path }),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Failed to create mission: ${err.error}`);
        return;
      }

      const created = await res.json();
      currentMissionId = created.mission_id;
      dom.modalBackdrop.classList.remove('open');
      await refreshMissionData(currentMissionId);
    } catch (err) {
      alert(`Network error creating mission: ${err}`);
    }
  }

  async function handleAdvanceStageClick() {
    if (!currentMissionId) return;

    try {
      const mRes = await fetch(`/api/v1/missions/${currentMissionId}`);
      if (!mRes.ok) return;
      const m = await mRes.json();

      const nextIdx = m.completed_stages.length;
      if (nextIdx >= STAGES.length) {
        alert('All stages already completed!');
        return;
      }

      const nextStage = STAGES[nextIdx];
      const res = await fetch(`/api/v1/missions/${currentMissionId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: nextStage }),
      });

      if (res.ok) {
        await refreshMissionData(currentMissionId);
      } else {
        const err = await res.json();
        alert(`Cannot advance stage: ${err.error}`);
      }
    } catch (err) {
      console.error('Advance stage failed:', err);
    }
  }

  async function handleGenerateReportClick() {
    if (!currentMissionId) return;
    try {
      const res = await fetch(`/api/v1/missions/${currentMissionId}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: 'Certified final mission report' }),
      });
      if (res.ok) {
        await refreshMissionData(currentMissionId);
        switchTab('tab-report');
      } else {
        const err = await res.json();
        alert(`Cannot generate report: ${err.error}`);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleRunPipelineDemo() {
    if (!currentMissionId) return;
    dom.btnRunDemo.disabled = true;
    dom.btnRunDemo.textContent = 'Executing Pipeline...';

    try {
      for (const stage of STAGES) {
        // Advance
        await fetch(`/api/v1/missions/${currentMissionId}/advance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage }),
        });
        await refreshMissionData(currentMissionId);
        await sleep(350);

        // Execute stage-appropriate tool if applicable
        if (stage === 'inspect_repository') {
          await fetch(`/api/v1/missions/${currentMissionId}/tool`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              stage: 'inspect_repository',
              tool_name: 'list_files',
              arguments: { path: '.' },
            }),
          });
        } else if (stage === 'generate_report') {
          await fetch(`/api/v1/missions/${currentMissionId}/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ summary: 'Pipeline automated execution verified' }),
          });
        }

        // Complete stage
        await fetch(`/api/v1/missions/${currentMissionId}/complete-stage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage }),
        });
        await refreshMissionData(currentMissionId);
        await sleep(350);
      }
    } catch (err) {
      console.error('Demo pipeline error:', err);
    } finally {
      dom.btnRunDemo.disabled = false;
      dom.btnRunDemo.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Execute Pipeline';
      switchTab('tab-report');
    }
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      await syncHealth();
      if (currentMissionId) await refreshMissionData(currentMissionId);
    }, 4000);
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

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Run on load
  document.addEventListener('DOMContentLoaded', init);
})();

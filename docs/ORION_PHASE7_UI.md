# ORION Phase 7: Mission Command Center UI Specification

## 1. Visual Design Philosophy

The ORION Mission Command Center rejects generic SaaS templates, excessive neon, and decorative animations. The aesthetic target is:

> **Cinematic AI Mission Control + Engineering IDE + Autonomous Workforce Observatory**

### Core Design Rules
1. **Factually Grounded**: No simulated progress bars, placeholder graphs, or artificial telemetry.
2. **Obsidian Dark Palette**: High-contrast, glare-free dark mode tailored for deep engineering sessions.
3. **Restrained Luminous Accents**:
   - `Cyan (#00F0FF)`: Active execution, telemetry streams, focus rings.
   - `Emerald (#10B981)`: Authoritative verification, test passes.
   - `Amber (#F59E0B)`: Approval gates, human intervention required.
   - `Rose (#F43F5E)`: Security violations, test failures, abort triggers.
   - `Violet (#8B5CF6)`: Autonomous workforce agents, AST operations.
4. **Engineering Typography**: Crisp monospaced data view (`JetBrains Mono`, `Fira Code`) paired with clean geometric headings (`Inter`, `system-ui`).
5. **Epistemic Clarity**: The distinction between `CLAIMED`, `OBSERVED`, and `VERIFIED` is visually stamped throughout the UI.

---

## 2. Layout & Component Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│ TOP BAR: Brand · Connection Health · Live Time · Active Workspace       │
├────────────────────────────────────────────────────────────────────────┤
│ MISSION INGESTION: Task Input Prompt · Execution Mode · [SUBMIT]       │
├────────────────────────────────────────────────────────────────────────┤
│ MISSION LIFECYCLE STEPPER (8 Stages with Live Status Badges)           │
│ [1. INGEST] ➔ [2. DIAGNOSE] ➔ [3. FIX] ➔ [4. APPROVE] ➔                │
│ [5. APPLY] ➔ [6. TEST] ➔ [7. VERIFY] ➔ [8. REPORT]                    │
├────────────────────────────────────────────────────────────────────────┤
│ MAIN OBSERVATORY TABS:                                                 │
│ [Workforce (4)] [Execution DAG] [Telemetry] [Changes] [Tests] [Verif]  │
├──────────────────────────────────┬─────────────────────────────────────┤
│ TAB CONTENT VIEWPORT             │ TELEMETRY / AUDIT SIDEBAR           │
│                                  │                                     │
│  - Workforce Agent Grid          │  - Real-time SSE stream log         │
│  - Interactive Topological DAG   │  - System resource metrics          │
│  - Dual-Key Approval Banner      │  - Epistemic evidence ledger        │
│  - Split-view Diff Viewer        │  - Failure & recovery budget meter  │
│  - Controlled Terminal Output    │                                     │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 3. Primary Observatories

### 3.1. Workforce Observatory
- Renders real-time cards for active agents:
  - **Orion-SWE-Engineer**
  - **Orion-Diagnostics-Specialist**
  - **Orion-Verification-Authority**
  - **Orion-Recovery-Specialist**
- Displays agent identity, active role, current task assignment, capability tags, completed task counters, and live status indicator chips (`IDLE`, `BUSY`, `WAITING_APPROVAL`, `COMPLETED`).

### 3.2. Execution Graph DAG
- Visualizes the 8-node workflow DAG using topological layout.
- Nodes reflect exact operational states:
  - `PENDING`: Muted gray border.
  - `READY`: Cyan pulse border.
  - `RUNNING`: High-glow cyan animation.
  - `WAITING_APPROVAL`: Flashing amber border.
  - `COMPLETED`: Solid emerald border.
  - `VERIFIED`: Double-bordered emerald badge.
  - `FAILED`: Solid rose border.
- Directional arrow connectors show strict prerequisite dependencies.

### 3.3. Dual-Key Approval Experience
- Activated when the backend enters `AWAITING_APPROVAL`.
- Highlights risk level and impacted files.
- Includes embedded unified diff viewer highlighting exact additions (`+`) and deletions (`-`).
- Features a secure dual-key authorization form:
  - Operator signature input (`LeadSecurityOfficer`).
  - Rationale textarea.
  - Distinct `[AUTHORIZE PATCH]` (emerald) and `[REJECT / ABORT]` (rose) action buttons.

### 3.4. Controlled Test & Verification Center
- Displays command executed under `ControlledExecutionAuthority` (e.g. `pytest tests/`).
- Real-time duration counter, exit status, and test counts (`passed`, `failed`, `skipped`).
- Verification panel displays criteria checklist evaluated by `VerificationEngine`.
- Certified Final Report viewer with JSON download and audit export capabilities.

### 3.5. Bounded Recovery Observatory
- Appears whenever an execution or test failure occurs.
- Displays:
  - Failure classification (AST error, assertion failure, syntax error).
  - Selected remediation strategy.
  - Circular progress gauges for **Remaining Recovery Attempts**, **Regeneration Budget**, and **Execution Time Budget**.
  - Historical timeline of all recovery attempts and outcomes.

---

## 4. Responsive Design & Accessibility

- **Responsive Viewports**:
  - Full desktop (1440px+): Side-by-side observatory and live telemetry.
  - Laptop (1024px - 1439px): Intelligently stacked views with tabbed sidebar.
  - Compact / Tablet (768px - 1023px): Collapsible drawer for telemetry, focused single-column observatory.
- **Accessibility & Human Factors**:
  - High WCAG AA contrast on all text elements against obsidian backgrounds.
  - Visible keyboard focus rings (`focus-visible: 2px solid #00F0FF`).
  - Full keyboard navigation for all tabs, modal inputs, and buttons.
  - Reduced-motion queries (`@media (prefers-reduced-motion: reduce)`) disabling pulse effects.
  - ARIA attributes on all interactive modals and status banners (`aria-live="polite"`).

---

## 5. Connection Loss & Reconnect Behavior

When real-time SSE drops (network hiccup or server restart):
1. A persistent `#connectionLostBanner` appears at the top of the interface.
2. The UI enters a graceful reconnect retry loop with exponential backoff.
3. A manual `[RECONNECT NOW]` button allows instant manual socket re-establishment.
4. Cached mission state remains readable; no blank screens or infinite loading spinners are shown.

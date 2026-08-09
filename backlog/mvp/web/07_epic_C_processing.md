# Epic C: Processing & Simulation

## Objective & User Value
Provide the primary execution interface for the simulation engine.
**User Value:** Replaces manual CLI executions (`run`, `grid`, `counterfactual`) with an intuitive, trackable UI. Users can launch massive grids of policies, monitor scenario generation, understand queue states, and quickly access outcomes and HTML reports.

## Capabilities & Scope
- Simulation run launch (single, grid, counterfactual).
- Policy selection and scenario configuration.
- Real-time execution monitoring (state machine tracking).
- Managing grid parallel execution.
- High-level results summary and KPI extraction.
- Run cancellation and re-execution.
- Seamless navigation to generated HTML reports.

---

## User Stories

### WC-001: Single Simulation Launcher
**Description:** As a simulation user, I want to configure and launch a single simulation run so that I can evaluate a specific policy.
**Acceptance Criteria:**
- **Functional:** Form allows selection of Config, Calibration artifact, specific Policy (R4-R14), and Master Seed.
- **UX:** Form uses semantic HTML, explicit labels, validation on blur.
- **Error Handling:** Explains clearly if a selected calibration is incompatible with the config.
**Dependencies:** WA-005, WB-004.
**UX/A11y/Responsive:** Persistent submit button, clear error states.
**Design System Components:** Form, Select, PrimaryButton.
**Technical/API:** Maps to `run` CLI command.

### WC-002: Scenario Generation Configuration
**Description:** As a simulation user, I want to configure CRN (Common Random Number) scenario generation so that I can control variance and sample size.
**Acceptance Criteria:**
- **Functional:** Toggle between generating new scenarios or reusing existing ones.
- **Functional:** Input for scenario count and base seed.
- **UX:** If reusing, provide a searchable dropdown of existing scenario parquet files.
**Dependencies:** WC-001.
**UX/A11y/Responsive:** Toggle uses standard accessible switch.
**Design System Components:** Switch, SearchableSelect, NumberInput.
**Technical/API:** Maps to `scenarios generate`.

### WC-003: Grid Execution Launcher
**Description:** As a simulation user, I want to launch a full grid evaluation across all candidate policies (R4, R6, R8, R10, R14) so that I can generate the trade-off frontier.
**Acceptance Criteria:**
- **Functional:** Select `grid_mvp.yaml` and launch.
- **Functional:** UI shows that this will spawn multiple concurrent evaluations.
- **UX:** Clear warning about estimated execution time based on scenario count * policy count.
**Dependencies:** WC-001.
**UX/A11y/Responsive:** Warning alert using high contrast.
**Design System Components:** Alert, GridLauncherCard.
**Technical/API:** Maps to `grid` CLI command.

### WC-004: Execution Monitoring & State Tracking
**Description:** As a simulation user, I want to monitor the exact state of my simulation run so that I know if it is stalled or progressing.
**Acceptance Criteria:**
- **Functional:** Visualizes the state machine: Queued -> Starting -> Running -> Evaluating -> Generating Reports -> Completed / Failed.
- **UX:** Uses contextual skeletons during data fetch.
- **Performance:** Uses live updates for scenario completion counts (e.g., "12/50 scenarios").
**Dependencies:** WC-001.
**UX/A11y/Responsive:** Progress tracker announces state changes via `aria-live`.
**Design System Components:** Stepper, ProgressCircle.
**Technical/API:** Websocket or polling for job status.

### WC-005: Counterfactual Execution
**Description:** As a simulation user, I want to easily configure counterfactual rules (e.g., junior-first drafting instead of standard rules) so that I can test union negotiation proposals.
**Acceptance Criteria:**
- **Functional:** Exposes a subset of configuration overrides mapped to the `counterfactual` CLI flags.
- **UX:** Clearly marks these runs as "Counterfactual" in the run history to avoid confusion with baseline policies.
**Dependencies:** WC-001.
**UX/A11y/Responsive:** Distinct visual badge for counterfactual runs.
**Design System Components:** FormOverrides, Badge.
**Technical/API:** Maps to `counterfactual` command.

### WC-006: High-Level Results Summary
**Description:** As a simulation user, I want to see a quick summary of a completed run's KPIs so that I don't have to download the full HTML report for a quick check.
**Acceptance Criteria:**
- **Functional:** Displays E[cost], CVaR95, uncovered legs, reserve dispatches, eligibility fraction, and total drafts.
- **Data Integrity:** Ensures figures are rounded appropriately and units ($, count, %) are clear.
- **UX:** Uses a dashboard metric card layout.
**Dependencies:** WC-004.
**UX/A11y/Responsive:** Metrics reflow to a 2-column or 1-column grid on smaller screens.
**Design System Components:** MetricCard, KeyValueGrid.
**Technical/API:** Parses the output summary JSON.

### WC-007: Run Cancellation
**Description:** As a simulation user, I want to cancel a running simulation so that I can free up compute resources if I realize I made a mistake.
**Acceptance Criteria:**
- **Functional:** Clicking cancel safely terminates the job and marks status as `cancelled`.
- **UX:** Requires confirmation (e.g., a modal) to prevent accidental clicks.
- **Error Handling:** If cancellation fails (e.g., job already finishing), show contextual error.
**Dependencies:** WC-004.
**UX/A11y/Responsive:** Focus trapping inside the confirmation modal.
**Design System Components:** Modal, DangerButton.
**Technical/API:** API endpoint to send SIGINT/terminate to the worker.

### WC-008: Navigation to Detailed Reports
**Description:** As a simulation user, I want a direct link from the completed run to the detailed Plotly HTML reports so that I can do deep-dive analysis.
**Acceptance Criteria:**
- **Functional:** Provides buttons to "View Policy Report (HTML)" and "View Gate V3 (HTML)".
- **UX:** Opens reports in a new tab with an external link icon.
**Dependencies:** WC-006.
**UX/A11y/Responsive:** `target="_blank"` links include visually hidden text indicating it opens a new window.
**Design System Components:** LinkButton, Icon.
**Technical/API:** Serves static HTML artifacts from the completed run directory.

### WC-009: Run Re-execution (Clone)
**Description:** As a simulation user, I want to clone and re-run a previous simulation with minor tweaks so that I don't have to re-enter all parameters.
**Acceptance Criteria:**
- **Functional:** "Re-run" button opens the launch form pre-populated with the previous run's exact parameters.
- **UX:** Highlights that this is a cloned configuration.
**Dependencies:** WC-001.
**UX/A11y/Responsive:** Form remains fully editable.
**Design System Components:** ActionMenu, Form.
**Technical/API:** Fetches previous run payload and seeds the UI state.

### WC-010: Grid Results Visualization
**Description:** As a simulation user, I want to see the results of a grid execution plotted as a trade-off curve so that I can identify the optimal policy.
**Acceptance Criteria:**
- **Functional:** Plots E[cost] vs CVaR95 for policies R4-R14 on a scatter plot.
- **UX:** Hovering over a point shows the policy name and exact values.
- **Accessibility:** Must provide the grid data as a sortable CSV-like table alongside the chart.
**Dependencies:** WC-003.
**UX/A11y/Responsive:** Chart must handle responsive resizing.
**Design System Components:** ScatterPlot, DataTable.
**Technical/API:** Parses the Grid CSV output artifact.

# Epic D — Cascade Evaluation & Epic E — Reporting & Analytics

## Implementation note, 2026-08-12 — WD-001/002/003/004 built

`reporting/cascade_analytics.py` + `api/routers/analytics.py` + the
`features/analytics` view. Three things diverge from the ACs below, each
because the data does not support what was specified:

1. **No cascade DEPTH anywhere (WD-002/WD-004).** `LedgerRow` carries
   `root_event_uid`, never the immediate parent, so a chain that cascaded four
   levels and one that broke four pairings at once are identical in the
   ledger — `tape.py::_depth_of` reads the same map and can only ever return 0
   or 1. Chain **size** (distinct open items sharing a root) is reported
   instead. Recording parentage in the engine is what WD-002's node-edge graph
   would need first; drawing it today would mean inventing the edges.
2. **No gate V4 verdict on the page.** V4 is INCONCLUSIVE (S1d-04: holdout
   draft reconstruction recall is 0.000, so the historical band has zero
   width). A "validated cascade rate" card would be the same fabrication this
   router's predecessor was deleted for.
3. **No seed-mismatch warning (WD-004).** Every row comes from one grid job,
   and `run_grid` passes one master seed to every policy in it, so the warning
   could never fire. The response states the pairing basis instead.

Computed in `grid._run_one_policy` while the Simulation objects are still in
memory (same reason `daily_outcomes` is) and stored on the batch job, so the
endpoints read a completed run rather than simulating on request — that keeps
the cascade figures and the E[C] beside them drawn from the same CRN set, and
keeps WD-001's "< 1s" bar reachable.

**Measured on the real corpus (R6/R10, 10 CRN scenarios, seed `master`):**
amplification **6.5×** ($464 mean per chain resolved where it landed vs
$3,000 once it cascaded), cascade rate 0.41% for R10 and 0.00% for R6, all 5
cascading drafts falling in scenario 7 alone. The costliest chain is 5 open
items and $3,400 — three successive tier-2 drafts. **A run with no cascades is
the common case at this roster scale, not an edge case**, so the empty state
is an explicit measured-zero panel, and a job that predates this feature is
reported as "no data, re-run" rather than rendered as zero — the two look
identical in a chart and mean opposite things.

**Open, found while building this (engine, not the dashboard).** Every ledger
row in both exemplar chains is booked at the *same simulated minute* as the
draft that triggered it, so `cascade.visibility_lag_hours` (24h) is currently
inert for them. The traces show why: the "future" pairing often starts
*before* `now` (item 170: pairing at `[31328, 32041]`, drafted at t=32026), and
where it is genuinely ahead it is inside the 24h lead, so
`visible_at = max(now, start - lag)` collapses to `now`. Worth a look against
S1d-01's own `fails_if` ("the cascade fires immediately — recovery then happens
with foresight nobody has"); not touched here.

## Epic D: Cascade Evaluation

### WD-001: Cascade Summary Dashboard
**Description**: As a planner, I need a summary of cascade statistics per run so I can understand the macro impact of draft-induced disruptions.
**Acceptance Criteria**:
- *Functional*: Display cascade rate, total cascade events, and total affected crew/pairings per run.
- *UX/Responsive*: KPI cards with trend indicators. Responsive grid layout.
- *Accessibility*: ARIA labels on all KPI cards. High contrast numbers.
- *Error/Data*: Handle zero-cascade runs with an educational empty state ("No cascades triggered in this run").
- *Performance*: Aggregate data must load in < 1s from the API.
**Dependencies**: W0-001 (API foundation), WF-002 (Run Detail)
**Design System Components**: KPI Card, Stat Grid, Empty State
**Technical/API Implications**: Requires API endpoint `/api/runs/{id}/metrics/cascade`.

### WD-002: Cascade Timeline Visualization
**Description**: As an analyst, I want to see the cascade chain visually so I can trace trigger events to resolutions.
**Acceptance Criteria**:
- *Functional*: Render a horizontal timeline showing the trigger event, propagation through OpenTimeItems, and final resolution.
- *UX/Responsive*: Interactive timeline with zoom/pan. On mobile, degrade to a vertical step list.
- *Accessibility*: Keyboard navigable nodes. Screen-reader readouts for each node's summary.
- *Error/Data*: Display skeleton loaders while fetching chain data.
- *Provenance*: Link nodes directly to the underlying `explain-cascade` CLI trace.
**Dependencies**: WD-001
**Design System Components**: Interactive Timeline, Skeleton Loader, Node Tooltip
**Technical/API Implications**: Parse output from `explain-cascade` into a node-edge graph structure.

### WD-003: Cascade Detail Drill-down
**Description**: As an analyst, I need to see the specific crew members, pairings, and legality rules applied at each step of a cascade.
**Acceptance Criteria**:
- *Functional*: Clicking a cascade node shows side-panel details (crew ID, pairing ID, Legality L0-L8 triggered, duration).
- *UX/Responsive*: Drawer component on tablet/desktop, full-screen modal on mobile.
- *Accessibility*: Focus management (trap focus in drawer).
- *Performance*: Lazy-load details only when a node is clicked.
**Dependencies**: WD-002
**Design System Components**: Sliding Drawer, Data List, Status Badge
**Technical/API Implications**: Fetch node-specific details via `/api/runs/{id}/cascades/{cascade_id}`.

### WD-004: Cascade Policy Comparison
**Description**: As a policy designer, I want to compare cascade behaviors across two policies to see which produces fewer disruptive chains.
**Acceptance Criteria**:
- *Functional*: Side-by-side metric comparison (rate, depth, duration) between two runs.
- *UX/Responsive*: Horizontal scroll on mobile for comparison tables.
- *Data Integrity*: Ensure both runs used the same random seed for valid comparison. Warn user if seeds differ.
**Dependencies**: WD-001, WH-001 (Run Comparison)
**Design System Components**: Comparison Table, Alert/Warning Banner
**Technical/API Implications**: Orchestrate data from two run IDs simultaneously.

---

## Epic E: Reporting & Analytics

### WE-001: KPI Dashboard
**Description**: As a user, I need a centralized dashboard of all key metrics for a run.
**Acceptance Criteria**:
- *Functional*: Display E[cost], CVaR95, uncovered legs, reserve dispatches, eligibility fraction, cascade rate, total drafts.
- *UX/Responsive*: Contextual skeletons for loading. Semantic status labels (not just colors).
- *Accessibility*: Accessible charts (e.g., data tables as alternatives).
**Dependencies**: WF-002 (Run Detail)
**Design System Components**: Dashboard Layout, KPI Card
**Technical/API Implications**: Map to `report` CLI command output JSON.

### WE-002: Cost Breakdown Analysis
**Description**: As a financial analyst, I need to see cost distributed across categories.
**Acceptance Criteria**:
- *Functional*: Show costs by reserve, draft, cascade, cancellation, delay, APPR, terminal.
- *UX/Responsive*: Stacked bar chart and detailed data table.
- *Accessibility*: Chart tooltips must be keyboard accessible.
**Dependencies**: WE-001
**Design System Components**: Stacked Bar Chart, Sortable Table
**Technical/API Implications**: Query CostLedger aggregated by category.

### WE-003: Cost Distribution Histograms
**Description**: As a risk manager, I want to see the distribution of costs across all scenarios.
**Acceptance Criteria**:
- *Functional*: Render a Plotly-equivalent histogram of total costs per scenario. Mark 95th percentile (CVaR boundary).
- *UX/Responsive*: Interactive bins. Responsive SVG/Canvas.
- *Data Integrity*: Ensure bin sizes dynamically adjust to avoid degenerate visuals.
**Dependencies**: WE-001
**Design System Components**: Histogram, Chart Legend
**Technical/API Implications**: Expose scenario-level cost aggregates from Parquet/DB.

### WE-004: Reserve Trade-off Curve
**Description**: As a scheduler, I want to explore the cost vs. reserve level trade-off.
**Acceptance Criteria**:
- *Functional*: Interactive scatter plot plotting E[Cost] on Y vs Reserve Headcount on X.
- *UX/Responsive*: Crosshairs on hover to read exact coordinates.
- *Accessibility*: Provide a tabular view of the plotted points.
**Dependencies**: WE-001
**Design System Components**: Scatter Plot, Toggle (Chart/Table)
**Technical/API Implications**: Extract from Policy Report HTML or raw Grid CSV.

### WE-005: Lambda Objective Curve
**Description**: As an optimizer, I need to visualize E[C] + λ·CVaR vs various λ values.
**Acceptance Criteria**:
- *Functional*: Line chart showing the objective function score as lambda varies.
- *UX/Responsive*: Slider to dynamically adjust lambda and see the projected score.
- *Performance*: Client-side calculation of the linear combination for real-time slider response.
**Dependencies**: WE-001
**Design System Components**: Line Chart, Range Slider
**Technical/API Implications**: Requires base E[C] and CVaR95 values.

### WE-006: Eligibility Analysis
**Description**: As a simulator validator, I want to compare simulated eligibility against historical bands.
**Acceptance Criteria**:
- *Functional*: Overlay simulated eligibility curve on historical confidence bands.
- *UX/Responsive*: Clearly distinguish sim (solid line) from historical (shaded area).
- *Data Integrity*: Show warning if simulated curve falls outside historical bands.
**Dependencies**: WE-001
**Design System Components**: Area Chart, Alert Banner
**Technical/API Implications**: Map to `data eligibility-target` output.

### WE-007: Exemplar Scenario Drilldowns
**Description**: As an analyst, I want to investigate the "costliest" and "typical" scenarios to understand the extremes and the norm.
**Acceptance Criteria**:
- *Functional*: Quick links to the max-cost scenario and median-cost scenario.
- *UX/Responsive*: Split-pane view showing scenario metadata and event timeline.
- *Accessibility*: Screen reader announcements for scenario context changes.
**Dependencies**: WE-001, WD-002
**Design System Components**: Split Pane, Event Timeline
**Technical/API Implications**: Find min/max/median scenarios via scenario aggregation queries.

### WE-008: Grid Results Explorer
**Description**: As an optimization engineer, I want to explore the results of a grid execution.
**Acceptance Criteria**:
- *Functional*: Render a highly filterable, sortable table representing the Grid CSV.
- *UX/Responsive*: Horizontal scrolling with frozen first column for policy ID.
- *Data Integrity*: Highlight the Pareto-optimal frontier policies.
**Dependencies**: WE-001
**Design System Components**: Advanced Data Grid, Sticky Column
**Technical/API Implications**: Parse and serve the Grid CSV efficiently (pagination required).

### WE-009: Gate Results Dashboard
**Description**: As a QA lead, I want to see the pass/fail status of Gates V1-V9 for a run.
**Acceptance Criteria**:
- *Functional*: Display a grid of gates (V1 degeneracy, V2 Erlang-B, V3 eligibility, etc.) with semantic status.
- *UX/Responsive*: Clickable gate cards that open detailed gate reports.
- *Accessibility*: Use icons + text for pass/fail (color independence).
**Dependencies**: WE-001
**Design System Components**: Status Grid, Gate Card
**Technical/API Implications**: Map `gate v1-v9` CLI command outputs to API statuses.

### WE-010: Data Quality Report Viewer
**Description**: As a data engineer, I need to review input data quality before trusting simulation results.
**Acceptance Criteria**:
- *Functional*: Display pass/marginal/fail indicators for data quality checks.
- *UX/Responsive*: Expandable accordion for failed checks showing exact missing/malformed records.
- *Error/Data*: Provide clear text on how to fix marginal/failed data.
**Dependencies**: W0-001
**Design System Components**: Accordion, Status Badge
**Technical/API Implications**: Output from `data quality-report`.

### WE-011: Universal Drill-down Pattern
**Description**: As a user, I want a consistent path from macro KPIs to micro ledger entries.
**Acceptance Criteria**:
- *Functional*: Every KPI card must link to a metric detail page -> underlying events list -> raw CostLedger entries.
- *UX/Responsive*: Breadcrumb navigation to track drill-down depth.
- *Accessibility*: Breadcrumbs must be marked up as `<nav aria-label="Breadcrumb">`.
**Dependencies**: WE-001, WE-002
**Design System Components**: Breadcrumbs, Drill-down Link
**Technical/API Implications**: Relational queries joining Scenarios -> Events -> Ledger.

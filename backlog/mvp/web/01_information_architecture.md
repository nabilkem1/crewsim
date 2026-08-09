# CrewSim Web UI: Information Architecture

## 1. Application Structure (Sitemap)

* **Dashboard** (System health, recent jobs, quick actions)
* **Configurations**
  * List Configurations
  * Detail / Edit
  * Parameter Tuning (Base, Costs, Policies, Grid)
  * Validation Constraints
* **Calibration**
  * List Calibrations
  * New Calibration Pipeline
  * Detail / Diagnostics
  * Generated Artifacts (Regimes, Sick Calls, Delays)
* **Processing / Execution**
  * New Run (Wizard)
  * Policy & Scenario Selection
  * Live Monitoring / Job State
  * Results Summary
* **Runs (History & Analysis)**
  * Run History
  * Run Detail
  * Provenance & Lineage
  * Compare Runs
* **Reports & Analytics**
  * Dashboard Overview (Plotly embeds)
  * KPI Analysis (E[C], CVaR95)
  * Cascade & Draft Analysis (Gini, Eligibility Bands)
* **Artifacts**
  * Browse Store (JSON, Parquet, HTML, CSV)
  * Artifact Detail & Hash Verification
* **Jobs**
  * Active Queue (running, queued)
  * Completed
  * Failed / Cancelled
* **Settings & Diagnostic**
  * Engine Diagnostics (`doctor`)

## 2. Navigation Model
* **Desktop:** Persistent left sidebar with accordion sections for domain areas (Data, Calibrate, Execute, Analyze). Main content area fluid, expanding to 100% width for grids.
* **Tablet:** Collapsible drawer navigation. Main content area optimized for touch targets.
* **Mobile:** Compact header with hamburger menu. Focus shifts exclusively to Job Status, Alerts, and high-level KPI consumption.

## 3. URL Structure

All routes should be deep-linkable and support browser history:
* `/dashboard`
* `/configurations`
* `/configurations/:id`
* `/calibrations`
* `/calibrations/new`
* `/calibrations/:id`
* `/processing/new`
* `/processing/:jobId`
* `/runs`
* `/runs/:id`
* `/runs/:id/provenance`
* `/runs/:id/reports`
* `/reports`
* `/reports/:id`
* `/compare?runs=id1,id2` (or `/compare?policies=p1,p2`)
* `/artifacts`
* `/artifacts/:id`
* `/jobs`
* `/jobs/:id`

## 4. Primary User Journeys

### 4.1. First-Time Calibration and Simulation
1. Operator navigates to `/calibrations/new`.
2. Initiates calibration pipeline (Regime, Sick-calls, Delays).
3. Monitors async job in `/jobs/:id`.
4. Upon `completed` status, reviews generated diagnostic artifacts.
5. Clicks "Start Run from Calibration", routing to `/processing/new`.
6. Selects Policies (R4, R6) and executes grid.
7. Views results in `/runs/:id/reports`.

### 4.2. Policy Comparison Workflow
1. Analyst navigates to `/runs`.
2. Selects two completed runs (e.g., Base Policy vs Counterfactual) using checkboxes.
3. Clicks "Compare", routing to `/compare?runs=A,B`.
4. Reviews side-by-side Paired CRN T-test results, cost distributions, and draft frequencies.
5. Exports comparison artifact.

### 4.3. Failed Run Investigation
1. Operator sees a `failed` badge in the navigation sidebar under Jobs.
2. Navigates to `/jobs/failed` and selects the failed run.
3. Reviews contextual error message (What, Why, What Next).
4. Navigates to the associated `/configurations/:id` via a deep link to fix the identified JSON validation issue.
5. Re-runs job.

### 4.4. Result Justification and Traceability (SME)
1. SME navigates to a completed run at `/runs/:id`.
2. Reviews the `CVaR95` metrics and clicks "Explain Cascade".
3. UI presents a trace narrative (timeline of events) for the peak disruption week.
4. SME drills down into a specific skipped pilot to view the Legality Check (L0-L8) failure reason.

### 4.5. Experienced User Direct-Access
1. Operator pastes a specific hash link `/artifacts/ab3f92e` into the browser.
2. Directly views the immutable JSON output and the downstream runs it spawned.

## 5. Cross-Cutting Navigation Patterns
* **Breadcrumbs:** Used in nested hierarchies, especially for artifact drill-downs (e.g., `Runs / Run-1024 / Provenance / Scenario-A`).
* **Contextual Navigation:** Entities are heavily cross-linked. A configuration links to all runs that used it; a report links back to the originating job and configuration.
* **Status-Aware Navigation:** The sidebar includes persistent badge counters for active/queued and failed jobs.

## 6. Responsive Navigation Adaptation
* **Empty States:** If a route expects data but finds none (e.g., no completed runs yet), the UI presents an educational empty state explaining *why* it is empty and providing a primary CTA (e.g., "Configure New Run").
* **Tables on Mobile:** Data grids transform to card-based layouts or implement strict horizontal scrolling with pinned left columns on viewports < 768px.
* **Loading States:** No full-page spinners. Transitioning to `/reports/:id` immediately renders the layout shell and breadcrumbs, utilizing contextual skeleton loaders for the specific Plotly graphs as they hydrate.

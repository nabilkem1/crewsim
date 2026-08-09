# CrewSim Web UI: CLI Capability Matrix

## CLI to Web UI Mapping

| CLI Command | Category | Web Equivalent | API Endpoint Required | Sync/Async | UI Pattern | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `doctor` | Diagnostic | Dashboard / System Settings | `GET /api/system/health` | Sync | Status Badges, Logs | Shows environment readiness, engine version. |
| `config show` | Diagnostic | Configuration Detail | `GET /api/configs/:id` | Sync | Read-only JSON / Form | Maps to 60+ param visual inspector. |
| `data head` | Data Validation | Dataset Preview Modal | `GET /api/data/preview` | Sync | Data Table | Paginated grid view. |
| `data profile` | Data Validation | Artifacts / Data Profile | `GET /api/artifacts/:id/profile` | Sync | HTML Embed | Renders standard pandas-profiling/custom HTML. |
| `data quality-report` | Data Validation | Diagnostics Dashboard | `GET /api/data/quality` | Sync | KPI Cards, Warning List | Highlights missing/invalid data before runs. |
| `data draft-events` | Data Validation | Event Explorer | `GET /api/data/drafts` | Sync | Filterable Table | |
| `data cascade-target` | Data Validation | Cascade Analysis | `GET /api/data/cascades` | Sync | Chart / Table | |
| `data eligibility-target` | Data Validation | Eligibility Analysis | `GET /api/data/eligibility` | Sync | Chart / Table | |
| `calibrate` | Calibration | New Calibration Pipeline | `POST /api/jobs/calibrate` | Async | Wizard + Progress | Triggers the full pipeline. |
| `calibrate regime` | Calibration | Regime Calibration Detail | `POST /api/jobs/calibrate/regime` | Async | Form + Progress | 4x4 Markov transition matrix visualizer. |
| `calibrate sick-calls` | Calibration | Sick Call Calibration | `POST /api/jobs/calibrate/sick-calls` | Async | Form + Progress | Shows NHPP GLM fit graphs. |
| `calibrate delays` | Calibration | Delay Calibration | `POST /api/jobs/calibrate/delays` | Async | Form + Progress | GMM distribution visualizer. |
| `fit-delays` | Calibration | Advanced Tuning | `POST /api/jobs/fit-delays` | Async | Advanced Modal | Likely backend-only or advanced toggle. |
| `scenarios generate` | Scenarios | Run Configurator | `POST /api/jobs/scenarios` | Async | Step in Run Wizard | Generates Parquet files, linked in Provenance. |
| `gate v1` - `gate v9` | Verification | Validation Gates View | `POST /api/jobs/gates/:version` | Async | Status Matrix | Dedicated view showing Pass/Fail for V1-V9 with drilldowns. |
| `roster summary` | Roster | Engine Data View | `GET /api/rosters/:id/summary` | Sync | Stats Row, Table | |
| `roster reserve-pattern` | Roster | Policy Editor | `GET /api/rosters/:id/patterns` | Sync | Gantt/Calendar View | Visual representation of Stage 1 variables. |
| `run` | Execution | New Run (Single) | `POST /api/jobs/run` | Async | Form + Progress | Core engine invocation. |
| `compare` | Execution | Policy Comparison | `POST /api/jobs/compare` | Async | Side-by-side View | Paired CRN T-test UI. |
| `report` | Analytics | Report Viewer | `GET /api/reports/:id` | Sync | Plotly Dashboard | Replaces raw HTML generation with embedded interactive components. |
| `grid` | Execution | Grid Execution | `POST /api/jobs/grid` | Async | Matrix Selector | Batch launches multiple `run` policies. |
| `counterfactual` | Execution | Scenario Tweaker | `POST /api/jobs/counterfactual` | Async | "What-if" Form | Clone run, modify Stage 2, execute. |
| `explain-legality` | Explainability | Legality Inspector | `GET /api/explain/legality` | Sync | Timeline / Checkbox List | Crucial SME tool showing L0-L8 pass/fail. |
| `explain-event` | Explainability | Event Trace | `GET /api/explain/events/:id` | Sync | Event Log | |
| `explain-crew` | Explainability | Crew Member Trace | `GET /api/explain/crew/:id` | Sync | Timeline | |
| `explain-cascade` | Explainability | Cascade Visualizer | `GET /api/explain/cascade/:id` | Sync | Flow Diagram / Tree | Shows how one delay triggered multiple drafts. |
| `explain-draft` | Explainability | Draft Rationale | `GET /api/explain/draft/:id` | Sync | Info Panel | Links Stage 2 rules to a specific action. |
| `explain-cost` | Explainability | Cost Breakdown | `GET /api/explain/cost/:id` | Sync | Waterfall Chart | Deconstructs E[C] into guarantee, premium, disruption. |
| `explain-recovery` | Explainability | Recovery Pipeline | `GET /api/explain/recovery/:id` | Sync | Pipeline visualizer | SimPy state machine visualization. |

## Web UI Value-Add (Beyond CLI Parity)
1. **Run History & Lineage:** The CLI relies on filesystem structures for history. The Web UI will maintain a relational history, allowing users to query "Show me all runs that used configuration X and scenario Y."
2. **Visual Configuration Builder:** Replacing manual editing of complex JSON parameter stores with form validation, dropdowns for base/fleet/position, and instant schema validation.
3. **Interactive Side-by-Side Comparison:** While the CLI `compare` runs statistical tests, the Web UI will overlay the Plotly charts (Cost distributions, reserve trade-off curves) from multiple runs interactively.
4. **Job Queue Management:** Moving from synchronous blocking terminal commands to a managed background queue (Active/Completed/Failed) with visual progression.
5. **Contextual Explainability:** In the CLI, users must note an ID in a report and pass it to an `explain-*` command. In the Web UI, explainability is triggered directly via contextual clicks within the reports and data tables.

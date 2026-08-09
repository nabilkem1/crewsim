# Epic F — Run Management & Epic G — Provenance & Justification

## Epic F: Run Management

### WF-001: Run History
**Description**: As a user, I need to browse a list of all historical simulation runs.
**Acceptance Criteria**:
- *Functional*: Paginated, sortable list of runs showing ID, Date, Policy, Status, and primary KPI.
- *UX/Responsive*: Table view on desktop, card stack view on mobile.
- *Accessibility*: Table headers must be sortable via keyboard.
- *Error/Data*: Empty state for new workspaces ("No runs yet. Start your first calibration.")
- *Performance*: Load first page of runs in < 500ms.
**Dependencies**: W0-001 (API/DB foundation)
**Design System Components**: Data Table, Pagination, Empty State
**Technical/API Implications**: GET `/api/runs` with pagination, sorting, and summary metrics.

### WF-002: Run Detail View
**Description**: As a user, I want a complete view of a single run to understand its context and results.
**Acceptance Criteria**:
- *Functional*: Display status, configuration, policy, calibration reference, seed, metrics, and links to reports.
- *UX/Responsive*: Persistent sidebar navigation on desktop for run sections, drawer on tablet.
- *Accessibility*: Main content landmark for screen readers.
- *Error/Data*: Clearly show if a run was cancelled or failed, with context.
**Dependencies**: WF-001
**Design System Components**: Page Header, Sidebar Nav, Detail List
**Technical/API Implications**: GET `/api/runs/{id}` containing full metadata payload.

### WF-003: Run Status & Lifecycle Updates
**Description**: As a user running a simulation, I want to know its current state.
**Acceptance Criteria**:
- *Functional*: Display semantic status: `queued`, `running`, `completed`, `failed`, `cancelled`.
- *UX/Responsive*: Progress indicators (percentage if available, or pulse for running).
- *Accessibility*: Live region (`aria-live="polite"`) for status changes.
**Dependencies**: WF-001, WJ-001 (Job Queue)
**Design System Components**: Status Badge, Progress Bar
**Technical/API Implications**: WebSocket or SSE for real-time status updates from the engine.

### WF-004: Run Re-execution (Clone & Run)
**Description**: As an analyst, I want to re-run an existing simulation with identical or slightly modified parameters.
**Acceptance Criteria**:
- *Functional*: "Re-run" button that pre-fills a configuration form with the run's exact parameters (seed included).
- *UX/Responsive*: Form with explicit labels, validation on blur.
- *Data Integrity*: Prevent mutation of the original run; always generate a new Run ID.
**Dependencies**: WF-002
**Design System Components**: Action Button, Complex Form
**Technical/API Implications**: POST `/api/runs` using payload from previous run.

### WF-005: Run Search & Filter
**Description**: As a manager, I need to find specific runs based on metadata or performance thresholds.
**Acceptance Criteria**:
- *Functional*: Filter by status, policy name, date range, config version, and metric thresholds (e.g. E[cost] < X).
- *UX/Responsive*: Filter panel that collapses into a filter icon on mobile.
- *Accessibility*: Clear focus states on form inputs; "Clear filters" button must be keyboard accessible.
**Dependencies**: WF-001
**Design System Components**: Filter Panel, Range Inputs, Tag List
**Technical/API Implications**: Complex query parameters on `/api/runs`.

### WF-006: Run Metadata Extensibility
**Description**: As a data engineer, I need to ensure all execution context is captured.
**Acceptance Criteria**:
- *Functional*: Store and display simulator version, config version, execution duration, and scenario count.
- *Data Integrity*: Metadata must be immutable once the run reaches `running` state.
**Dependencies**: WF-002
**Design System Components**: Metadata Grid
**Technical/API Implications**: Schema validation for metadata JSONb columns.

---

## Epic G: Provenance & Justification

### WG-001: End-to-End Provenance View
**Description**: As an auditor, I need to see the complete lineage of a run's result.
**Acceptance Criteria**:
- *Functional*: Visual chain linking: Sim Version → Config → Calibration → Policy → Seed → Run Execution → Output Metrics.
- *UX/Responsive*: Flow diagram or step-wise lineage view.
- *Accessibility*: Text-based alternative to the visual lineage graph.
**Dependencies**: WF-002
**Design System Components**: Lineage Graph, Timeline
**Technical/API Implications**: Query linking multiple database entities (calibrations, configs, runs).

### WG-002: Effective Configuration Snapshot
**Description**: As a user, I need to know the exact parameter values used, not just the file reference, to avoid mutation issues.
**Acceptance Criteria**:
- *Functional*: Display a read-only snapshot of the exact JSON configuration resolved at run-time.
- *UX/Responsive*: Code viewer component with syntax highlighting and copy-to-clipboard.
- *Data Integrity*: Snapshot must be detached from the source config file so future edits don't alter the run record.
**Dependencies**: WG-001
**Design System Components**: Code Viewer, Copy Button
**Technical/API Implications**: Engine must emit `effective_config.json` upon run start.

### WG-003: Reproducibility Proof (Gate V7)
**Description**: As a developer, I must guarantee that running the same inputs yields the same outputs.
**Acceptance Criteria**:
- *Functional*: UI exposes the V7 Gate verification button. When clicked, it runs a micro-simulation with the same seed and diffs the output.
- *UX/Responsive*: Loading skeleton during verification; clear "Match" / "Mismatch" result card.
- *Provenance*: Explicitly states "Seed X + Config Y = Exact Match".
**Dependencies**: WG-001, WE-009
**Design System Components**: Verification Card, Skeleton
**Technical/API Implications**: API endpoint to trigger a V7 reproducibility test job.

### WG-004: Result Tracing Path
**Description**: As an analyst, I want to trace a high-level KPI down to its root cause.
**Acceptance Criteria**:
- *Functional*: Click path from KPI → Metric Detail → Scenario Event → Ledger Entry → Root Cause Event.
- *UX/Responsive*: Split view where clicking a ledger entry highlights the root cause in the event timeline.
- *Error/Data*: Graceful fallback if the root cause was pruned due to data retention limits.
**Dependencies**: WE-011, WG-001
**Design System Components**: Split View, Highlighted Rows
**Technical/API Implications**: Graph traversal of `root_event_uid` in the CostLedger.

### WG-005: Explain Command Integration
**Description**: As a planner, I want web UI access to the CLI's `explain-*` insights.
**Acceptance Criteria**:
- *Functional*: Web interfaces for `explain-legality`, `explain-crew`, `explain-draft`, `explain-cost`, `explain-recovery`.
- *UX/Responsive*: Contextual side-panels or modals when clicking on a Crew ID, Event, or Cost entry.
- *Accessibility*: Modal dialogs must trap focus and support `Esc` to close.
**Dependencies**: WF-002
**Design System Components**: Modal Dialog, Data Tree
**Technical/API Implications**: API wrappers around the corresponding CLI trace commands.

### WG-006: Audit Trail Log
**Description**: As a system administrator, I need to know who ran what and when.
**Acceptance Criteria**:
- *Functional*: Read-only log showing User, Action (started run, cancelled run, modified config), Timestamp, and Run ID.
- *UX/Responsive*: Simple chronological list with search.
- *Data Integrity*: Audit logs must be append-only and immutable.
**Dependencies**: W0-001
**Design System Components**: Audit Log Table
**Technical/API Implications**: Middleware to intercept state-changing API requests and log them.

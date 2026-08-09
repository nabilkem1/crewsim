# Epic B: Calibration

## Objective & User Value
Expose the complex calibration pipeline through the Web UI. 
**User Value:** Demystifies the Markov Chain and GMM fitting process. Allows users to confidently launch, monitor, inspect, and trust the mathematical calibration of the simulator without needing CLI mastery, ensuring provenance and transparency in the underlying models.

## Capabilities & Scope
- Launch calibration pipelines (full or specific stages: regime/sick-calls/delays).
- Real-time monitoring of calibration progress.
- Visualization of calibration results (Markov matrix, NHPP coefficients, GMM fits).
- Diagnostics and goodness-of-fit.
- Comparing parameter fits across runs/seasons.
- Quality Gates (Data quality-report for D4, D6, D9).
- Hash-based artifact provenance tracking.

---

## User Stories

### WB-001: Run Data Quality Gates (`quality-report`)
**Description:** As a simulation user, I want to run and view the data quality gates before calibration so that I know if the raw data is fit for fitting models.
**Acceptance Criteria:**
- **Functional:** Executes the equivalent of `data quality-report`.
- **Functional:** Displays pass/fail status for D4 linkage (>0.95), D6/D7 join (>0.80), and D9 completeness (>0.98).
- **UX:** Uses semantic indicators (e.g., green checkmark for pass, red warning for fail).
- **Error Handling:** Explains exactly what missing data caused a failure (What, Why, What next).
**Dependencies:** None.
**UX/A11y/Responsive:** Data tables must be sortable and scrollable horizontally on mobile.
**Design System Components:** StatusBadge, DataTable, Alert.
**Technical/API:** New endpoint mapping to CLI `data quality-report`.

### WB-002: Calibration Pipeline Launcher
**Description:** As a simulation user, I want to configure and launch a calibration run so that I can generate new parameter sets for simulation.
**Acceptance Criteria:**
- **Functional:** Form allows selection of Season, Window, and specific stages (Full, Regime, Sick-calls, Delays).
- **UX:** Form uses semantic HTML, explicit labels, and validation on blur. 
- **Error Handling:** Cannot launch if dependent config is missing.
**Dependencies:** WB-001.
**UX/A11y/Responsive:** Drawer or modal layout for the launch form.
**Design System Components:** Form, Select, ButtonGroup.
**Technical/API:** Triggers asynchronous job for `calibrate`.

### WB-003: Calibration Run Monitoring
**Description:** As a simulation user, I want to monitor the progress of a running calibration so that I know when my parameters are ready.
**Acceptance Criteria:**
- **Functional:** Displays real-time progress through Regime -> Sick Call -> Delay stages.
- **UX:** Uses semantic status indicators (queued, running, completed, failed, cancelled) instead of just colors.
- **Performance:** UI updates efficiently without full page reloads (e.g., SSE or polling).
**Dependencies:** WB-002.
**UX/A11y/Responsive:** Progress bar with screen reader text for completion percentage.
**Design System Components:** ProgressBar, StatusTracker, LiveLogViewer.
**Technical/API:** Requires a streaming log or job status endpoint.

### WB-004: Calibration Results Inspection
**Description:** As a simulation user, I want to inspect the results of a completed calibration to verify the fitted models.
**Acceptance Criteria:**
- **Functional:** Displays Regime 4x4 Markov Matrix (CALM, NORMAL, DISRUPTED, SEVERE).
- **Functional:** Shows NHPP coefficients (NegBin GLM) and Delay GMM components (using configured component count).
- **UX:** Displays values in a well-spaced, easy-to-read layout.
**Dependencies:** WB-003.
**UX/A11y/Responsive:** Matrices displayed as properly formatted HTML tables with `th` and `scope` attributes.
**Design System Components:** DataGrid, Card.
**Technical/API:** Fetches the generated JSON parameter store.

### WB-005: Calibration Diagnostics & Goodness-of-Fit
**Description:** As a simulation user, I want to visualize the goodness-of-fit diagnostics to ensure the statistical models accurately reflect the underlying data.
**Acceptance Criteria:**
- **Functional:** Displays charts overlaying raw data distributions vs. fitted GMM and NHPP curves.
- **UX:** Purpose-built charts with accessible alternatives (data tables). Clear axes/units/legends.
**Dependencies:** WB-004.
**UX/A11y/Responsive:** Charts are responsive to container width.
**Design System Components:** LineChart, Histogram, TabView.
**Technical/API:** Might require generating plot data on the backend and sending to frontend.

### WB-006: Calibration Comparison
**Description:** As a simulation user, I want to compare calibration outputs across two seasons so that I can analyze behavioral drift in operations.
**Acceptance Criteria:**
- **Functional:** Select two calibration runs and view a diff of the Markov matrices and coefficients.
- **UX:** Clear visual cues for deltas (up/down arrows, percentage changes).
**Dependencies:** WB-004.
**UX/A11y/Responsive:** Use compact spacing for side-by-side matrices on desktop, stack on mobile.
**Design System Components:** ComparisonTable, DeltaIndicator.
**Technical/API:** Backend endpoint to compute matrix/vector differences.

### WB-007: Calibration Artifacts & Provenance
**Description:** As a simulation user, I want to view the artifact hashes and data sources used for a calibration run to guarantee reproducibility.
**Acceptance Criteria:**
- **Functional:** Shows the blake2b hash of the JSON param store.
- **Data Integrity:** Links back to the exact code version and data snapshots used.
- **UX:** Simple, read-only metadata list.
**Dependencies:** WB-004.
**UX/A11y/Responsive:** Click-to-copy hash values with toast confirmation.
**Design System Components:** DescriptionList, ClipboardButton, Toast.
**Technical/API:** Extracted from calibration run metadata.

### WB-008: Calibration Log Explorer
**Description:** As a simulation user, I want to explore detailed execution logs for a completed or failed calibration to troubleshoot issues.
**Acceptance Criteria:**
- **Functional:** Searchable, filterable log viewer (info/warn/error levels).
- **UX:** Monospace font for logs. Contextual skeletons during log loading.
**Dependencies:** WB-003.
**UX/A11y/Responsive:** Dark mode log viewer. Screen reader friendly log container.
**Design System Components:** CodeViewer, LogFilter.
**Technical/API:** Connects to file-based logs or central logging service.

# Epic A: Configuration

## Objective & User Value
Expose the simulator's extensive configuration system—currently managed via YAML files (e.g., `base.yaml`, `costs_pilots.yaml`, policies)—through a professional, readable web interface. 
**User Value:** Users can discover, inspect, search, and validate configuration parameters without touching YAML. It ensures configuration provenance is preserved and transparent for every historical run, reducing misconfiguration errors and democratizing access to the simulation engine.

## Capabilities & Scope
- Discovery, browsing, and grouping of config files (Scope, Horizon, Population, etc.).
- Deep parameter inspection (type, default, description, bounds).
- Full-text parameter search.
- Pre-flight configuration validation (identifying invalid values and requiring [CONFIRM] flags).
- Policy (R4-R14) browsing and comparison.
- Visualizing cost structures (tiers, APPR brackets, reserve guarantees).
- Exact configuration snapshots for historical runs.

---

## User Stories

### WA-001: Configuration Discovery & Browsing Dashboard
**Description:** As a simulation user, I want to browse available configuration files grouped by logical categories so that I can easily navigate the complex configuration surface.
**Acceptance Criteria:**
- **Functional:** Displays categories for Scope, Horizon, Population, QualityGates, Calibration, Reconstruction, Legality, Cascade, Sensitivity, and Costs. 
- **Functional:** Lists specific YAML files mapped to these categories (`base.yaml`, `costs_pilots.yaml`, etc.).
- **UX:** Uses a card-based layout for categories. Empty states must explain what a category contains if no files are found.
- **Error Handling:** Contextual error if the backend cannot read the `configs/` directory (What, Why, What next).
**Dependencies:** None.
**UX/A11y/Responsive:** Persistent sidebar for navigation. Tab focus order follows visual hierarchy.
**Design System Components:** Card, Sidebar, Typography (Heading levels).
**Technical/API:** Requires a new `GET /api/v1/configs` endpoint returning grouped metadata.

### WA-002: Deep Parameter Inspection
**Description:** As a simulation user, I want to inspect individual parameters to understand their data types, defaults, and descriptions.
**Acceptance Criteria:**
- **Functional:** Clicking a parameter displays its type (e.g., int, string, array), default value, allowed values, and a verbose description.
- **Data Integrity:** Must parse comments or metadata from the YAML/engine schema to populate descriptions.
- **UX:** Uses contextual skeletons during initial load. 
**Dependencies:** WA-001.
**UX/A11y/Responsive:** Detailed view opens in a side-drawer (tablet/desktop) or full page (mobile).
**Design System Components:** Drawer, Data List, Badge (for types).
**Technical/API:** `GET /api/v1/configs/{id}/parameters` parsed dynamically.

### WA-003: Full-Text Parameter Search
**Description:** As a simulation user, I want to search for parameters globally across all configuration files to quickly locate specific settings like `roster_size` or `terminal_penalty`.
**Acceptance Criteria:**
- **Functional:** Search input queries across file names, parameter keys, and parameter descriptions.
- **UX:** Search highlights the matching text in the results. Shows an educational empty state if no results match.
- **Performance:** Debounced input (300ms) to prevent excessive API calls.
**Dependencies:** WA-001.
**UX/A11y/Responsive:** Search bar in the compact header. `aria-live` region announces the number of results found.
**Design System Components:** SearchInput, HighlightedText.
**Technical/API:** Requires backend search indexing or in-memory search across the config schema.

### WA-004: Pre-flight Configuration Validation
**Description:** As a simulation user, I want the system to validate configurations before execution so that I do not waste time on guaranteed-to-fail runs.
**Acceptance Criteria:**
- **Functional:** Validates rules like `d4_link` bounds, `roster_size` > 0, etc.
- **Functional:** Flags missing [CONFIRM] markers for sensitive overrides.
- **Error Handling:** Invalid fields are marked with contextual errors (e.g., "Must be between 0 and 1").
**Dependencies:** WA-002.
**UX/A11y/Responsive:** Inline validation on blur. Form preserves input on error.
**Design System Components:** FormField, Alert, ValidationMessage.
**Technical/API:** `POST /api/v1/configs/validate` endpoint executing the engine's internal Pydantic validation.

### WA-005: Policy Browser (R4-R14)
**Description:** As a simulation user, I want to browse defined policies (R4, R6, R8, etc.) to understand reserve sizing and stage 2 drafting rules.
**Acceptance Criteria:**
- **Functional:** Lists policies by ID. Shows `stage1.reserves` rules and `stage2` (e.g., `allow_cross_base_reserve`).
- **UX:** Displays complex stage 1 reserve structures in a sortable, filterable table.
**Dependencies:** WA-001.
**UX/A11y/Responsive:** Horizontal scroll on mobile for the stage 1 rules table.
**Design System Components:** Table, Badge (for FULL/REDUCED mode).
**Technical/API:** Parses `policies/*.yaml`.

### WA-006: Cost Structure Visualization
**Description:** As a simulation user, I want to visualize cost structures (Draft tiers, APPR brackets, Reserve guarantees) to understand the financial penalty models.
**Acceptance Criteria:**
- **Functional:** Renders a step-chart or tiered visualization for Draft base_premium and tiers 1-5.
- **UX:** Purpose-built charts with accessible alternatives (data tables) and clear axes/units.
**Dependencies:** WA-001.
**UX/A11y/Responsive:** Chart must use high-contrast colors and provide a toggle to view as a raw data table.
**Design System Components:** StepChart, Toggle, DataTable.
**Technical/API:** Maps `costs_pilots.yaml` / `costs_cabin.yaml`.

### WA-007: Effective Configuration Provenance
**Description:** As a simulation user, I want to view the exact configuration snapshot used for any historical run to ensure auditability and provenance.
**Acceptance Criteria:**
- **Functional:** Given a Run ID, loads the exact resolved configuration JSON artifact.
- **Data Integrity:** Displays the blake2b hash of the configuration to prove immutability.
- **UX:** Clearly visually distinct from the "live/editable" configuration browser.
**Dependencies:** WA-001, WC-nnn (Runs).
**UX/A11y/Responsive:** Read-only mode indicators.
**Design System Components:** CodeViewer, HashBadge.
**Technical/API:** Fetches the configuration artifact from the scenario `.parquet` or metadata store.

### WA-008: Configuration Comparison (Diff)
**Description:** As a simulation user, I want to compare two configurations or policies to see exactly what parameters differ between them.
**Acceptance Criteria:**
- **Functional:** Select two Config IDs or Policy IDs and render a side-by-side or unified diff.
- **UX:** Highlights additions in green, deletions in red, and modifications.
- **Accessibility:** Ensure color differences are accompanied by text labels (e.g., "+", "-", "changed").
**Dependencies:** WA-007, WA-005.
**UX/A11y/Responsive:** Unified diff on mobile, side-by-side on desktop.
**Design System Components:** DiffViewer.
**Technical/API:** Backend endpoint to perform a deep diff of two resolved JSON configurations.

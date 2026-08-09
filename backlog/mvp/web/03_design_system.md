# CrewSim Web UI: Design System Strategy

## 1. Design Tokens

The foundation of the CrewSim Web UI visual language, ensuring consistency, accessibility, and a professional engineering aesthetic.

### Color System
*   **Primary**: `#005A9C` (Actionable elements, primary buttons, active navigation)
*   **Neutral (Surface & Background)**:
    *   `bg-canvas`: `#F8FAFC` (App background)
    *   `bg-surface`: `#FFFFFF` (Cards, panels, modals)
    *   `bg-surface-alt`: `#F1F5F9` (Table headers, secondary panels)
*   **Semantic (Status & Alerts)**:
    *   `success`: `#10B981` (Completed, valid)
    *   `warning`: `#F59E0B` (Delayed, potential issue, degraded)
    *   `error`: `#EF4444` (Failed, illegal state, validation error)
    *   `info`: `#3B82F6` (Running, queued, informational)
*   **Text Colors**:
    *   `text-primary`: `#0F172A` (Headings, primary body)
    *   `text-secondary`: `#475569` (Labels, metadata, timestamps)
    *   `text-disabled`: `#94A3B8` (Disabled states)
*   **Chart Palette**: A distinct, color-blind friendly categorical palette (e.g., Okabe-Ito) prioritizing contrast for lines and bars (e.g., E[C] vs CVaR₀.₉₅ lines).

### Typography
*   **Font Family (UI)**: Inter or standard system sans-serif (system-ui, -apple-system, Roboto) for highly legible UI elements.
*   **Font Family (Data/Code)**: Fira Code, JetBrains Mono, or system monospace. **Mandatory** for numerical data, IDs, hashes (blake2b), and configuration keys.
*   **Hierarchy**:
    *   `h1`: 24px, Semi-Bold (Page Titles)
    *   `h2`: 20px, Medium (Section Headers, Epic Titles)
    *   `h3`: 16px, Medium (Card Titles, Panel Headers)
    *   `body`: 14px, Regular (General text, tables)
    *   `caption`: 12px, Regular (Metadata, timestamps, tooltips)

### Spacing & Layout Scales
*   **Base Unit**: 4px scale (4, 8, 12, 16, 24, 32, 48, 64)
*   **Density**: Emphasize high information density; default padding for tables and cards should be compact (e.g., 8px/12px) to minimize scrolling for operators.
*   **Border Radius**: 4px (`rounded-sm`) for inputs/buttons, 8px (`rounded-md`) for cards and panels. Avoid excessive rounding to maintain a professional, analytical tool aesthetic.
*   **Elevation**: Subtle drop shadows for layered elements (dropdowns, modals, floating headers), using opacities rather than large blur radii.

## 2. Core Components

### Layout & Navigation
*   **App Shell**: Persistent sidebar (desktop), sticky header (actions/status), breadcrumbs (`Simulation > Runs > Run #12a4b > Logs`), and main scrollable content area.
*   **Navigation**: Sidebar items with distinct SVG icons. Badges indicating active background jobs (e.g., a subtle pulse dot or count for running calibrations).
*   **Page Header**: Context-aware. Contains the Title, Breadcrumbs, Metadata (e.g., Environment, Last Synced), and primary Page Actions (e.g., "Run Simulation").

### Status & Feedback
*   **Status Badge**: **CRITICAL RULE**: Never use color alone. Always `Icon + Label + Color`.
    *   *Queued*: `[Clock Icon] Queued (Gray/Info)`
    *   *Running*: `[Spinner/Play Icon] Running (Blue)`
    *   *Completed*: `[Check Icon] Completed (Green)`
    *   *Failed*: `[X Icon] Failed (Red)`
    *   *Cancelled*: `[Slash Icon] Cancelled (Yellow/Gray)`
*   **Progress Indicator**: Determinate (when % is known, e.g., "Stage 1/3") or Indeterminate (when waiting on engine response). Always include text describing the current stage (e.g., "Initializing Cascade Rules...").
*   **Alert/Notification**: Toast notifications for asynchronous events ("Calibration Job failed"). Contextual inline alerts for form validation. Use What/Why/What Next format.
*   **Empty State**: Educational. Includes an icon, clear message ("No Scenarios Generated"), and a primary action button ("Generate Scenario").
*   **Loading Skeleton**: Contextual shapes matching the incoming content (tables, cards) rather than full-page spinners to reduce perceived load time.

### Data Visualization & Tables
*   **KPI Card**: Value (monospace), Label, Trend (Arrow up/down), Unit (e.g., $, crews), and Comparison Delta vs Baseline.
*   **Metric Card**: Compact version for grid displays and dense dashboard views.
*   **Data Table**: 
    *   Sortable columns, filterable via headers.
    *   Responsive horizontal scroll for mobile/tablet.
    *   Monospace formatting for all numerical columns.
    *   Sticky headers and first column for wide tables.
*   **Chart Container**: Standardized wrapper for Plotly/D3 charts. Includes title, clear axes labels/units, legend, tooltips, and an accessible data-table alternative toggle.
*   **Timeline Component**: Vertical/Horizontal progression for Cascade domino effects or Draft event chronologies.

### Forms & Configuration
*   **Configuration Field**: Label, value input, explicit type indicator (e.g., `[Int]`, `[Float]`, `[Enum]`), description tooltip (for SME context), and inline validation on blur.
*   **Parameter Group**: Collapsible sections for logical grouping (e.g., "Legality L0-L8", "Cost Config") with a count badge of modified parameters.
*   **Validation Message**: Explicit inline text below the field, preserving input on error.

### Specialized Components
*   **Log Viewer**: Monospace, timestamped lines, auto-scrolling (with manual override), text filter/search, and level highlighting (INFO, WARN, ERROR).
*   **Comparison Row**: Side-by-side diff highlighting for comparing two Policies (e.g., R4 vs R6 grids).
*   **Provenance Chain**: Linked metadata cards showing lineage (e.g., Report -> derives from -> Run X -> derives from -> Config Y + Scenario Z).

## 3. Accessibility Standards (WCAG 2.2 AA)

*   **Semantic HTML**: Proper use of `<nav>`, `<main>`, `<article>`, `<section>`, and sequential heading hierarchy (`h1` -> `h2` -> `h3`).
*   **Keyboard Navigation**: All interactive elements must be focusable. No keyboard traps. Logical tab order (left-to-right, top-to-bottom). Focus rings must be highly visible (e.g., 2px solid primary color with offset).
*   **ARIA Usage**: 
    *   Use `aria-live="polite"` for background job status updates.
    *   Use `aria-expanded` on collapsible parameter groups.
    *   Use `role="alert"` for form validation errors and critical system failures.
*   **Color Contrast**: Minimum contrast ratio of 4.5:1 for normal text and 3:1 for large text and UI components (charts included).
*   **Chart Accessibility**: Every chart must have a `<canvas>` fallback or a visually hidden data table. Data points must not rely solely on color (use varied markers or dash patterns for lines).

## 4. Responsive Breakpoints

*   **Desktop (≥1280px)**: Full expanded sidebar. Multi-column layouts (e.g., Config form left, live preview right). High-density tables without horizontal scrolling.
*   **Laptop (≥1024px)**: Narrower sidebar or collapsible to icons. Slight reduction in padding. 
*   **Tablet (≥768px)**: Sidebar converts to a hidden Navigation Drawer (hamburger menu). Layouts stack to single or two columns. Tables may require horizontal scroll.
*   **Mobile (<768px)**: Compact header. Single column everything. KPI cards stack vertically. Deeply nested tables converted to card-lists or require horizontal swipe with sticky first column.

## 5. Pattern Library

*   **Long-Running Operations**: (The Operation Model). User triggers action -> Server returns Job ID immediately -> UI transitions to Job View -> Subscribes to SSE/polling -> Displays Progress Indicator + Log Viewer -> On completion, displays "View Results" CTA.
*   **Drill-down**: Summary (Total E[C]) -> Metric (Cost by Base) -> Event (Specific draft instance) -> Raw (SimPy ledger entry).
*   **Configuration Editing**: Preserves previous state. Indicates "dirty" (unsaved) fields visually. Supports JSON import/export as a fallback.
*   **Errors**: Always follow the triad: What happened (Simulation Failed), Why (Legality Rule L3 violated in Scenario 4), What next (Edit Config or View Detailed Logs).

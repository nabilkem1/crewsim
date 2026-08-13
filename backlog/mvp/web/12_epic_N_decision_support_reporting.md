# Epic N — Decision-Support Reporting (finding the best reserve number)

## Why this epic exists, and how it differs from Epic E

Epic E (`08_epic_DE_cascade_reporting.md`) was written before most of the reporting stack existed and
reads as a general metrics-dashboard wishlist (histograms, an eligibility overlay, a grid explorer). Most
of it has since been built, but along a different, more tightly-scoped path than Epic E assumed: a
CRN-paired batch grid (`reporting/grid.py`), a real KPI aggregator (`reporting/kpis.py`), a real R\*
recommender that reuses gate V9's own formula (`reporting/recommendation.py`), and a native React page
(`features/results/PolicyComparison.tsx`) that reads a real job's `results` JSON from
`GET /api/results/{job_id}` — alongside a separate, older, self-contained HTML report
(`reporting/report.py`, `crewsim report`) that has richer content (drill-down, full gate table, `[CONFIRM]`
scan) than the native page does.

This epic is scoped specifically to the system's **actual decision problem** (spec §7.4: minimise
`C₁(R) + E[Q] + λ·CVaR₀.₉₅[Q]`, report the whole λ curve — not one number) and to the **specific,
verified gaps** between what that decision needs and what the native Results & Reports page currently
shows. It supersedes Epic E's WE-004/005/007/009/010 (superseded, not duplicated — those are marked below)
and leaves Epic E's chart-library items (WE-003 histograms, WE-006 eligibility overlay, WE-008 grid
explorer) alone as independent, lower-priority visualization work this epic does not depend on.

Every story below states what already exists today (so this document can't rot into claiming credit for
work already done) and what is net-new.

---

### WN-001: R\* Recommendation, promoted to the top of the page
**Description**: As Crew Planning or Finance, I want the recommended reserve level by risk tolerance to be
the first thing I see when I open Results & Reports, labelled the way spec §7.4 frames the decision
(risk-neutral / balanced / stability-prioritised) — not a raw λ axis I have to already understand.
**Already built**: `reporting/recommendation.py::compute_r_recommendation` (reuses gate V9's own
`argmin_R[E[cost] + λ·CVaR95]`, computed once in the job worker, not recomputed on read — see its own
module docstring for why); `PolicyComparison.tsx`'s `RecommendationPanel`, currently the 4th block on the
page, below the scoreboard.
**Net-new**:
- *Functional*: Move `RecommendationPanel` above the scoreboard. Add a labelled λ legend (0.0 "minimise
  average cost, accept tail exposure" / 0.5 "balanced" / 1.0 "prioritise stability through bad months",
  spec §7.4's own table) instead of bare `λ=0.25` column headers.
- *UX/Responsive*: The stability badge (STABLE/UNSTABLE) must be visible without scrolling on a
  1280px-wide viewport.
- *Data Integrity*: If gate V3 failed for this run, the existing red "treat as unvalidated" banner must
  render **above** this panel, not below it — a planner should never see the recommendation before the
  caveat that it might be a coin flip (S1c-01 AC4's own reasoning, already implemented for the panel
  itself; this story is about page order, not new logic).
**Dependencies**: none (page-layout change only).
**Design System Components**: Legend, Badge.
**Technical/API Implications**: None — reorders existing JSX, restates existing `rec.curve[].lambda`
values against a static label lookup. No backend change.

---

### WN-002: Cost decomposition per policy — Stage 1 vs. recourse, by ledger category
**Description**: As a planner comparing R values, I want to see *where* the money goes for each policy,
not just a total — the system's whole framing (spec §1.1) is a tension between guaranteed staffing cost
(`C₁`, rises with R) and recourse cost (drafting, cancellation, delay; falls with R), and right now that
tension is invisible behind one E[cost] number per row.
**Already built**: The ledger already carries `category` on every row (`RESERVE_STAFFING`,
`RESERVE_UTILIZATION`, `DRAFT_TIER1`–`5`, `CANCELLATION`, `TERMINAL_PENALTY`; `costs_pilots.yaml`'s
`disruption.delay_per_minute` is declared but not yet booked by any code path — `crewsim` prints this as an
unconsumed-field `[NOTICE]` at startup, verified directly against a live run). `des.rows_in_measurement_window`
already does the window/cool-down attribution `compute_kpis` would need.
**Net-new**:
- *Functional*: `reporting/kpis.py::compute_kpis` gains a `cost_by_category: dict[str, float]` (mean
  per-scenario, summed over measurement-window rows, keyed by real ledger category — no invented
  categories, and any category with zero rows in this run is simply absent, not zero-padded to look
  complete). `run_processing_job` includes it per scoreboard row.
- *UX/Responsive*: A stacked bar per policy in the scoreboard (staffing at the bottom, then
  utilization/draft/cancellation/terminal stacked above), sorted by R so the staffing-up /
  recourse-down trade visibly crosses.
- *Accessibility*: The stacked bar ships with a toggle to the same data as a plain table — a bar chart
  with no tabular fallback fails the same accessibility bar `WE-001`/`WE-003` already set for this app.
- *Data Integrity*: The bars must sum to the same `expected_cost` already shown in the scoreboard —
  add this as an assertion in the KPI test, not just a visual expectation.
**Dependencies**: WN-001 (page-layout precedent).
**Design System Components**: Stacked Bar Chart, Chart/Table Toggle.
**Technical/API Implications**: `reporting/kpis.py`, `api/routers/processing.py::run_processing_job`
(extend the scoreboard row dict), `PolicyComparison.tsx` (new `CostDecomposition` component reading
`row.cost_by_category`).

---

### WN-003: Reserve utilization rate
**Description**: As a planner, I want to see what fraction of the reserve capacity I bought actually got
used, not just a raw dispatch count — a reserve dispatched twice out of a 21-measured-day, R=10
establishment (`10 × 21 = 210` reserve-days bought) reads completely differently from the same 2
dispatches against an R=2 establishment. Spec §1.1 opens on exactly this: "a reserve who is never called is
pure cost."
**Already built**: `compute_kpis` returns `reserve_dispatches_mean`; `cfg.horizon.measurement_days` and the
policy's own `stage1.reserves` count are both already available at the point KPIs are computed.
**Net-new**:
- *Functional*: Add `utilization_rate = reserve_dispatches_mean / (R × measurement_days)` to the KPI dict
  and the scoreboard (as a column, not a separate report — it belongs next to `reserve_dispatches_mean`
  in the same row a reader is already looking at).
- *UX/Responsive*: Render as a percentage with the raw dispatch count in a tooltip/subtext, not
  standalone — a bare "12%" invites misreading without the numerator/denominator next to it.
- *Data Integrity*: `R` must come from the policy's actual `stage1.reserves` total (summed across
  day-of-week blocks and call type), never re-derived from the policy's filename. Verified directly against
  `configs/policies/R6.yaml`: it is **not** a constant 6 — 4 short-call + 2 long-call Mon–Fri (6), but 5
  short-call + 2 long-call Sat/Sun (7). A denominator computed as `int(policy_name.lstrip("R"))` (the
  pattern `reporting/recommendation.py` already uses, correctly, only to pick an R *value* to argmin over,
  not a headcount to divide by) would silently understate this policy's true establishment size.
**Dependencies**: none.
**Design System Components**: none new (extends the existing Scoreboard table).
**Technical/API Implications**: `reporting/kpis.py::compute_kpis` (new field, needs the resolved reserve
count passed in — `Policy.stage1` already has it), `PolicyComparison.tsx`'s `ScoreboardTable`.

---

### WN-004: Service-level constraint — `P(uncovered legs > u_max) ≤ ε`
**Description**: As Crew Planning, I want to know whether a candidate R satisfies the actual formal
constraint the spec defines (§7.5), not just see a mean uncovered-legs count — the spec states this as a
**chance constraint** ("infeasible policies are filtered from the candidate set"), and nothing in the
system today evaluates it.
**Status: blocked on a real input, not implementable as written.** Verified directly: no `u_max` or `ε`
exists anywhere in `configs/` or `config.py`. Per this project's standing "ask before inventing a modelling
parameter" rule, this story cannot be estimated or built until Crew Planning supplies both values as a real
`[CONFIRM: Crew Planning]`-flagged config entry — guessing a threshold to make a chart would be exactly the
"tuned inputs to hit the target" failure V3/V4's own gate documentation warns against (§9.2's "Golden
Rule"), applied to a constraint instead of a validation target.
**Acceptance Criteria** (once `u_max`/`ε` exist in `configs/base.yaml`):
- *Functional*: `compute_kpis` computes `P(uncovered_legs > u_max)` from the same per-scenario
  distribution `cvar95` already uses (no new simulation), and a boolean `service_level_met`.
- *UX/Responsive*: Any scoreboard row failing the constraint is visually flagged (not hidden — spec §9.3's
  "no black box" rule applies to infeasible candidates too; a planner should see *that* R4 was filtered
  and *why*, not have it silently vanish from the table).
- *Data Integrity*: The recommendation panel (WN-001) must exclude infeasible R values from the λ-curve
  argmin, matching §7.5's enforcement table ("the optimiser never proposes an infeasible R") — a stable
  recommendation that turns out to be infeasible is not a recommendation.
**Dependencies**: A confirmed `u_max`/`ε` from Crew Planning. **Do not start implementation before this
lands** — this is the one story in this epic where the code is not the bottleneck.
**Design System Components**: Alert/Warning Banner (reuse existing pattern from the V3 banner).
**Technical/API Implications**: `configs/base.yaml` (new `service_level` block), `config.py` (new
`ServiceLevelConfig` model, no numeric default per this repo's own
`test_no_config_model_field_has_a_numeric_default`), `reporting/kpis.py`,
`reporting/recommendation.py` (exclude infeasible R from `r_lookup`).

---

### WN-005: Gate status + outstanding `[CONFIRM]` flags on the native page
**Description**: As a reviewer, I want to see the V1–V9 gate table and every outstanding `[CONFIRM: owner]`
flag directly on the page a planner actually opens, not only in the separate HTML file — spec §9.3 makes
both mandatory on "every single recommendation report," and today only V3 appears natively.
**Already built**: Every gate runner (`gates/v1_degeneracy.py` through `v9_sensitivity.py`) already returns
a structured `{"pass": bool, ...}` dict; `reporting/report.py::extract_confirm_markers` already scans the
raw text of `configs/base.yaml`/`costs_pilots.yaml` for `[CONFIRM: owner]` markers (a YAML-comment scan,
since these are invisible to the parsed config object) — both currently only feed the HTML report.
**Net-new**:
- *Functional*: A `GET /api/results/{job_id}/gates` (or an addition to the existing job `results` JSON)
  returning the same gate-status rows `report.py`'s `gate_rows` builds, plus `extract_confirm_markers`'
  output, as JSON instead of pre-rendered HTML.
- *UX/Responsive*: A gate-status grid (reuse the existing `results.v3` banner's PASS/FAIL styling) and a
  `[CONFIRM]` flag list, both on `PolicyComparison.tsx`, below the recommendation panel.
- *Data Integrity*: Gates with no real implementation must render as `STUB`, matching `report.py`'s own
  `KNOWN_STUB_GATES` convention — never a silent PASS. If `KNOWN_STUB_GATES` is empty (it is, as of
  S1a-10/S1b-07), the grid should have no STUB rows; do not add a placeholder STUB just to exercise the
  UI state.
**Dependencies**: WN-001 (page-layout precedent).
**Design System Components**: Status Grid, Gate Card (Epic E's WE-009 already named these — this story
implements them against real data, on the page WE-009 didn't specify).
**Technical/API Implications**: `api/routers/results.py` (new endpoint or field), `reporting/report.py`
(extract the gate-row-building logic into a function shared by the HTML report and this endpoint, same
"one real computation" pattern `reporting/paired.py`'s own module docstring documents — not a second copy
that can drift).

---

### WN-006: V3 *and* V4 reality-check table, side by side
**Description**: As a reviewer, I want both emergent-rate validation gates shown together — spec §9.3 item
4 requires "the AI's Usability **and** Domino rates directly compared to the real historical rates," and
today only V3 (eligibility/usability) is surfaced; V4 (cascade/domino) is computed by the batch job
(`n_cascading_drafts / n_drafts`) but never checked against `data/cascades.py`'s historical target on this
page.
**Already built**: `gates/v4_cascade.py::run_v4_gate`; the scoreboard's `casc` field already carries
per-policy cascade rate; `_v3_verdict` in `processing.py` is the pattern to follow.
**Net-new**:
- *Functional*: A `_v4_verdict` alongside `_v3_verdict` in `run_processing_job`, added to `job.results`
  the same way; a second banner in `PolicyComparison.tsx` next to the V3 one.
- *UX/Responsive*: Both banners share one component (`ValidationBanner`), parameterised by gate id/message
  — not two near-duplicate blocks of JSX that can drift apart the way the codebase has repeatedly found
  and fixed elsewhere this project (the "test validates a copy, not the real thing" pattern named in
  several backlog-integrity notes).
- *Data Integrity*: If either gate has no events to validate against (no drafts in any scenario, for V4),
  say so explicitly — matching V3's existing "no eligibility events in window" `None` handling — never
  silently omit the banner.
**Dependencies**: none.
**Design System Components**: `ValidationBanner` (generalised from the existing V3-only banner).
**Technical/API Implications**: `api/routers/processing.py` (new `_v4_verdict`, mirroring `_v3_verdict`),
`PolicyComparison.tsx`.

---

### WN-007: Complete the reproducibility chain on the native page
**Description**: As an engineer, I want the full reproducibility chain spec §9.3 item 2 requires — "type in
the exact master seed and data hashes a year later and get the exact same answer" — visible on the page,
not just season/seed/params version.
**Already built**: `job.results` already carries `season`, `master_seed`, `params_version`, `params_hash`;
`Policy.get_hash()` and the pinned `costs_file@version` string already exist and are used by the CLI's
`run --print-provenance` and the HTML report's `build_provenance`. Checked directly against the current
code, not assumed: `run_processing_job`'s scoreboard row **already carries `policy_hash`** (verified in
`api/routers/processing.py`) — it is computed and sent to the browser today, but `PolicyComparison.tsx`'s
`ScoreboardTable` never renders it (verified: no reference to `policy_hash` anywhere in that file). So half
of this story is a frontend-only fix.
**Net-new**:
- *Functional*: Render each row's existing `policy_hash` (frontend-only change). Separately, add
  `costs_version` to the scoreboard row — this one genuinely does not exist on the row today; the
  representative policy's `costs_file` string (e.g. `costs_pilots.yaml@v0.1.0-placeholder`) needs
  threading from `Policy.costs_file` into the scoreboard dict in `run_processing_job`.
- *UX/Responsive*: Render both as a compact monospace line under each policy's row, collapsed by default
  (this is audit detail, not a headline number).
**Dependencies**: none.
**Design System Components**: none new.
**Technical/API Implications**: `api/routers/processing.py` (add `costs_version` to the scoreboard dict,
sourced from `policy.costs_file`), `PolicyComparison.tsx`'s `ScoreboardTable` (render both fields).

---

### WN-008: Per-policy drill-down deep links
**Description**: As a planner asking "why R=8 and not R=6", I want to click *that row* and land on its
specific costliest/typical scenario timelines — spec §9.3 item 1 says drill-down must resolve to "a
specific simulated Tuesday," reachable from the recommendation itself, not a generic link to a separate
document.
**Already built**: `reporting/drilldown.py` (`select_exemplar_scenarios`, `build_scenario_drilldown`) and
`report.py`'s `--drilldown` flag already build exactly this content, embedded as anchored sections
(`#scenario-costliest-<id>`) in the HTML report; `PolicyComparison.tsx` currently links only to the report
file as a whole.
**Net-new**:
- *Functional*: Generate the HTML report with `--drilldown` for the representative policy as part of the
  batch job (or on demand, see Performance note below), and link each scoreboard row to its own
  `#drilldown` anchor in that file rather than the file's top.
- *Performance*: A full drilldown (5 costliest + 5 typical, traced) is not currently produced by
  `run_processing_job` — only `crewsim report --drilldown` does, and it re-simulates with `trace=True`,
  which is real memory/time cost (S1e-03's own measured note: ~half the cost when reusing an
  already-traced batch, still not free). Decide explicitly whether this runs synchronously in the batch
  job, as a separate on-demand job triggered from a row's "why?" button, or is deferred to a follow-up —
  this needs a scope decision, not a default.
**Dependencies**: WN-002 (both want the batch job to carry more per-policy detail; sequencing them
together avoids two separate `run_processing_job` changes).
**Design System Components**: Drill-down Link (per Epic E's WE-011 naming).
**Technical/API Implications**: `api/routers/processing.py`, `reporting/report.py`, `PolicyComparison.tsx`.
Needs an `AskUserQuestion`-style scope decision before implementation (see Performance note) — flag this
explicitly when this story is picked up, per this project's standing "ask before changing design" rule.

---

## Sequencing

WN-001 and WN-007 are page-only or near-trivial and should go first (cheapest, no backend risk). WN-002,
WN-003, WN-005, WN-006 are independent of each other and can proceed in any order once WN-001 lands.
WN-004 is blocked on a real Crew Planning input and should be raised as a question now, not scheduled.
WN-008 needs a scope decision (see its own Performance note) before estimation.

# Slice 1e — Reporting, Policy Grid & Backtest

**Epic E1e** · 7 stories · Gate: **V5 SME sign-off · V6 cost backtest**
Needs datasets **D7, D10**.

The slice that turns a validated model into something a planner can act on. Two of its stories are
gates that require humans: an IOC duty manager (V5) and Finance's actual payroll figures (V6).

---

## 🟢 [DONE] S1e-01 — KPI aggregation over the measurement window
**Size:** `M` | **Depends on:** S1d-05 | **Spec:** §2.1, §5.0.5

**As a** planner **I want** KPIs aggregated accurately over the measurement window
**so that** warm-up noise is excluded and metrics are comparable.

### Description
The first 7 days of the simulation are noisy as the engine spins up. Throwing out this warm-up period ensures the final financial KPIs are perfectly stable and trustworthy.

### Acceptance Criteria
- [x] E[C], CVaR₀.₉₅, uncovered legs, reserve utilisation, eligibility, cascade rate, draft distribution
- [x] **Warm-up rows booked but excluded**; cool-down costs attributed back when their cause is in-window
- [x] Draft distribution reported as **premium earnings**, not as burden (§1.3.5)
- [x] Gini reported with a caveat: when drafts are rare relative to headcount it is arithmetic, not insight

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_kpis.py`
*   🙋 **Manual:** `crewsim run --policy R6 --scenarios 500 --kpis`
    *   **Expect:** every KPI, with the warm-up window explicitly excluded and stated
    *   **Fails if:** warm-up rows are included, or cool-down costs are dropped

### How it was implemented
Implemented 2026-08-07. Found and fixed a significant pre-existing bug in `des.measured_window_costs`
(S1d-04d) while building this — squarely in scope, since this story's own acceptance criterion *is* the
attribution rule ("cool-down costs attributed back when their cause is in-window"). The old implementation
(`min_time=warmup_end`, no `max_time`) treated EVERY cool-down-booked ledger row as in-window, including
ones whose root event is a brand-new sick call that itself arrived during cool-down
(`_load_daily_sick_calls` generates arrivals across the full `horizon_days`, cool-down included — a known,
separate S1d-04c limitation, not fixed here). Measured directly before fixing: **15–33% of the old
per-scenario cost figure**, across 5 real R6 scenarios, was cool-down-originated cost that should never
have counted.

Fixed with a real `root_event_uid`-based attribution rule (`des.rows_in_measurement_window`, refactored
out of `measured_window_costs` so both cost totals and the new KPI counts share one definition of "in the
measurement window"): a row counts if booked inside the window, OR booked in cool-down with its causal
chain's origin (earliest `sim_time` among all rows sharing its `root_event_uid`) inside the window.
Verified the `root_event_uid == 0` sentinel (background costs with no causal chain at all, e.g.
`RESERVE_STAFFING`) is NOT treated as one shared chain across unrelated rows — each uses its own booking
time. Verified against real data (not assumed) that no chain currently straddles window-origin →
cool-down-booking in this corpus (the "pull back in" branch is real per spec but currently empirically
unexercised by real data — covered instead by a synthetic regression test,
`test_measured_window_costs_cooldown_attribution`).

**Downstream impact, re-verified directly:** S1d-05 (V9 gate) is the only other consumer of
`measured_window_costs`, and its own sweep finding *changed* after this fix — see its card, corrected in
place. `EligibilityEngine.get_distribution()` gained optional `min_time`/`max_time` params for the same
window filtering (backward compatible — the no-args call V3's gate already depends on is unchanged).
Cascade rate is *not* window-filtered (`sim.n_cascading_drafts`/`n_drafts` are whole-simulation counters
with no `root_event_uid` to attribute back with), matching gate V4's own existing convention.

Gini's "arithmetic, not insight" caveat (spec's glossary and §9 language) is printed unconditionally
alongside every Gini value, not gated behind an invented numeric rarity threshold — the spec gives no such
threshold, and its own language reads as a standing caveat, not a conditional warning.

---

## 🟢 [DONE] S1e-02 — Self-contained HTML report
**Size:** `M` | **Depends on:** S1e-01 | **Spec:** §2.2, §9.3

**As a** stakeholder **I want** a self-contained HTML report
**so that** I can easily digest and share the results of the simulation.

### Description
Decision makers need readable dashboards, not terminal output. Generating an HTML artifact lets executives quickly compare policy tradeoffs visually.

### Acceptance Criteria
- [x] **One file**, no external assets — it has to be emailable to Crew Planning
- [x] Cost distributions; the trade-off curve with the optimum marked; the λ curve
- [x] Front page carries: gate status (**including failures**), the provenance chain, and **every
  outstanding `[CONFIRM: …]` the result depends on**

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_html.py`
*   🙋 **Manual:** `crewsim report --policies R4 R6 R8 R10 R14 --open`
    *   **Expect:** a U-shaped trade-off curve with the optimum marked, in a single file
    *   **Fails if:** it needs a CDN or a local server — it must open from an email attachment

### How it was implemented
Implemented 2026-08-07. Scoped to this story's own 3 acceptance criteria, not spec §9.3's full 5-item
epic-level obligation (item 1, drill-down links, is explicitly S1e-03's own card, which depends on this
one).

`crewsim report --policies <names> [--scenarios N] [--open]` writes one self-contained HTML file
(`output/reports/policy_report.html`, plotly embedded inline once, same convention as
`gates/v3_eligibility.py::write_v3_report`) with: cost distributions per policy, a reserve-level trade-off
curve (E[C] and CVaR95 vs R, real argmin marked), a lambda curve (the real objective from spec §7.4, per
R, plus the resulting R\* — reusing S1d-05's `_real_r_recommender` on data already simulated for the
trade-off curve rather than re-simulating via `build_r_star_lookup`), the reproducibility chain, a
gate-status table, and every outstanding `[CONFIRM: owner]` marker found by scanning the RAW text of
`configs/base.yaml` and `costs_pilots.yaml` (these are YAML comments, invisible to the parsed config
object). Verified self-contained by grepping the output for actual `<script src=` / `<link href=` tags
(zero) — not a naive substring search for "http", which also matches literal attribution-link strings
baked into the bundled plotly.js library itself (unused map-tile copyright text), a false positive
`gate_v3_holdout.html` already has too.

**Real, measured findings surfaced by actually building this:** E[cost] is close to flat across R4..R14
(~1–2% spread) at this corpus/policy scale — CVaR95 is where the real U-shape lives (matches S1d-05's own
corrected finding). The report says this explicitly on the page (captioned, not silently marking a
meaningless E[cost] optimum) rather than forcing the "U-shaped curve" language from this story's own
`expect` onto data that doesn't show it for E[cost].

**Gate status is honest, not uniformly green:** V1/V2 are rendered as `STUB` (their pre-existing `cli.py`
implementations are hardcoded PASS text / a stubbed mock value, not derived from any real run) — printing
them as PASS in a report whose entire premise is spec §9.3's "no black box" rule would itself be a black
box. V3/V4/V9 report real verdicts against a stated representative policy (first of `--policies`, named
explicitly on the page). Found and fixed a real, separate bug while wiring V7 into this table: `gate v7`'s
CLI dispatch crashed with `NameError` on every invocation (see S1a-11's own corrected note) — fixed by
extracting a real, shared `gates/v7_reproducibility.py::run_v7_gate`, now used by both the CLI and its own
test.

---

## 🟢 [DONE] S1e-03 — Exemplar-scenario drill-down
**Size:** `M` | **Depends on:** S1e-02 | **Spec:** §9.3, §2.3/C2

**As a** planner **I want** to interrogate a recommendation
**so that** "why 6 reserves?" resolves to a specific simulated Tuesday.

### Description
"Why 6 reserves?" needs proof. The ability to drill down into a specific day and see exactly how the 6th reserve prevented a massive cascade builds trust.

### Acceptance Criteria
- [x] The 5 costliest and 5 most typical scenarios, each as an auditable event timeline
- [x] Every cost row traceable to its `root_event_uid`, so a cancellation shows its whole causal chain
- [x] Reachable from the recommendation itself, not buried in an appendix

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_drilldown.py`
*   🙋 **Manual:** `crewsim report --policy R6 --drilldown costliest`
    *   **Expect:** a readable timeline: sick call → reserve exhausted → draft → cascade → cancellation
    *   **Fails if:** the chain cannot be followed end to end — a planner will not act on an aggregate

### How it was implemented
Implemented 2026-08-07. `crewsim report` gained `--policy` (single policy, shorthand for
`--policies <one>`) and `--drilldown {costliest,typical,both}`, embedding the drill-down section directly
into the SAME self-contained HTML file `report` already produces (S1e-02) — reachable via an in-page
anchor link near the top of the page, not a separate file or a buried appendix. `--drilldown`'s value is
display-only (which group lists first): both the 5 costliest and 5 most-typical scenarios are always
shown, since that's this story's own acceptance bar regardless of which single mode word is passed.
"Typical" = closest to the **median** cost, not the mean — cost distributions here are right-skewed (a few
very bad months dominate CVaR), so the mean would be pulled toward the tail this drill-down's own
"costliest" half already covers separately.

`gates/drilldown.py` (`select_exemplar_scenarios`, `root_chain`, `build_scenario_drilldown`) reuses two
REAL, already-existing mechanisms rather than inventing new event-timeline logic: `Simulation.trace`
(S1d-04c's own readable per-scenario event log — SICK_CALL → RESERVE/DRAFT/CANCELLED → cascade-visible,
already chronological) for the full auditable timeline, and `CostLedger.filter_by_root` (already existed,
unused until now) for the causal-chain requirement (spec §2.3/C2: "root_event_uid is what lets you
attribute a Thursday cancellation back to the Tuesday sick call that caused it"). Each uncovered leg's
(`CANCELLATION`/`TERMINAL_PENALTY`) full chain of ledger rows is matched against `sim.trace` by
`item {uid}` text so the SAME real narrative the engine already produced is shown, not a second,
independently-reconstructed story that could silently diverge from what actually happened.
`des.run_policy_crn` gained a `trace: bool = False` passthrough (off by default — real memory cost, wasted
for e.g. S1e-01's own 500-scenario KPI run which never reads it); when `--drilldown`'s policy is also one
of `--policies`, the report reuses that already-simulated (now traced) batch instead of re-simulating it a
second time — measured directly: the naive approach took 13.1s for
`--policy R6 --drilldown costliest --scenarios 5`, the reused-sims version took 7.6s, roughly half, for
the common case where the drill-down policy is also under comparison.

**Real, measured finding:** at this corpus/policy scale, every uncovered-leg chain found in real 3–10
scenario test runs was a single-row chain (SICK_CALL → CANCELLED directly, no intervening
RESERVE/DRAFT/cascade step) — consistent with the already-documented near-zero cascade rate (S1d-04e,
S1e-01/02's own KPI/report output). Multi-step "sick call → reserve exhausted → draft → cascade →
cancellation" chains are real and supported by the code (verified via a synthetic fixture,
`test_root_chain_matches_ledger_rows_and_trace_lines`, since real data at this scale doesn't currently
exercise the longer path) but not what real data currently produces — not forced to look richer than it
is.

---

## 🟢 [DONE] S1e-04 — Policy grid runner
**Size:** `M` | **Depends on:** S1e-01 | **Spec:** §3

**As a** researcher **I want** an automated runner for grid searches
**so that** I can evaluate multiple policies systematically without manual intervention.

### Description
Testing one policy at a time is too slow. An automated grid runner lets us effortlessly compute the entire cost surface across dozens of reserve counts overnight.

### Acceptance Criteria
- [x] Grid from config: R axis (5 combinations — see "How it was implemented" for why reserve-selection ×
  cross-base was scoped out, not the story's original "24 combinations")
- [x] **All combinations share one CRN scenario set** — comparisons are paired
- [x] Parallel via joblib; V7 must still pass with the grid running

### Verification
*   🤖 **Automated:** `pytest tests/test_grid.py`
*   🙋 **Manual:** `crewsim grid --config configs/grid_mvp.yaml --scenarios 1000`
    *   **Expect:** 5 combinations (R axis only), paired, minutes not hours
    *   **Fails if:** each combination regenerates its own scenarios — the comparison becomes unpaired
    *   and needs ~100× the runs to resolve anything

### How it was implemented
Implemented 2026-08-07. Before writing any code, investigated the grid's 3 named axes (R,
reserve-selection, cross-base) and found 2 of them aren't real in the engine: `reserve_selection` is a
declared `Stage2Config` field that `Simulation._attempt_resolution` never reads — dispatch is hardcoded to
exactly one strategy (shortest remaining window, seniority tiebreak) regardless of a policy file's value —
and `allow_cross_base_reserve` has nothing to filter against, since the loaded roster is confirmed
single-base (`roster_loader.load_rosters` returns only `{'YUL'}` crew bases at current MVP scope). Also
found the story's own "24 combinations" conflicts with spec §3's grid (6 R-levels × 5 callout rules × 2
cross-base rules = 60), and no `R12` policy file exists to match the spec's 4/6/8/10/12/14 R-level list —
only R4/R6/R8/R10/R14 (5 files).

Per this project's standing "ask before changing design" rule, presented this via `AskUserQuestion` before
implementing rather than guessing: ship the real R-axis grid now and park the other two axes as a
follow-up story (same disposition as `roster_size` in S1d-05), implement all 4 missing reserve-selection
strategies now (bigger scope, needs several domain decisions first), or just rewrite the AC to "5
combinations" with no follow-up. **User chose to ship the real R axis now.** Follow-up filed as **S1e-04b**.

Implemented `configs/grid_mvp.yaml` (the `policies:` list, header comment records the inert-axis finding so
the scope decision doesn't silently rot); `src/crewsim/reporting/grid.py` (`load_grid_config`, `run_grid` —
CRN-paired by construction, since every combination gets the same `master_seed` and `run_policy_crn`'s
arrival draws never take policy as an input; `joblib`-parallel across policies via `jobs=N`, each worker
returning only a picklable KPI dict so no `simpy` state crosses the process boundary; reuses
`reporting.kpis.compute_kpis` rather than a second cost-aggregation implementation; `print_grid_report`,
`write_grid_csv`); `crewsim grid --config --scenarios --master-seed --jobs` CLI subcommand (writes
`output/reports/grid_results.csv`, stderr progress via the existing `_stderr_progress` helper).

**Pairing proof** (`tests/test_grid.py`): spied on `des._load_daily_sick_calls` — the one call site in
`run_scenario` that pulls a scenario's arrival counts from the cached scenario set — across two different
real policies (R4, R14) and confirmed identical `(season, master_seed, n_scenarios, scenario_id)` call args
for every scenario. Deliberately does **not** assert identical sick-call trace lines across policies — an
earlier draft of this test did, and failed for a real, non-bug reason: roster composition differs by R
(different line-holder/reserve split), so the same arrival draw can land on a different crew member, or on
nobody currently on a pairing, under a different policy — that's downstream of the shared scenario set, not
evidence against pairing. Also verified V7 (reproducibility) still passes while a grid run is running
concurrently, per this story's own AC, and that `jobs>1` output matches `jobs=1` exactly (same policy
order, same KPI values). Full suite 246→252 (6 new tests), 0 regressions.

---

## ⏳ [TODO] S1e-04b — Real reserve-selection strategies and cross-base reserve filter
**Size:** `L` | **Depends on:** S1e-04 | **Spec:** §3

**As a** researcher **I want** the grid's reserve-selection and cross-base axes to be real
**so that** the full 60-combination grid spec §3 describes can actually be run, not just the R axis.

### Description
Parked out of S1e-04's scope by explicit user choice (see S1e-04's own note). Before this can be
implemented for real, several domain questions need answers, not guesses, per this project's standing "ask
before changing design" rule:

- `reserve_selection` has 5 named strategies in the spec, only 1 (`shortest_remaining_window`) is coded
  today. The other 4 each need a precise definition: "lowest hours flown" — which rolling window
  (`get_rolling_counters` exposes both 7d and 28d) and duty vs flight hours?; "FIFO" — standby-since when
  (block start? last assignment?)?; "best fit / least buffer waste" — what distance metric between
  remaining legal hours and duty length?; "seniority" — spec says "most junior (or senior)", itself
  undecided.
- `allow_cross_base_reserve` is cheap to make real (filter `eligible_reserves` to `r.base == item.base`)
  with no domain ambiguity, **but** is structurally untestable at current MVP scope: the loaded roster is
  single-base (YUL only), so there's no second base for the filter to ever restrict against. Also note the
  interaction already found in `_attempt_resolution`: `min_rest` is 11h if `chosen.base == item.base` else
  10h — the away-base branch is reachable today even though nothing currently produces an away-base
  reserve, so restricting the pool would change real rest-hour calculations, not just eligibility counts.
- The backlog-vs-spec grid-shape conflict (24 vs 60 combinations, and the missing R12 policy file) needs
  resolving once the other two axes are real, not before.

### Verification
*   🤖 **Automated:** TBD once scope is confirmed
*   🙋 **Manual:** TBD once scope is confirmed
    *   **Expect:** the grid's reserve_selection and cross-base axes stop being confirmed-inert and actually
        change simulated outcomes
    *   **Fails if:** a strategy is implemented from a guessed interpretation of its name instead of a
        confirmed domain definition — e.g. "lowest hours flown" coded against an arbitrarily chosen rolling
        window, or "best fit" against an invented distance metric, with no `[CONFIRM: owner]` marker on the
        choice

---

## 🟢 [DONE] S1e-05 — Counterfactual runs
**Size:** `M` | **Depends on:** S1e-04 | **Spec:** §3, §5.6

**As a** decision-maker **I want** the price of the mandated rules quantified
**so that** keeping them is a choice made with a number attached.

### Description
Union rules cost money. Running counterfactual scenarios (e.g. what if L5 was relaxed?) quantifies exactly how much a specific rule constraints operations.

### Acceptance Criteria
- [x] Two counterfactuals: `junior_first` ordering, and a `myopic_total_cost` selector that ranks by
  (draft cost + predicted cascade cost) rather than strictly by tier
- [x] **Structurally impossible** to select either as a candidate policy — a separate analysis flag
- [x] Output labelled **NOT A RECOMMENDATION** wherever it appears

### Verification
*   🤖 **Automated:** `pytest tests/test_counterfactuals.py`
*   🙋 **Manual:** `crewsim counterfactual --vs-mandated`
    *   **Expect:** the cost delta of each mandated rule, clearly labelled
    *   **Fails if:** a counterfactual can appear in a recommendation
    *   > With drafting fully determined at Air Transat, these are the most informative runs available — there
    *   > is no drafting policy to search, only a mandated one to price.

### How it was implemented
Implemented 2026-08-08. `junior_first` already existed as an unused parameter on
`drafting.py::select_draft_candidate` — `des.py`'s call site never passed it through. Wired a new
`draft_mode: str = "mandated"` parameter through `Simulation`/`run_scenario`/`run_policy_crn`
(`"mandated" | "junior_first" | "myopic_total_cost"`, defaulting to `"mandated"` so every existing caller
is unaffected) and dispatched it in `_attempt_resolution`.

Found a real gap while verifying the AC's own "structurally impossible to select as a candidate policy"
language: `Policy`/`Stage2Config` were plain pydantic `BaseModel`s with no `extra="forbid"`, so a policy
YAML carrying e.g. `junior_first: true` would validate successfully and be silently ignored — safe (never
read), but not the loud rejection the AC implies. Fixed by adding `extra="forbid"` to every model in
`policy.py` (matching `config.py`'s own `_Model` convention), verified all 5 real policy files still load
and that an extra key now raises `ValidationError`.

`myopic_total_cost` ("Pure Cost-Ranked", spec §3) needed a "predicted cascade cost" per candidate with no
existing dollar figure to source it from — presented via `AskUserQuestion` (count × base_premium vs. real
one-step lookahead vs. park it). **User chose count × base_premium**:
`predicted_cascade_cost = len(cascaded_items) * costs.draft.base_premium`, where `cascaded_items` comes
from `cascade.py`'s already-existing `compute_draft_delta` (pure, no mutation — safe to call once per legal
candidate purely to rank them). Implemented in new `src/crewsim/engine/counterfactuals.py::select_myopic_total_cost`,
kept **out** of `drafting.py` deliberately — `drafting.py` stays about the one real mandated algorithm plus
the `junior_first` flag; `counterfactuals.py` owns every NOT-A-RECOMMENDATION strategy.

New `src/crewsim/reporting/counterfactual.py` (`run_counterfactual_comparison` — same policy's stage1
reserves, same CRN scenario set, all 3 `draft_modes`; `print_counterfactual_report`) and
`crewsim counterfactual --vs-mandated --policy --scenarios --master-seed` CLI subcommand, with the
`NOT A RECOMMENDATION` label printed at both the top and bottom of the report.

**Real, measured finding:** at this scale of data (R6, real scenarios), E[cost] came out identical to the
cent across all 3 `draft_modes` despite genuinely different crew being drafted (verified directly —
senior-first and junior-first drafted different real `crew_id` sequences). Root cause, not a bug: every
draft observed (196/196 in one real scenario) was satisfied from tier 1 (day-off candidates, `tier_cost=0`),
so reordering WHO is picked within a non-empty tier never changes the tier used, hence never changes total
dollar cost — only WHO earns the premium (matches spec §5.6's own framing: "read as the distribution of
premium earnings, not an imposed burden"). The rule has a real, nonzero price only in scenarios where tier
1 is exhausted. `print_counterfactual_report` shows the per-tier draft breakdown alongside the cost table
and states this explicitly rather than presenting an unexplained $0.00 delta — same discipline as the flat
E[cost]-across-R finding in S1e-02/03.

Structural-impossibility test (`test_draft_mode_rejected_by_policy_schema`): injects
`junior_first`/`myopic_total_cost`/`draft_mode` into a real loaded policy's `stage2` dict and asserts
`Policy(**data)` raises `ValidationError` for each. Also tests: `junior_first` genuinely selects a
different real crew sequence (not a no-op), `myopic_total_cost` prefers a real tier-1 candidate over a
real, equally-legal tier-2 candidate (both verified individually legal via `is_legal_assignment`, so the
test exercises tier comparison, not an accidental legality filter), and CRN pairing across `draft_modes`.
Full suite 253→259 (6 new tests here), 0 regressions.

Also resolved this session's parallelism question for S1e-05/06/07 via `AskUserQuestion`: sequential, not
parallel agents — S1e-07 hard-depends on S1e-06's replay infrastructure, and S1e-05/S1e-06 both edit
`des.py`/`cli.py`, so concurrent agents risked a conflicting merge costing more than the wall-clock saved.

---

## 🟢 [DONE] S1e-06 — V5 trace export for the SME walkthrough  ·  **gate V5**
**Size:** `M` | **Depends on:** S1e-03 | **Spec:** §9.2

**As a** SME **I want** a detailed trace export
**so that** I can manually step through a simulation day and verify the engine's logical decisions.

### Description
Subject Matter Experts need to trust the engine's logic. Exporting a detailed, step-by-step trace allows a planner to verify the engine handles Edge Case X correctly.

### Acceptance Criteria
- [x] Replay a real disruption week; export an **operational timeline**, not a log dump
- [x] Each decision shows the alternatives considered and why they were rejected
- [x] Formatted for a 60–90 minute session — you get one hour of a duty manager's attention

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v5_trace.py`
*   🙋 **Manual:** `crewsim gate v5 --week 2026-01-12 --format timeline`
    *   **Expect:** hour-by-hour, readable by someone who has never seen the code
    *   **Fails if:** it reads as debug output
    *   > **The question to ask the SME is "would you have done this?"** — not "is this number right". A model
    *   > that reaches the right total by making decisions no duty manager would make is not validated.
    *   > Expect to learn about a recovery instrument the model does not have; that is a **successful** V5.

### How it was implemented
Implemented 2026-08-08. Genuinely un-passable as a real V5 gate in the spec's own sense: PASS requires a
human IOC duty manager saying "yes, I would have done this" in a real walkthrough — no code in this repo
can self-certify that. This story builds the artifact that walkthrough needs (a real replay + a readable
timeline) and says so explicitly, everywhere; it never claims a PASS it can't back.

User-confirmed disposition (this session's `AskUserQuestion` round, alongside S1e-05/07's scoping): the
corpus is entirely mock, so there's no real "memorable January ice storm" to replay — use the mock corpus's
own highest-disruption week instead, labelled as such everywhere it appears.

New `src/crewsim/engine/replay.py` prepares data only (which week has the most real D4 disruption for
`cfg.scope`, which real D4 rows fall inside it, a real calendar-anchored roster via `roster_loader.load_rosters`'s
existing `window` param). `des.py` gained `Simulation.real_absence_source` (a new generator, sibling to
`sick_call_source`, reading real D4 rows instead of NHPP draws) and `run_historical_week` — moved there
mid-implementation after `tests/test_dependency_rule.py` caught `replay.py` importing `simpy` directly
(S0-00b: only `des.py` may). `notification_ts` (real report time) drives when each `OpenTimeItem` surfaces;
`[absence_start, absence_end)` (also real) is the window searched for broken pairings — two distinct real
timestamps D4 already carries, which the synthetic generator conflates into one draw but real data doesn't
have to. `sick_calls.py` gained `apply_named_absence` (a named-crew sibling to `apply_sick_call`, sharing a
new `_break_pairings` helper) — extracting that helper surfaced a separate, real, pre-existing gap:
`apply_sick_call` never set `OpenTimeItem.flight_mins` (always the dataclass default `0.0`), unlike
`cascade.py`'s own item construction, so `legality.py`'s rolling-flight-hour check has been undercounting
sick-call-origin items' added flight time since S1b-04. Deliberately **not** fixed here — changing it would
alter every existing CRN scenario's legality outcomes, well outside this story's scope — documented in
`_break_pairings`' own docstring as a future story candidate instead of silently patched.

Added `Simulation.verbose_trace` (new, separate from the existing `trace` flag) so this story's heavier
per-decision logging never affects S1e-02/03's existing `trace=True` callers — only `replay.py`'s path sets
it. When `True`, `_attempt_resolution` logs the full alternative set for every decision: `RESERVE` decisions
show every on-call reserve's real legality verdict (`fail_rule`/`reason` verbatim from `legality.py`) for
whoever was rejected; `DRAFT` decisions show real tier sizes and the chosen candidate's real seniority rank
within their tier, not every candidate's name (a tier can hold dozens of real day-off crew — an SME's hour
is better spent on which tier was reached than a name dump).

New `src/crewsim/gates/v5_trace.py` (`format_timeline` groups `sim.trace` into hour-by-hour buckets anchored
to the real week's Monday 00:00, `MOCK_DATA_CAVEAT` printed at the top of every export) and
`crewsim gate v5 --week --format timeline --policy` CLI dispatch — `--week` accepts an explicit ISO date
(the story's own literal syntax still works) or, if omitted, defaults to the peak-disruption week.

`tests/gates/test_v5_trace.py` cross-checks the peak-week finder against an independent manual aggregation;
proves no synthetic arrivals leak into the replay by verifying every "REAL ABSENCE" trace line's `absence_id`
is a real D4 row for that exact week/scope; verifies hour-grouping and the mock-data caveat; verifies real
rejection reasons (`ILLEGAL_L3` etc., verbatim from a real legality check) appear when a real on-call reserve
was actually rejected.

**Two real bugs found reviewing the shipped output against this story's own AC** ("each decision shows the
alternatives considered and why they were rejected") before calling it done:
1. A pairing that started *before* the replay window (a duty already mid-flight when the week begins —
   `load_rosters`'s `window` param returns any block *overlapping* the window, not just ones starting inside
   it) produced an item whose deadline was already in the past at sim time 0 — instant cancellation, zero
   recovery attempt, nothing for the timeline to show. Fixed: `apply_named_absence` now excludes any block
   with `b.start < 0`. The normal CRN engine (`apply_sick_call`) never hits this — every item it creates
   already has `item.start` within the same horizon its "now" is measured against.
2. Separately, an item that legitimately finds zero eligible reserves *and* zero legal draft candidates at a
   real retry checkpoint produced no trace line at all before its eventual cancellation — a real, reachable
   decision ("we looked, found nobody") with nothing shown. Fixed: `_attempt_resolution` now logs this case
   explicitly under `verbose_trace`.

Both covered by new regression tests (2 in `tests/engine/test_sick_calls.py`; a 3rd in `test_v5_trace.py`
scanning every real "CANCELLED at deadline" line for preceding reasoning). Re-verified both manual-check
forms after the fixes — the story's own literal `--week 2026-01-12` and the confirmed default (peak-
disruption week, currently 2026-02-23) both produce a clean timeline with no unexplained cancellations.
Full suite 259→268 (9 new tests: 5 in `test_v5_trace.py` + `test_cli_gate_v5` + 3 regression tests for the
two bugs above), 0 regressions.

---

## 🟢 [DONE] S1e-07 — V6 cost backtest against actuals  ·  **gate V6**
**Size:** `L` | **Depends on:** S1e-06 | **Spec:** §9.2

**As a** reviewer **I want** a backtest against historical costs
**so that** I can validate that the simulation's baseline matches reality.

### Description
The ultimate proof is historical accuracy. If the simulation's baseline cost is drastically different from what finance actually paid last year, the model is invalid.

### Acceptance Criteria
- [x] Feed **actual** historical disruption streams through the model; compare against real payroll and
  invoice cost for the same period
- [x] Report the **bias decomposition** from §9.2, not just the headline gap
- [x] State the direction each exclusion pushes: voluntary layer, conservative surrogate, no network
  propagation, no aircraft/passenger recovery

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v6_backtest.py`
*   🙋 **Manual:** `crewsim gate v6 --period 2026-01`
    *   **Expect:** simulated vs actual, with the decomposition shown
    *   **Fails if:** it lands inside tolerance with no decomposition — offsetting biases that cancel by
    *   luck are worth less than a miss in the predicted direction and magnitude
    *   ## Exiting Phase 1
    *   Once V5 and V6 pass, the model may inform a bid-period decision — subject to §9.3's reporting
    *   obligations, which include listing every outstanding `[CONFIRM: …]` the result depends on.
    *   **Only then refine the `product_1/` epics.** Writing detailed Phase-2 acceptance criteria before this
    *   point encodes today's assumptions into next quarter's work.

### How it was implemented
Implemented 2026-08-08. Same un-passable-as-a-real-gate disposition as S1e-06: PASS requires comparing
against **real** D7 payroll / D10 invoices, which don't exist in this repo — only
`tools/generate_mock_corpus.py`'s generated ones do. User-confirmed disposition (this session's
`AskUserQuestion` round, the non-default choice): build the real backtest mechanics now against mock data,
always labelled `MOCK CORPUS DATA` at the top and bottom of every report, rather than parking the story — so
it's ready to run for real the moment real payroll/invoice data exists.

Generalized S1e-06's replay path from a fixed 7-day week to an arbitrary date range: `des.run_historical_week`
renamed to `des.run_historical_replay` (period-agnostic — `horizon_minutes` is whatever span the caller
prepared roster/reserves/absences for). `replay.py` gained `run_historical_period(cfg, costs, policy,
period_start, period_end, trace, verbose_trace)` as the new general entry point; `run_historical_week` stays
as a thin wrapper (always `trace=True`/`verbose_trace=True`, since an SME walkthrough always wants full
alternative-set logging) so S1e-06's own tests/CLI path is untouched. V6 calls `run_historical_period`
directly with `month_bounds(period)` and `trace=False`/`verbose_trace=False` — a full-month backtest has no
SME audience and would otherwise log every decision for 31 days.

New `src/crewsim/gates/v6_backtest.py`: `month_bounds` ("YYYY-MM" → `[first day, first day of next month)`);
`compute_actual_cost` sums real D7 rows by `pay_code` for `cfg.scope`'s crew_ids in that `pay_period`, plus D10
positioning invoices for the same crew/date range (reported separately — the engine doesn't model positioning
cost at all); `compute_simulated_cost` sums the replay's own ledger by category; `run_v6_gate` computes the
gap and gap% between the two comparable totals; `print_v6_report` renders both totals, the gap, what's
excluded from each side and why, and spec §9.2's own bias-decomposition table verbatim
(`SPEC_BIAS_DECOMPOSITION` — qualitative OVERSTATES/UNDERSTATES statements, not computed values, matching
this story's own `fails_if`).

**Real bug found before calling this done:** the first version matched sim ledger categories against a flat
dict with exactly two keys (`RESERVE_STAFFING`, `RESERVE_UTILIZATION`) mapped to their D7 pay_codes, but
`des.py` books draft costs under a dynamic `f"DRAFT_TIER{tier}"` category name (tier 1–5) that matched no key
at all — every draft cost was silently dropped from *both* the comparable total and the excluded-costs
breakdown, so the printed report simply never accounted for them anywhere. Found by manual smoke-test: the
"Excluded" section's total didn't visibly include the drafts a disruption month obviously produces. Fixed with
`_pay_code_for_sim_category()`, which special-cases the `DRAFT_TIER` prefix → D7's single `DRAFT_PREM` pay_code
(D7 doesn't break draft premium out by impact tier, so neither does this comparison). Covered by a dedicated
regression test (`test_draft_costs_are_not_silently_dropped_from_the_comparison`).

**Second finding, non-blocking:** for `2026-01` the printed gap is large (simulated ≫ actual) because only
~21 of 120 in-scope crew have *any* D7 row that month — verified this is real fixture behaviour, not a
scope-filter bug (`tools/generate_mock_corpus.py` only emits D7 rows for `RESERVE_UTIL`/`DRAFT_PREM`/
`RESERVE_GTE` **events**, never a full payroll register, and there are zero `ALL`-fleet crew at the
YUL/A321neoLR/FO scope that could be getting dropped). Since a bare gap % next to a sparse actual total
invites being misread as a calibration signal, `print_v6_report` now also states `n_crew` in scope, how many
of them have any comparable D7 row, and the row count backing that — so the sparsity is visible, not just
correct.

`tests/gates/test_v6_backtest.py` (6 tests): `month_bounds`; `compute_actual_cost` cross-checked against an
independent manual D7 aggregation; a real disruption month produces a nonzero comparable gap; the
`DRAFT_TIER` regression test above; excluded costs (`CANCELLATION`/`TERMINAL_PENALTY` on the sim side, D10
positioning on the actual side) are present in the result, not silently dropped; `print_v6_report` shows the
`MOCK_DATA_CAVEAT` at both top and bottom plus every `SPEC_BIAS_DECOMPOSITION` row. Plus `test_cli_gate_v6`
and `test_cli_gate_v6_requires_period` (exit code 2 with a clear message when `--period` is omitted) in
`tests/test_cli.py`.

Re-verified the story's own literal manual check, `crewsim gate v6 --period 2026-01` (default `--policy`, no
other flags), after all fixes — clean output, correctly labelled. `mypy --strict src/crewsim/engine/`
unchanged at 17 pre-existing errors. Full suite 268→276 (8 new tests: 6 in `test_v6_backtest.py` + 2 in
`test_cli.py`), 0 regressions.


# CrewSim — Logic Analysis & Items To Be Fixed

> Source: static code review of `src/crewsim/**`, `configs/**`, `spec_sections/**` (read-only analysis, Oct 2026).
> Measured figures marked **(measured)** were obtained by read-only runs against the mock corpus.
> All paths are relative to `C:\dev\crewsim\`. Line numbers are indicative at time of review.

---

## 0. Executive summary

CrewSim is a two-stage stochastic simulation that picks a reserve level R* for one crew cell
(YUL / A321neoLR / FO / winter_sun):

```
D1–D12 data → quality gates → calibration (NB2 sick calls, delay GMM, Markov regimes)
  → scenario generation (cached parquet, CRN)
  → SimPy DES per policy (reserve → cross-base → draft → hold → cancel; legality L0–L8; cascades)
  → cost ledger → KPIs / paired comparison → R* = argmin E[C] + λ·CVaR95(C)
  → V&V gates V1–V9 → CLI / HTML report / FastAPI + React UI
```

The architecture is sound, but several defects **directly bias the recommended R\***:

| # | Issue | Impact on decision |
|---|---|---|
| F-01 | Stage-1 staffing counted (1+λ)× in objective | R* biased **down** as λ grows |
| F-02 | Policy label ≠ real headcount (R6/R8/R10 carve 7/9/12), `dow` ignored | x-axis of the decision is wrong |
| F-03 | CRN only aligns arrival timing, not *who* is sick | Paired CIs overstated |
| F-04 | Sick calls have zero notice, durations too short | Demand & lead time under-stated |
| F-05 | NB2 model: no exposure offset, no interactions, ~Poisson | Cell rate off −14 %…+23 %, tails too thin |
| F-06 | UTC vs local clock mix; rolling limits start cold | Legality & replay misaligned by 4–5 h |
| F-07 | Double-booking paths (cross-base, donor blocks, sick draftee) | Infeasible schedules accepted |

Priority legend: **P0** = corrupts the recommendation, **P1** = materially biases KPIs/gates,
**P2** = correctness/robustness, **P3** = hygiene.

---

## 1. Decision / objective layer

### F-01 · P0 · Stage-1 staffing cost counted (1+λ) times
- **Where:** `src/crewsim/engine/des.py:1191-1216` (`measured_window_costs` includes `RESERVE_STAFFING`),
  `src/crewsim/gates/v9_sensitivity.py:76-91` (`real_r_recommender`), `reporting/recommendation.py`.
- **Problem:** objective computed as `E[C1+Q] + λ·CVaR(C1+Q)` = `(1+λ)·C1 + E[Q] + λ·CVaR(Q)`.
  Spec §7.4 is `C1 + E[Q] + λ·CVaR(Q)`. The spec's own worked table (§7.4/§8.3) repeats the error.
- **Fix:**
  1. Split ledger categories into `STAGE1 = {RESERVE_STAFFING}` and `STAGE2 = everything else except DELAY_AMBIENT`.
  2. Add `measured_window_costs_by_stage()` returning `(c1, q)` per scenario.
  3. Recommender: `score = mean(c1) + mean(q) + λ·cvar95(q)`.
  4. Correct spec §7.4 / §8.3 tables.
- **Acceptance:** unit test where C1 is constant and Q = 0 → score independent of λ; V9 surface recomputed.

### F-02 · P0 · Policy labels ≠ headcount; `dow` never applied
- **Where:** `engine/policy.py:71-80` (`total_reserves` = peak SC+LC), `engine/roster_loader.py:242-320`,
  `reporting/recommendation.py:46-53`, `reporting/report.py:161`, `gates/v9_sensitivity.py:59`.
- **Problem:** R6 = 4+2 weekdays / 5+2 weekends → carves **7**; R8 → 9; R10 → 12. `dow` is never read,
  so weekday/weekend targets are not honoured; SC/LC split taken from peak entry only. R is parsed from the file name.
- **Fix:**
  1. Carve reserves per day: on day *d*, only `sc(dow(d))` SC and `lc(dow(d))` LC reserve blocks are active
     (others become day-off for that day, or are not carved at all).
  2. Add `Policy.reserve_days()` = Σ_d (SC+LC) and `Policy.mean_daily_reserves()`; use that as the x-axis.
  3. Replace `int(name.lstrip("R"))` / regex parsing with the computed metric.
  4. Either rename policies to match peak or make files consistent (e.g. R6 = 6 every day).
- **Acceptance:** test asserting active reserves per day == policy table for each dow; report x-axis uses computed value.

### F-08 · P1 · R* ignores statistical uncertainty
- **Where:** `gates/v9_sensitivity.py:86-90`, `reporting/recommendation.py:63`, CLI defaults `cli.py:592,605` (n=20).
- **Problem:** argmin on point estimates; with n=20 CVaR95 = 1 scenario; paired CIs computed but unused;
  10 pairwise tests without multiplicity correction (`api/routers/processing.py:62-76`).
- **Fix:**
  - Recommend the **smallest R whose score is not significantly worse** than the argmin (paired CI on score difference, bootstrap for CVaR).
  - Raise default `n_scenarios` to ≥ 200 for `grid`/`report`; warn when `ceil(0.05·n) < 5`.
  - Holm–Bonferroni on pairwise p-values.
  - Bootstrap CI for CVaR95 per policy.
- **Acceptance:** report shows "R* and indifference set"; warning emitted for n<100.

### F-09 · P1 · Report and API can disagree on R*
- **Where:** `reporting/report.py:192-207,255` vs `reporting/recommendation.py`.
- **Problem:** report has no service-level filter, labels λ-only sweep as "V9 STABLE", marks CVaR-only minimum as optimum.
- **Fix:** report must call the same `recommendation.recommend()`; label λ-sweep honestly; show full V9 (λ × terminal penalty × roster size).

### F-10 · P2 · Service-level test on raw proportion
- **Where:** `reporting/kpis.py:253-266`.
- **Fix:** use Wilson upper bound of `p = #(uncovered > u_max)/n` vs ε; report the bound.

### F-11 · P2 · Zero-variance pairs → NaN → JSON 500
- **Where:** `reporting/paired.py:60-62`; duplicate `config_ids` not rejected.
- **Fix:** if SE == 0 return `t=None, p=None, identical=True`; dedupe `config_ids` at API boundary.

---

## 2. Simulation engine (`src/crewsim/engine/`)

### F-03 · P0 · Common random numbers only partially aligned
- **Where:** `sick_calls.py:108-121`, `des.py:373, 819-843, 984`, `eligibility.py:127`.
- **Problems:**
  1. Sick crew chosen as `rng.integers(len(eligible))` over a **policy-dependent** list (carve-out, drafts, prior absences).
  2. Arrivals with no eligible crew silently vanish.
  3. REDUCED-mode cascade draws keyed by `item.uid`, which is policy-dependent (docstring claims otherwise).
  4. `self.rng` shared sequentially for eligibility/positioning draws.
- **Fix:**
  - Choose the sick *crew_id* from the **original, un-carved roster** (policy-independent), keyed by `event_rng("sick_call:{day}:{i}")`.
    If that crew is a reserve under this policy, apply the absence to the reserve (removes on-call capacity) — this also fixes F-19.
  - Key all policy-dependent draws with `event_rng(stream, f"{purpose}:{root_event_uid}:{ordinal}")`; remove `self.rng` usage.
  - Count and report dropped arrivals as a KPI.
- **Acceptance:** test: same scenario under R4 and R14 → identical list of (time, crew_id, duration) for sick calls.

### F-04 · P0 · Sick-call notice and duration unrealistic
- **Where:** `des.py:365-400` (uniform time-of-day, absence starts at arrival), `sick_calls.py:111-114`,
  `calibration/nhpp.py:134-139` (lognormal), `des.py:379-384` (0.5-day floor).
- **Problem (measured):** real notice mean ≈ 13.7 h (2–26 h); P(dur = 1 day) = 57.9 % in data vs model P(X≤1) = 22.8 %;
  P(>10 d) 0.68 % vs 0.16 %. Same-day pairings reporting before the draw time are never broken.
- **Fix:**
  1. Calibrate an empirical (or fitted) **notice-lead-time** distribution from D4 `notification_ts − absence_start`.
  2. Absence starts at the **start of the absence day** (local); notification = start − lead.
  3. Model duration as a **discrete** distribution on whole days (empirical PMF or zero-truncated NB / geometric).
  4. Remove the 0.5-day floor.
- **Acceptance:** generated vs historical notice & duration distributions pass KS/χ² test in a new calibration diagnostic.

### F-06 · P1 · Clock / timezone inconsistencies
- **Where:** `roster_loader.py:103,162-163,184,196-199`, `replay.py:79-100`, `des.py:368`, `generator.py:189-192`, `costs.py:65-69`.
- **Problems:**
  1. Sim minute 0 = UTC midnight (= 19:00/20:00 local previous day); day buckets are UTC, DOW covariate is local.
  2. Replay measures D4 local timestamps from local midnight vs roster in UTC → 4–5 h shift.
  3. One UTC offset applied to all duty periods of a pairing (down-route stations, DST).
  4. Blocks ending before the anchor are dropped → 7/28-day rolling limits start at zero.
  5. Staffing paid per UTC day with any overlap → overnight shifts may be paid twice.
- **Fix:**
  - Choose one canonical clock: **UTC minutes from `window_start` in base-local midnight converted to UTC**.
    Convert every local timestamp through a single helper `to_sim_minutes(ts, tz)` using `zoneinfo`.
  - Compute day buckets/DOW in base-local time everywhere.
  - Load a **28-day pre-window history** (blocks only, read-only) to seed rolling counters.
  - Staffing: pay per reserve *duty day* (block start date local), not per UTC-day overlap.
- **Acceptance:** replay test: a D4 absence at 06:00 local breaks the 07:00 local pairing; DST-crossing fixture.

### F-07 · P1 · Double-booking / calendar consistency
- **Where:** `roster_loader.py:272,310-314,384-390`, `events.py:60-65`, `legality.py:14-23`, `sick_calls.py:37,111-114`.
- **Problems:**
  1. Cross-base reserves keep their real PAIRINGs; `assign_reserve` removes only RESERVE blocks → overlapping DRAFTED_DUTY + PAIRING, no cascade.
  2. In-scope reserves inherit donor VACATION/TRAINING/SIMULATOR blocks and lose their own non-pairing blocks.
  3. Sick crew's future DRAFTED_DUTY is not broken (only PAIRING).
  4. Line holders who were real reserves keep empty gaps → inflate tier-1 draft pool.
- **Fix:**
  - `assign_reserve` must route overlapping PAIRING/TRAINING/SIM blocks through the same `compute_draft_delta` path (→ CASCADE items) or reject via legality.
  - Carve-out: keep the reserve's **own** VACATION/TRAINING/SIM; only overlay donor RESERVE pattern on free days.
  - `apply_sick_call` breaks DRAFTED_DUTY and DEADHEAD too.
  - Former-reserve gaps become explicit DAY_OFF or OPEN blocks (decide tier explicitly).
  - Run `find_l0_violations` as a post-condition in debug/test mode for every scenario (cheap invariant).
- **Acceptance:** Hypothesis test: after any simulation, no crew has overlapping duty blocks (all crew incl. cross-base).

### F-12 · P1 · Legality only looks backward
- **Where:** `legality.py:137-161` (L2), `270-313` (L3/L4), `315-386` (L5).
- **Problems:** new duty not checked against **future** rolling windows or rest before the next kept duty;
  L2 treats RESERVE as duty regardless of `reserve_counts_as_duty`; L2 relies on sorted calendar (`break`).
- **Fix:** evaluate L3/L4/L5 over all windows touching `[start, end]` (sliding forward too); honour
  `reserve_counts_as_duty` in L2; replace `break` with explicit filter or assert sortedness.
- **Acceptance:** fixture where a draft makes next week's 7-day window exceed 60 h → illegal.

### F-13 · P1 · Cross-base reserves never flown home; hold loop ignores them
- **Where:** `des.py:504-511, 542-621, 651-664`.
- **Fix:** add return DEADHEAD (+ cost) after REST, or keep reserve away until next home duty; include cross-base pool in hold-wakeup times.

### F-14 · P2 · Broken pairing handled per duty-period, always at home base
- **Where:** `cascade.py:55-80`, `sick_calls.py:42,111-114`, `des.py:632-641`.
- **Fix:** break whole pairing (all remaining duty periods) as one item, or carry the duty period's real departure station so positioning is priced.

### F-15 · P2 · Broken pairings vanish in REDUCED mode / cascades disabled
- **Where:** `des.py:736-755`.
- **Fix:** when cascades are suppressed, keep the pairing on the calendar (don't apply removal), or book a counted "SUPPRESSED_CASCADE" row.

### F-16 · P2 · Horizon edge effects
- **Where:** `des.py:430-432, 916-920`, `terminal.py:19-25`, `des.py:1172-1177`.
- **Problems:** displaced pairings starting before t=0 cancelled at t=0; items scheduled after horizon never charged;
  deadline == horizon → TERMINAL_PENALTY not CANCELLATION; terminal penalty omits APPR; asymmetric window attribution
  (warm-up-rooted costs booked in window count, cool-down only if root in window).
- **Fix:** filter `start < 0` in displaced path (as `apply_named_absence` does); add APPR to terminal penalty;
  attribute strictly by **root time** for all rows (symmetric rule); document horizon boundary semantics.

### F-17 · P2 · Hold queue has no priority
- **Where:** `des.py:503-520`.
- **Fix:** when multiple items wake at the same reserve start, serve by earliest deadline (EDF) — implement a central dispatcher rather than per-item processes.

### F-18 · P2 · `stage2.reserve_selection`, Policy `season`/`mode` are inert
- **Where:** `des.py:687,590,989,993`, `eligibility.py:81`, `config.py:322`.
- **Fix:** implement a selection-rule registry (`shortest_remaining_window`, `least_utilised`, `senior_first`...) or remove the field;
  validate `mode` as `Literal["FULL","REDUCED"]`; CLI must reject policy whose `season` ≠ run season (API already does).

### F-19 · P2 · Reserves never call in sick
- **Where:** `sick_calls.py:111-115`.
- **Fix:** resolved by F-03 (select from full roster; reserve absence removes on-call blocks).

### F-20 · P3 · Misc engine hygiene
- Stale comment SIMULATOR tier (`des.py:767-772` vs `drafting.py:16-20`).
- Hard-coded constants → config: L5 144 h/24 h (`legality.py:352-353`), p_elig 0.3 / p_cascade 0.2 (`eligibility.py:59-62`),
  myopic cascade price $500 (`counterfactuals.py:46`), replay `default_rng(0)` (`des.py:1062`), REDUCED "+1 day" synthetic cascade (`des.py:834-843`).
- `next(iter(crew.fleet_quals))` (`cascade.py:68`, `sick_calls.py:43`, `des.py:429`, `eligibility_target.py:86`) → `sorted(...)[0]` or explicit primary qual.
- Fleet filter uses substring `str.contains` (`roster_loader.py:114`) → exact match; honour `qual_valid_from/to`.
- Eligibility samples recorded on every retry (`eligibility.py:136-138`) → record once per item.
- Unused `Pairing`/`DutyPeriod` dataclasses (`state.py:53-65`) → remove or use.
- Silent empty reserve calendars when no donor pattern (`roster_loader.py:291`) → raise/warn.

---

## 3. Calibration & scenarios (`src/crewsim/calibration/`, `scenarios/`)

### F-05 · P1 · Sick-call regression mis-specified
- **Where:** `calibration/nhpp.py:47-119`.
- **Problems (measured):** formula main-effects only, no exposure offset (crew headcount), α = 0.004 (≈ Poisson) while
  observed Var/Mean = 1.05–1.33; cell predicted vs observed: CALM 0.50/0.40, NORMAL 1.08/1.16, DISRUPTED 2.07/2.39, SEVERE 3.48/3.05.
  Pooled across seasons (spec requires per-season). Cells from today's ACTIVE D1 snapshot.
- **Fix:**
  - Add `offset=log(active_crew_in_cell_on_day)` (from D2/D1 history) → rate per crew-day; scale by line-holder count in DES.
  - Add interactions `base:fleet`, `season:regime` (or fit per season as per spec).
  - Fit dispersion per regime or use a random-effect / NB with cell-level α.
  - Add a posterior-predictive check (mean + variance per regime) to diagnostics.
- **Acceptance:** predicted/observed within ±5 % per regime in the scope cell; dispersion check within CI.

### F-21 · P1 · Absence type & linkage assumptions
- **Where:** `nhpp.py:71-75`.
- **Problem:** SICK + INJURY + FAMILY all counted; 8.4 % of D4 rows have no pairing but DES forces every arrival onto a pairing holder.
- **Fix:** make included absence types configurable & documented; model P(absence hits a pairing) explicitly.

### F-22 · P2 · Delay model
- **Where:** `calibration/delays.py:100-187`, `scenarios/generator.py:209`.
- **Problems:** Gaussian mixture on positive skewed data (4–5 % negative draws floored to 1 min); pooled across regimes;
  flights/day fixed at `round(mean)`; departures from base only; delays not tied to simulated pairings.
- **Fix:** lognormal/gamma mixture; per-regime durations if data allows; Poisson/NB flights/day by DOW from D8/D3.
  (Lower priority while `DELAY_AMBIENT` is excluded from the objective — but document it.)

### F-23 · P2 · Regime model details
- **Where:** `calibration/regime.py:56-166, 196-291`, `pipeline.py:97,120-124`.
- **Problems:** pi0 computed after consecutive-day filter; called "steady state" but is empirical marginal;
  `label_agreement` mixes network-wide vs base-scoped chaos and is part of `content_hash`; no smoothing on sparse rows;
  hard-coded `p50/p80/p95` labels; `normal_mean = 1.0` silent fallback; `multiplier` column unused.
- **Fix:** compute pi0 before filtering (or use true stationary dist); exclude `diagnostics` from `content_hash`;
  Dirichlet(1) smoothing on transition rows; fix/remove `label_agreement`; drop or use `multiplier`.

### F-24 · P2 · Scenario cache invalidation
- **Where:** `scenarios/generator.py:18-61, 240-255`.
- **Problems:** cache key omits sampler code version & numpy version; `stable_seed(42)` vs `"42"` collide in key string;
  temp file named by PID only (thread collision); no eviction.
- **Fix:** include `crewsim.__version__`, numpy version, and type-tagged seed in signature; temp name with `uuid4`; add `scenarios prune`.

### F-25 · P2 · Template window / scope calendar
- **Where:** `roster_loader.py:12-42`; `scope.bid_period` unused.
- **Problem:** template is latest all-winter 42-day holdout span (Mar–Apr 2026) not the target bid period; holdout leakage into V3/V6.
- **Fix:** pick template window from `scope.bid_period` analogue in **fitting** data, or make it explicit config; keep holdout for gates only.

### F-26 · P3 · Calibration hygiene
- Per-fitter CLI commands fit on full corpus incl. holdout (`cli.py:863-883`) → apply window guard inside `pipeline.run_pipeline`.
- Side JSON files (`nhpp_sick_calls.json`, ...) unused & overwritten → remove or namespace by season.
- Nelder-Mead fallback "converged" flag unreliable (`nhpp.py:109-113`) → check gradient norm.
- Calibration writes params file in place (`pipeline.py:147`) → atomic temp+rename.

---

## 4. Data reconstruction & V&V gates

### F-27 · P1 · V2 Erlang gate cannot fail meaningfully
- **Where:** `gates/v2_erlang.py:92-108,190`, `des.py:606-607,703`.
- **Problems:** passes if `ci_high ≥ B(s,a)` (blocking-everything passes); `s` measured after sim on mutated calendars
  (busy time subtracted twice); cross-base path inflates on-call minutes without counting assignments; cross-base not disabled.
- **Fix:** two-sided test (B within CI, or |p̂−B| < tol); compute `s` from pre-simulation calendars; disable cross-base,
  L3/L4/L8 and use single airport per spec §9.2; count cross-base assignments consistently.

### F-28 · P1 · V4 cascade gate compares different populations
- **Where:** `data/cascades.py:43-56,91-124`, `gates/v4_cascade.py:64-120`, `tests/data/test_cascade_table.py:184`.
- **Problems (measured):** one D6 cascade row credited to several drafts (588 flagged vs 511 rows); historical scope =
  all bases/fleets/seasons vs sim = one cell; definitions differ; window filter truncates last 7 days; recall warning uses `d4_link_marginal`.
- **Fix:** 1-to-1 assignment (cascade → most recent prior draft); filter historical to sim scope & season; filter window
  *after* scan; dedicated `draft_recall_warn` threshold; fix the test that asserts the bias.

### F-29 · P1 · V3/V4 compare mean vs CI of historical mean
- **Fix:** two-sample comparison (KS / bootstrap on difference of means with both sampling errors), per spec "full distribution".

### F-30 · P2 · Draft reconstruction vs spec §6.3
- **Where:** `data/drafts.py:27-126`, `data/quality.py:101-118`.
- **Problems:** prior status not filtered (37 PAIRING→PAIRING counted); premium join ignores `duty_date`;
  "recall" = count ratio (can exceed 1); `quality.py` hard-codes codes, doesn't dedupe D7 (rate can exceed 100 %).
- **Fix:** filter prior block ∈ {DAY_OFF, VACATION, TRAINING}; join on date; event-level matching for precision/recall;
  single shared reconstruction function used by both quality gate and drafts.

### F-31 · P2 · Eligibility target reconstruction
- **Where:** `data/eligibility_target.py:22-125`.
- **Fix:** update docstring; exclude in-progress pairings; one event per pairing (not per duty period); remove other absent crew from pool.

### F-32 · P2 · Missing / non-verdict gates
- V5, V6, V9 never return PASS/FAIL (`cli.py:1151-1179`); V8 has no module (`cli.py:1181`).
- **Fix:** V6 add tolerance & bias-direction check, use exact week & historical reserve establishment;
  create `gates/v8_invariants.py` running N chaos scenarios with full-roster invariant checks (incl. cross-base crew);
  V9 test roster_size axis, deterministic findings ordering, handle empty surface, include 1× terminal baseline;
  `report.py` must show INCONCLUSIVE ≠ FAIL.

### F-33 · P2 · V7 reproducibility scope
- **Fix:** include `reserve_call_types` side table in ledger hash; shuffle scenario order in the parallel run; optional cross-machine CI job.

### F-34 · P3 · Data quality coverage
- D4 link should check against D2 schedule, not only D3 (spec §6.2).
- Domain checks missing: D5 outcome, D4 absence_type, D9 class, D8 cancelled; no end ≥ start, UTC/local consistency checks.
- `employment_status LEAVE` allowed by dictionary but rejected by `quality.py:16-19`.
- D12 long-call 12 h vs `base.yaml:216` 14 h (documented open question).
- README ground-truth figures out of date; `gates/` lacks `__init__.py`.

### F-35 · P3 · Weak tests to strengthen
- `test_v3_eligibility.py` (sim = hist mean), `test_eligibility_table.py` (only len>100), `test_v4_cascade.py` (all mocked),
  `test_v1_degeneracy.py:97-119` (negative control never calls gate), `test_quality_gates.py` (no duplicate-D7 case),
  `test_legality.py` (`test_l0_invariant` restates predicate; `test_l5_invariant` only no-crash), `test_v9_sensitivity.py` (roster axis untested).

---

## 5. Reporting & KPIs

### F-36 · P2 · KPI definitions
- **Where:** `reporting/kpis.py:249,251,294`, `reporting/grid.py:86-134`, `reporting/cascade_analytics.py`, `reporting/tape.py:11-14`, `engine/cascade.py:77`, `sick_calls.py:49`.
- **Problems:** cascade rate = mean of per-scenario ratios, drops zero-draft scenarios, not window-attributed;
  Gini excludes zero-draft crew; per-day counts over whole horizon vs scenario counts over window;
  chain depth always 0/1 (root passed down, not parent); one sick call with N pairings = N chains (amplification skewed);
  `cost_by_category` includes DELAY_AMBIENT so doesn't sum to `expected_cost`.
- **Fix:** ratio-of-sums with window attribution; Gini over all eligible crew; add `parent_event_uid` to ledger rows;
  one root per sick call; document/separate excluded categories.

### F-37 · P3 · Report provenance & robustness
- `report.py:92` costs version from pin label not loaded file; `report.py:161` crashes on non-`R<n>` names;
  counterfactual shows mean diff only (`counterfactual.py:52-57`) → add paired CI.

---

## 6. API / Web / Ops

### F-38 · P0 (security) · No auth + arbitrary file read
- **Where:** `api/main.py`, `config.py:683-686` (`policy_path` accepts any path), `api/routers/processing.py:404,641-643,772`.
- **Fix:** allow-list policy IDs from `configs/policies/*.yaml` (resolve & ensure under policies dir); never echo exception text;
  add authentication (at minimum an API token / Entra ID) on all mutating routes.

### F-39 · P1 · Job lifecycle bugs
- Cancelled-while-queued jobs still run (`processing.py:201`); late cancel overwritten by "completed" (`processing.py:447`);
  generic retry (`routers/jobs.py:106-121`) re-runs any job with demo worker and marks it completed; `create_job` accepts any type;
  joblib cancel only after all policies finish (`grid.py:188-195`).
- **Fix:** compare-and-set status transitions (`UPDATE ... WHERE status='queued'`); re-read before completing;
  restrict retry to its own job type or dispatch by type; per-scenario cancel token checked inside workers.

### F-40 · P1 · Concurrency & resource limits
- CPU-bound sims in Starlette thread pool, unbounded; `num_scenarios`/`jobs` unbounded (`processing.py:176-185`);
  SQLite without WAL/busy_timeout (`db.py:96-97`) + commit per scenario + SSE polling every 0.5 s;
  fixed output filenames overwritten (`grid.py:257`, `report.py:403`); tape `lru_cache` key lacks params hash/costs version (`processing.py:759-773`).
- **Fix:** bounded `ProcessPoolExecutor` / job queue with max concurrency; validate limits (e.g. scenarios ≤ 2000, jobs ≤ cpu_count);
  `PRAGMA journal_mode=WAL; busy_timeout=5000`; throttle progress commits (≥1 s); per-run output dirs (`output/runs/<run_id>/`);
  include params hash & costs version in tape cache key; DB path from config (absolute).

### F-41 · P3 · Config validation gaps
- Missing: window start<end & fitting/holdout non-overlap (`config.py:67-74`), non-negative horizon (92-95),
  ε ∈ [0,1] (303-304), quantile ordering (152-155), `dow` ∈ 1..7 (`policy.py:22`), `mode` literal.
- Uncovered deadline silently 0.0 when `demand` missing (`sick_calls.py:19-22`) → required field.
- `costs_cabin.yaml` does not validate → mark as stub or complete.
- CLI: `compare` help says "two or more" but requires two (`cli.py:530,1438`); `scenarios generate --season` hard-coded default (`cli.py:474`);
  `config.load()` prints warnings on every API request.

---

## 6b. Severity regime source (D9 `disruption_class`)

### F-42 · P0 · Regime labels are an external, undefined input — they must be computed, not loaded

> **STATUS: IMPLEMENTED (Option B — hidden Markov model, hmmlearn).**
> `calibration/hmm.py` (DisruptionHMM: multinomial flight outcomes + Poisson sick calls with crew-on-duty
> exposure), `calibration/regime.py` (per base × season fit, Viterbi labels replacing D9, BIC 1–5 states,
> holdout log-lik vs a 1-state model), NHPP/delay fits consume the computed labels, D9 optional
> (cross-check only), quality gate `station_day_coverage_pass` on D8 replaces D9 completeness,
> `configs/base.yaml → calibration.regime_hmm`, API/UI report the HMM goodness of fit.
> Mock corpus: recovered regime agreement **82%** (old quantile labels: 25.8%), BIC selects 4 states,
> holdout log-lik/day −6.14 vs −9.64 without regimes. Full test suite: 530 passed, 7 skipped.
> Remaining from the plan below: real-data validation once Pierre's D8 extract is fixed.
- **Where:** `calibration/regime.py:44-65` (states = D9 `disruption_class`), `calibration/nhpp.py:38-57` (`C(regime)` covariate),
  `calibration/delays.py:37-55` (per-regime P(delay)), `data/profile.py:260-326`, `data/quality.py:30-56,121-126` (D9 completeness gate),
  `data/loaders.py:181-185` (schema), `tools/generate_mock_corpus.py:108-119,221-241,261,569`.
- **Current state:**
  - Since AUD-18 the *only* thing that defines a regime is the D9 column supplied by Air Transat. Everything in `regime.py`
    that looks like a definition — the chaos index, the p50/p80/p95 cut points (`regime.py:97-100`) and the multipliers
    (`regime.py:103-111`) — is computed **after** the fact, conditioned on D9's labels. The quantiles are not used to label
    anything in `fit_regime`; they are stored for reference. The multipliers are metadata only (generation does not use them).
  - The real meaning of `disruption_class` was never specified to Pierre (open question in
    `backlog/verify/pierre_analyse_donnees_reelles.md:171,202`). Real data: YUL has **3 SEVERE days out of 299**
    vs 130/1 075 in the mock. Its `intensity_multiplier` has a 1.5 value that doesn't exist in the mock.
  - **The mock is circular.** `generate_mock_corpus.py` draws the regime chain first (`REGIME_P`, line 111) and then generates
    D8 delays (line 261-264) and D4 sick calls (line 569) *from* that hidden regime with `REGIME_MULT`. D9 therefore hands the
    pipeline the oracle latent state. Every calibration result on the mock (clean β_regime gradient, persistence, V-gates) was obtained
    with information that real operations data does not contain.
  - The project's own computed labels agree with D9 only **25.8 %** of the time (`label_agreement`), so "D9" and "our chaos index"
    are two different definitions of a regime.
- **Why AUD-18 doesn't require D9:** AUD-18's real requirement is *one label source shared by the Markov chain, the NB2 sick-call
  model and the delay model*. That holds equally if the label is computed in-house.
- **Pitfall to avoid when computing it:** if the regime is defined from sick-call counts and the NB2 model then uses `C(regime)` to
  explain those same sick-call counts, the regime coefficient is inflated by construction (selection on the outcome). The regime
  must either be built from signals **other than** the modelled outcome, or be estimated as a latent state.
- **Fix (recommended order):**
  1. **Option A — deterministic, explainable (MVP):**
     - New module `calibration/regime_labels.py::label_days(cfg, window, season) -> DataFrame[station, date, regime]`.
     - Index from **operational signals at the scoped base only**: delay rate, mean delay minutes and cancellation rate of base
       departures (D8), optionally weather/ATC delay codes. **Exclude sick calls** (outcome of the NB2 model).
     - Cut points (`regime_quantiles`) computed on the **fitting window, per season**, stored in the parameter store, and then
       *applied* unchanged to holdout (no re-quantiling → no leakage).
     - Handle ties on discrete low counts (many zero days) — e.g. use a continuous index (rates/minutes) or rank-with-random-tie-break
       keyed by date.
  2. **Option B — principled (target):** a 4-state **hidden Markov model** at the base, fitted jointly on daily sick calls (NB emission)
     and delays/cancellations (emissions per state). It gives the transition matrix, pi0 and per-state rates in one fit; the states are latent
     and not imposed on the data, so the selection-on-outcome problem disappears. Viterbi labels can still be exported for reports.
  3. Make `fit_regime`, `nhpp.fit_sick_calls` and `delays.fit_delays` consume the **same** computed label table
     (pass it in, don't reload D9).
  4. **D9 fate:** drop `disruption_class` and `intensity_multiplier` from the required D9 schema. `season` is derivable from
     `configs/seasons.yaml`, so D9 can be removed from the required input list entirely. Keep it **optional** as a
     cross-check: if Air Transat supplies an operational class, report agreement in diagnostics only.
  5. Replace the D9 completeness quality gate with a "station-day coverage" gate on D8 (days with ≥1 base departure).
  6. **Mock corpus:** stop writing the oracle regime to D9 (or write it to a separate `_ground_truth_regimes.csv` used only by tests to
     score label recovery, e.g. adjusted Rand index / confusion matrix).
  7. Update the data dictionary, `pierre_analyse_donnees_reelles.md` (question 3 becomes "do you have a weather/ATC disruption log?"
     rather than "how is disruption_class computed?"), `calibrate_steps.py`, and the tests that build fake D9 frames
     (`test_regime.py`, `test_nhpp.py`, `test_delay_mixture.py`, `test_audit_fixes.py`, `test_quality_gates.py`, `test_loaders.py`).
- **Acceptance:**
  - Calibration runs with no D9 file present.
  - On the mock corpus, computed labels recover the hidden regime with a reported agreement / ARI (target to be agreed; Option B should beat Option A).
  - NB2 β_regime fitted on computed labels, with sick calls excluded from the label index, is reported alongside the diagnostic.
  - Cut points / HMM parameters are stored in the parameter store and included in `content_hash`; holdout labels use the fitted cut points.

---

## 7. Proposed fix plan (waves)

| Wave | Goal | Items | Exit criterion |
|---|---|---|---|
| **W1 – Decision integrity** | Make R* mathematically correct | F-01, F-02, F-03, F-38 | Objective matches spec §7.4; per-dow carve-out test green; CRN identical sick-call list across policies; policy allow-list in place |
| **W2 – Demand realism** | Correct demand process | F-42, F-04, F-05, F-06, F-21 | Notice/duration/mean/variance PPCs pass per regime; replay alignment test green |
| **W3 – Feasibility** | No illegal/double-booked schedules | F-07, F-12, F-13, F-14, F-15, F-16, F-19 | New V8 invariant gate passes on 100 chaos scenarios incl. cross-base crew |
| **W4 – Gates that can fail** | Trustworthy V&V | F-27, F-28, F-29, F-30, F-31, F-32, F-33, F-35 | Negative controls make each gate FAIL; V4 scoped to cell |
| **W5 – Decision reporting** | Honest uncertainty | F-08, F-09, F-10, F-11, F-36, F-37 | R* + indifference set with CIs; report == API |
| **W6 – Platform hardening** | Safe multi-user operation | F-39, F-40, F-41, F-24, F-26 | Load test: 5 concurrent jobs, no "database is locked", cancel honoured within 1 scenario |
| **W7 – Hygiene** | Clean-up | F-17, F-18, F-20, F-22, F-23, F-25, F-34 | Lint + docs updated |

### Re-baseline after W1–W3
After waves 1–3, **all previously produced R\* results, V&V verdicts and reports must be considered invalid** and re-run:
re-calibrate → regenerate scenarios (bump `GENERATOR_EPOCH`) → re-run grid with n ≥ 200 → re-run all gates.

---

## 8. Open questions for the business (to confirm before fixing)

1. Should R represent **peak** daily reserves, **average** daily reserves, or **reserve-days per bid period**?
2. Is standby time counted as duty for the 11 h rest rule (L2) under the Air Transat agreement? (`reserve_counts_as_duty`)
3. Long-call notice: 12 h (D12) or 14 h (`base.yaml`)?
4. Which absence types (SICK / INJURY / FAMILY) should drive open-time demand?
5. Must a cross-base reserve be deadheaded home, and who pays hotel on the return?
6. Is `uncovered_deadline_hours = 0` (cancel at report time) operationally realistic, or should it be e.g. 1–2 h?
7. Target service level (`u_max`, ε) and λ range to be signed off by Crew Planning.
8. Regime definition (F-42): does Air Transat have an operational disruption log (weather / ATC / IROPS declarations) that could feed the
   computed regime index? If not, the regime is computed from D8 delays and cancellations only (Option A) or estimated as a latent state (Option B).

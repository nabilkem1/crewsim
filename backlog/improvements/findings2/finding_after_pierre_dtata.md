# Findings after Pierre's data — code fixes to make

**Source:** the second extract in `src/crewsim/data/corpus/real_data/` (D1–D11), loaded with the project's own
loaders and gates through a temporary config, plus Pierre's email. Numbers below were measured on that
extract. **Nothing here is implemented.** Ids continue the data/reporting epic (`IMP-512` onward).

> This file lists **our** fixes. What only Pierre can fix (re-extraction, duplicates in D4, dated ids in D4/D5,
> D3 null times, definitions) is in [`answer.md`](../../../answer.md). Where a fix depends on his answer, the story
> gives an **interim behaviour**, so the code work is not blocked.

**Verified, no change needed.** `real_data/` is git-ignored (`.gitignore:40`), excluded from the wheel
(`pyproject.toml`, `**/real_data/**`), and `tests/test_project_structure.py::test_no_real_data_in_wheel` guards both.
0 files are tracked. Keep it that way: never write run output derived from this data outside `output/` (ignored).

## Index

| Story | Fix | Priority | Size | Waits for Pierre? |
|---|---|---|---|---|
| IMP-512 | Choose the corpus without editing `base.yaml` | P0 | S | no |
| IMP-513 | D8 coverage gate: active bases and operated days only | P0 | S | no |
| IMP-514 | Draft codes from config; notice-lead rule; two-way join gate | P0 | M | **definition** |
| IMP-515 | One "operated flight" rule (drop post-cutoff flights) | P0 | M | no |
| IMP-516 | Per-dataset coverage: a missing day is not a zero | P0 | L | no |
| IMP-517 | D4 canonicalisation: duplicates, absence types, constant columns | P1 | M | **source of truth** |
| IMP-518 | Pairing-id resolution (bare codes, `TS18@date`) | P1 | M | partly |
| IMP-519 | D8 operating day: UTC `date` vs local departure date | P1 | S | confirm |
| IMP-520 | Roster loader: null D3 times, overlaps, zero block hours | P0 | M | no |
| IMP-521 | Block types `SICK` / `OFFICE` / `OTHER`: handle, never skip silently | P0 | M | **meaning** |
| IMP-522 | Fleet qualification: D1 vs D2, A321 family | P1 | M | **authoritative fleet** |
| IMP-523 | D3 quality gates (legs, fleet `UNKNOWN`, credit hours) | P1 | S | no |
| IMP-524 | Generic gates: duplicates, constant columns, overlaps, future rows | P1 | M | no |
| IMP-525 | D7 pay-code registry; D10 duplicates and null crew | P1 | S | **codes** |
| IMP-526 | Scope, windows and population config for the real extract | P0 | S | no |
| IMP-527 | Calibration guards for thin data and zero-cancellation data | P1 | M | no |
| IMP-528 | D9 is derived from D8: label it, do not read it as truth | P2 | S | no |
| IMP-529 | Regression fixture of the extract's defects + readiness command | P1 | M | no |

**Suggested order:** IMP-526 and IMP-512 (so the data can be run at all) → IMP-520, IMP-521 (loader stops
crashing or lying) → IMP-515, IMP-516 (inputs stop being wrong) → IMP-513, IMP-514 (gates tell the truth) →
the P1 group → IMP-529 last, as the proof that each fix holds.

---

## P0 — nothing runs correctly without these

### IMP-512 — Choose the corpus without editing `base.yaml`
**Where:** `cli.py` (every `config.load()`, e.g. lines 205, 251, 303, 387; `--config` exists only on `grid`, line 605), `configs/base.yaml:18`.
**Problem:** the corpus is whatever `paths.corpus_dir` says. To run on `real_data/` I had to write a copy of the
config. A person doing it by hand will edit the committed file and risk committing the path.
**Fix:** a global `--config PATH` (and `CREWSIM_CONFIG` env var) on every command and in the API; add
`configs/real.yaml` (git-ignored) overriding only `paths.corpus_dir`, `paths.params_dir`, `windows`, `scope`.
Print the corpus path and a **MOCK / REAL** banner at the top of every command, report and API response.
**Test:** `crewsim --config configs/real.yaml data quality-report` reads `real_data/`; the banner says REAL.

### IMP-513 — D8 coverage gate: active bases and operated days only
**Where:** `data/quality.py:128-135` (bases), `quality.py:30-61` (`station_day_completeness`).
**Problem:** bases come from **all** D1 pilots, terminated included (`PRG, YHM, YHZ, YMX, YOW, YVR`), so the gate
reads **76.2%**. On the real crew bases it is 97.7% (YUL) and 99.3% (YYZ), 98.5% combined. The days
after the extraction cut (Sep–Oct, no actuals) also count as "covered".
**Fix:** bases = pilots with `employment_status == "ACTIVE"` (same rule as `regime.crew_bases`, `regime.py:114-124`),
and count only operated days (IMP-515). Report per base.
**Test:** a corpus with a terminated-only base passes; a missing interior day at an active base fails.

### IMP-514 — Draft codes from config; notice-lead rule; two-way join gate
**Where:** `quality.py:106-123` (hard-coded `"DRAFT_PREM"` at line 111), `gates/v6_backtest.py:63-76,114`,
`data/drafts.py:48-61`, `config.py:213-221`, `configs/base.yaml:181`.
**Problem:**
1. The gate ignores `draft_reconstruction.premium_pay_codes`, so with Pierre's codes it reads **0%** (0 draft rows).
   With `DRAFT_THX`, `DRAFT_T2` it reads **13.1%**.
2. The gate divides by **all** D6 `SHORT_NOTICE_COVER` rows (15,099), but ~11,000 are ordinary roster changes
   (median lead ~14 days; only 30% within 48 h). From the D7 side, **86.3%** of paid drafts (1,120/1,298) have a D6 row.
3. `drafts.reconstruct_drafts` has no lead-time condition, so it would call a planned roster change a draft whenever
   a premium row happens to share the pairing.
4. V6 maps sim categories to D7 codes `RESERVE_GTE`, `RESERVE_UTIL`, `DRAFT_PREM`; the extract has `RESERVE_CREDIT`,
   `DRAFT_THX`, `DRAFT_T2`.
**Fix:** (a) `premium_pay_codes: [DRAFT_THX, DRAFT_T2]` in config and use it in `quality.py`; (b) add
`draft_reconstruction.max_notice_hours` (default null = off; set after Pierre's answer); (c) the gate reports **both**
directions: D6→D7 (precision) and D7→D6 (recall), and the pass rule uses the recall direction the spec describes;
(d) move V6's sim-category → pay-code map to config (`pay_codes`, see IMP-525).
**Interim (before Pierre answers):** use the D7→D6 recall (86%) as the gate, print the D6→D7 precision as information.
**Test:** codes in config change the gate; a planned change 20 days ahead is not a draft when the notice rule is on.

### IMP-515 — One "operated flight" rule (drop post-cutoff flights)
**Where:** `calibration/regime.py:66-77`, `calibration/delays.py:44-88`, `data/profile.py`, `quality.py:128-135`. Extends IMP-205.
**Problem:** D8 September–October rows (**2,244 flights**) and 378 late-August rows have `actual_dep_local` null and
`delay_minutes = 0`. They are scheduled-only. The code reads them as on-time flights: September's share of delays ≥ 15 min
is 0.0 against 0.15–0.28 in the months before. Overall 11.7% of flights have no actuals. They would label September CALM.
**Fix:** one helper `loaders.operated_flights(cfg)` returning D8 rows that are cancelled **or** have an actual departure.
All callers use it. Add `data.cutoff` (date, optional, auto-detected as the last day with actuals) and drop later rows.
Count and print what was dropped.
**Test:** rows with null actuals and `cancelled = 0` are excluded; delay probability of a month with only such rows is undefined, not 0.

### IMP-516 — Per-dataset coverage: a missing day is not a zero
**Where:** `regime.py:127-184` (obs; sick masked only where exposure ≤ 0, lines 178-180), `nhpp.py:62-94`
(grid from the regime table, then `fill_null(0)` at line 94), `roster_loader.py:12-42`, `configs/base.yaml:24-34`.
**Problem (measured):**
- **D4 starts on 1 June.** On the winter fit (17 Dec – 30 Apr) the HMM sees **0 sick calls** on 30 days that have exposure, and
  fits all sick rates to 0.0. Days outside D4's period are treated as "zero sick calls", not "unknown". The NB design
  matrix has the same flaw (`fill_null(0)`).
- **D2 is cut off after ~12 June.** PAIRING blocks fall from 113–136 a day to 17, 4, 2, 2. The exposure on 15–17 June is 12, 4, 2 crew while
  ~12 sick calls a day continue, so the HMM fits a state with **3.5 sick calls per crew-day**.
- The fitting window (2023-08..2025-07) holds no data, so `run_pipeline` raises; the template window (20 Mar – 1 May) starts 12 days before D2 does.
**Fix:** a `data/coverage.py` that gives each dataset a **valid interval** (`data.coverage` in config, else auto-detected: first/last
day above a fraction of the median daily volume). Then:
(a) HMM obs: set exposure and sick count to "unknown" (the likelihood treats it as uninformative) outside the D4 ∩ D2 interval;
(b) NB grid: restrict to days inside D4's interval; (c) `select_template_window` must lie inside D2's interval, else raise with the interval;
(d) windows validation: fitting and holdout must lie inside the data's valid span, with a clear message and no silent empty fit.
**Test:** a corpus with D4 starting later than D2 gives sick rate 0 only where D4 exists; a truncated D2 tail is excluded from exposure.

### IMP-520 — Roster loader: null D3 times, overlaps, zero block hours
**Where:** `engine/roster_loader.py:45-74` (duty periods), `:190-208` (`duty_end_local + utc_offset`), `:216-229` (L0 raise).
**Problem:**
- 765 duty periods (548 pairings; 73 used by D2) have null report/release. `duty_end_local + utc_offset` raises `TypeError`
  (`roster_loader.py:199`), so `load_rosters(cfg)` crashes for anyone whose calendar uses them.
- Even once fixed, the L0 check raises `ValueError` on any overlap. D2 has **500 overlapping blocks** in 321 crews
  (204 PAIRING↔PAIRING, 244 PAIRING↔DAY_OFF). Median overlap 3.2 h, up to 24 h.
- `block_hours` is 0 for 11,155 legs and null for 1,843, so `flight_mins` (L3) is wrong or 0 for 45% of pairings.
**Fix:** (a) skip or fall back to the D2 block span when a duty period has null times, and **count** it in the exclusion counts;
(b) reconcile overlaps by rule: trim `DAY_OFF`/`VACATION`/`OTHER` to the start of an overlapping PAIRING, report PAIRING↔PAIRING
as a data defect (count, do not crash, drop the later block, name the crew); (c) when `block_hours` is 0 or null derive it from
`arr_local − dep_local` and flag the pairing `flight_hours_estimated`.
**Test:** a crew with a null-time pairing loads with an exclusion count; a DAY_OFF overlapping a pairing is trimmed; a PAIRING↔PAIRING overlap is reported.

### IMP-521 — Block types `SICK` / `OFFICE` / `OTHER`: handle, never skip silently
**Where:** `engine/state.py:5-21`, `engine/roster_loader.py:174-178` (`except ValueError: continue`), `quality.py:12-14,178-184`, `engine/legality.py` (`OCCUPYING_BLOCKS`).
**Problem:** D2 carries `SICK` 4,429, `OTHER` 1,168, `OFFICE` 1,001 (**16% of blocks**). `BlockType(...)` raises `ValueError` and the loader
**skips** them, so a pilot who is sick or in the office looks free and is offered a draft or reserve call. The gate also fails them.
**Fix:** until Pierre defines them: `SICK` → `ABSENCE` (unavailable; already in `OCCUPYING_BLOCKS`), `OFFICE` → unavailable non-duty block,
`OTHER` → unavailable **and counted**. Make the unknown-type branch **raise** (or count in `exclusion_counts`) instead of `continue`. Add the types to
`VALID_BLOCK_TYPES`. Config: `roster.block_type_map` so the mapping is data, not code.
**Test:** a crew with a `SICK` block is rejected by eligibility on that day; an unmapped type fails loudly.

### IMP-526 — Scope, windows and population config for the real extract
**Where:** `configs/base.yaml` (`windows` 33-34, `scope` 37-42, `population.roster_size` 108), `config.py:72-107`.
**Problem:** scope `YUL / A321neoLR / FO` has **1 ACTIVE pilot** in D1 (12 in D2; 1 reserve), against `roster_size: 120`. Windows hold no data.
Real bases are YUL and YYZ only (no ACTIVE YVR pilots).
**Fix:** a real-data config (see IMP-512) with: scope = A321 family at YUL (after IMP-522), windows inside the valid interval of IMP-516,
`roster_size` from the data or marked `[CONFIRM]`. Do not change the committed mock config.
**Test:** `crewsim doctor` on the real config prints rostered crew, reserves and valid windows without a `[WARN]` about empty scope.

---

## P1 — before any calibration is believed

### IMP-517 — D4 canonicalisation: duplicates, absence types, constant columns
**Where:** `nhpp.py:82-87`, `regime.py:79-84`, `nhpp.py:145-148`; new `data/clean.py`. Extends IMP-203.
**Problem:** **415 of 1,527 rows (27%)** are exact copies (same crew, dates, type, pairing; up to 36 copies); 802 absences overlap for the same crew.
Raw counts feed every sick-call fit. `notification_ts` is exactly 12:00 on **all** rows. Only SICK and FAMILY exist.
**Fix:** `clean.dedupe_absences` (key: crew, start, end, type) used by both fitters and the quality gate; `calibration.absence_types` (IMP-203);
flag a constant `notification_ts` and do **not** use it for notice-time calibration. Report rows removed in the store diagnostics.
**Interim:** de-duplicate on the exact key; prefer D4 over D2 `SICK` blocks for counts (pending Pierre).
**Test:** the 36-copy case counts once; the removed count is in the report.

### IMP-518 — Pairing-id resolution (bare codes, `TS18@date`)
**Where:** `quality.py:85-103` (D4 link), `:143-158` (referential integrity), new `data/ids.py`.
**Problem:** D4 (857 bare `G####`) and D5 (all) use the rotation code without the date, so the linkage reads **0%**. Recoverable for 1,089 of 1,400 D4 rows (78%) with `code + absence_start`.
D6 has 222 ids like `TS18@2026-05-18`. D7 has 42 orphans.
**Fix:** `ids.resolve_pairing(code, date, d3)` with a documented rule; the gate reports **exact** and **resolvable** rates separately and passes only on exact unless
`quality_gates.allow_resolved_ids` is on (then flagged). Normalise the `FLIGHT@date` form or list it as a defect.
**Test:** a bare code with a unique date resolves; an ambiguous one is reported, not guessed.

### IMP-519 — D8 operating day: UTC `date` vs local departure date
**Where:** `regime.py:66-77` (group by `date`), `delays.py:64-77` (join on `date`).
**Problem:** `date` differs from the local scheduled departure date for **5,349 of 22,421 flights (24%)**; e.g. a 20:10 EST departure carries the next UTC day. D4 and D2 use local dates, so the HMM mixes two day definitions.
**Fix:** `calibration.flight_day: sched_dep_local | date` (default `sched_dep_local` for the real extract); one helper `loaders.flight_day(d8)`.
**Test:** a flight at 20:10 local is counted on its local day.

### IMP-522 — Fleet qualification: D1 vs D2, A321 family
**Where:** `roster_loader.py:112-114,141-147,243-257`, `engine/legality.py:163-169` (`item.fleet not in crew.fleet_quals`), `engine/cascade.py:68`, `des.py:429`.
**Problem:** the loader sets `fleet_quals = {D1.fleet}`. In the extract D1's fleet disagrees with D2 for **365 of 725** crews (248 are D1 `A320-200` flying `A321-200`),
and `A321-200` vs `A321neoLR` are different strings, so L6 rejects a pilot for the other A321.
**Fix:** `fleet_groups` in config (e.g. `A321: [A321-200, A321neoLR]`); `fleet_quals` = the group plus D2's fleet; scope matches on the group.
Use the **D2** fleet for the roster period unless Pierre says D1 is authoritative.
**Test:** an A321-200 pilot is legal on an A321neoLR pairing when they share a group; an A330 pilot is not.

### IMP-523 — D3 quality gates
**Where:** `quality.py` (new checks), `roster_loader.py:57-74`.
**Problem:** none of these is gated: legs with `block_hours` 0 (25.6%) or null (4.2%), 1,055 legs with null times, 72 with arrival ≤ departure, 818 shorter than 10 minutes,
739 pairings with fleet `UNKNOWN`, 711 with `credit_hours` null or ≤ 0.
**Fix:** rates with thresholds in `quality_gates` (e.g. `d3_leg_complete_pass`, `d3_known_fleet_pass`); a failing D3 gate blocks `roster` commands unless `--allow-marginal`.
**Test:** the extract fails; the mock passes.

### IMP-524 — Generic gates: duplicates, constant columns, overlaps, future rows
**Where:** `quality.py` (new), `loaders.py`.
**Problem:** the gates miss defects that are visible in this extract: exact duplicate rows (D4 27%, D10 8.3%, D7 8, D8 7), constant columns
(`D4.notification_ts` 12:00, `D5.call_ts` 00:00, `D5.report_ts` = +2.5 h, `D5.outcome` always `assigned`, `D8.iata_delay_code` 100% null, `D8.cancelled` always 0),
D2 overlaps per crew, rows after the cutoff.
**Fix:** four generic checks run on every dataset: `duplicate_rate`, `constant_column` (a column with one value over > N rows), `null_rate` for key columns,
`overlap` for D2 per crew. Thresholds in config; results in the same report and API.
**Test:** each defect in the fixture of IMP-529 trips exactly one check.

### IMP-525 — D7 pay-code registry; D10 duplicates and null crew
**Where:** `gates/v6_backtest.py:63-76,102-115`, `quality.py`, `config`.
**Problem:** D7 has codes no one maps: `T_1_4` (2,179), `AJU` (1,287), `MIN` (980), `DMG`, `BME`, `RED_CAP` (~4,500 rows) and 169 negative amounts. D10 has 8.3% duplicates, and 21% null
`crew_id`, which V6 drops silently when it filters to scope crew (`v6_backtest.py:109-111`).
**Fix:** `pay_codes:` registry in config (`code → {meaning, comparable_to: RESERVE_STAFFING|RESERVE_UTILIZATION|DRAFT|ignore}`); warn on any code not in it; V6 reads it. Report D10
rows dropped for null crew and de-duplicate exact copies.
**Interim:** unmapped codes are `ignore` and listed in the V6 report.

### IMP-527 — Calibration guards for thin data and zero-cancellation data
**Where:** `regime.py:248-261`, `calibration/hmm.py:126-129`, `nhpp.py:139-141`, `pipeline.py:163-169`. Links IMP-207, IMP-220.
**Problem:** with 135 days and no cancellations or sick calls the HMM still "converges" (3 of 8 restarts at best) with cancel probability 1e-6 and sick rate 0.0 in all four states, and
a fit with 1 of 8 restarts at best on summer. `obs.height < 2` is the only size guard. One season gives a GLM with one `season` level.
**Fix:** `calibration.regime_hmm.min_days` and `min_sequences` (fail with the counts); drop a stream whose total is 0 from the likelihood and record `streams_used`; warn when `restarts_reaching_best` is below a configured fraction or a state sits at the `min_probability` floor; refuse a GLM covariate with a single level.
**Test:** the winter fit on this extract reports `streams_used: [flights]` instead of fabricating sick rates.

### IMP-529 — Regression fixture of the extract's defects + readiness command
**Where:** `tests/data/`, `crewsim data` CLI.
**Fix:** a small synthetic corpus (`tests/data/fixtures/real_like/`) that reproduces each defect above: duplicated D4 rows, bare D4/D5 ids, post-cutoff D8 rows, truncated D2 tail, D4 later than D2,
`SICK/OFFICE/OTHER` blocks, overlapping blocks, null D3 times, D1/D2 fleet mismatch, constant columns. One test per fix asserts the behaviour.
Add `crewsim data readiness`: one table of every gate with PASS/FAIL and the **valid windows** (IMP-516), so "can we calibrate?" has one answer.
**Test:** the readiness command exits non-zero on the fixture and on the current extract; zero on the mock.

---

## P2

### IMP-528 — D9 is derived from D8: label it, do not read it as truth
**Where:** `calibration/regime.py:495-531` (`label_agreement`), `api/routers/calibration.py`, `pipeline.py:152-159`.
**Problem:** Pierre's D9 is a deterministic function of D8 (mean departure delay; ≥ 1 cancellation; thresholds 5/20/45), and 65% of station-days have 2 flights or fewer. Agreement with it measures similarity to a
threshold rule, not the HMM's accuracy as on the mock (where D9 is the generator's hidden truth). I could reproduce 91% of it from D8 across all stations, but only **71% at YUL/YYZ**, so the rule used is not exactly the one in the email.
**Fix:** a `d9_source: generator_truth | derived_rule | unknown` setting; the diagnostic prints which it is and never states "recovery accuracy" for a derived rule.

---

## Before / after targets

| Check | Now (real extract) | Target after the fixes |
|---|---|---|
| `run_pipeline` on the real config | raises: no data in the fitting window | runs on a configured valid window, or refuses with the valid interval |
| D8 coverage | 76.2% | ≥ 98% on active bases, operated days |
| D6/D7 recovery | 0% (13.1% with the right codes) | measured by the D7→D6 direction (86% on this data) |
| D4 linkage | 0% | exact and resolvable rates reported (78% resolvable) |
| D2 block-type domain | FAIL (6,598 blocks) | types handled by config, none skipped silently |
| `load_rosters(cfg)` | `TypeError` at `roster_loader.py:199` | loads; defects counted, none crash |
| Winter HMM sick rates | 0.0 in every state | stream marked unused (no D4 coverage) |
| Summer HMM top sick rate | 3.48 per crew-day | no state fitted on the truncated D2 tail |
| Delay probability, September | 0.0 | undefined (no operated flights) |

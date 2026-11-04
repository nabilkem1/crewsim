# Findings — Correctness

**6 new stories** · Source: code analysis of the working tree (October 2026) · Gate: all V1–V9
re-run green, with before/after E[C], CVaR95 and R* recorded for any story that changes simulated costs.

The analysis found 11 correctness issues. Five of them are already tracked by existing stories, so
they are **not** repeated here (see [Already tracked](#already-tracked)). The six below are new.

---

## [DONE] IMP-116 — L8 notice uses the same reserve block as eligibility
**Size:** `S` | **Category:** Must fix | **Depends on:** — | **Source:** `engine/legality.py:208-235`, `engine/eligibility.py:121`

**As a** planner **I want** a reserve to be held to the short-call or long-call notice rule whenever they are picked as a reserve
**so that** reserves are not called in on a line holder's notice rule (0 h today).

### Problem
- The eligibility pool admits a reserve if a RESERVE block covers the **report time** (`is_on_call_at(r, item.start)`, `eligibility.py:121`).
- L8 looks up the reserve type from the block covering the **call time** (`b.start <= now < b.end`, `legality.py:212-216`).
- A reserve called while **between shifts**, for a duty in their next shift, therefore gets `reserve_type = None`. L8 then applies the line-holder rule (`line_holder_draft_notice_hours`, 0.0 today) instead of the 2 h short-call or 14 h long-call notice.
- Side effect: this is currently the main way a long-call reserve can be called at all (see IMP-117). Fixing it may sharply reduce long-call utilisation.

### Acceptance Criteria
- [x] L8 decides "is this a reserve call?" with the same rule the pool uses. A crew member admitted through the reserve pool is always checked against the SC/LC notice, never against the line-holder notice.
- [x] The rule for picking the SC/LC type is written down in the docstring: the block covering the call, or else the block covering the report. It must match the reasoning in `legality.py:208-211`.
- [x] Regression test: a reserve whose shift starts after `now` and covers `item.start` is checked against the SC/LC notice. With less notice than that, the call is illegal.
- [x] Regression test: a line holder (no RESERVE block at all) still gets `line_holder_draft_notice_hours`.
- [ ] Re-baseline: record SC/LC reserve utilisation and E[C]/CVaR95/R* for R4–R14 before and after. *Partly done: R4/R10/R14 at 20 scenarios, below. R6/R8, R* and the V1–V9 re-run are still open.*

### Verification
*   **Automated:** `pytest tests/engine/test_legality.py -k "l8 and between_shifts"`
*   **Manual:** `crewsim explain-legality --crew <a reserve> --pairing <pairing reporting in their next shift>`
    *   **Expect:** the L8 line names SC or LC notice and states the required hours
    *   **Fails if:** it reports "for a line holder" for a crew member on a reserve line

### How it was implemented
- New `legality.reserve_call_type_for(crew, item, now)`. It returns the call type of the RESERVE block covering `now`, or else of the block covering `item.start` (the block that admitted the reserve to the pool). It returns `None` only when neither exists. `check_l8_notice_time` uses it.
- `on_call_block` moved from `eligibility.py` to `legality.py`, which eligibility already imports, so both use one definition. `eligibility` re-exports it under the same name.
- Tests: `test_l8_between_shifts_reserve_gets_reserve_notice`, `test_l8_between_shifts_long_call_reserve_gets_long_call_notice` and `test_l8_line_holder_still_gets_line_holder_notice` in `tests/engine/test_legality.py`.

**Before/after** (`master` seed, 20 scenarios, mean per scenario, measurement window):

| Policy | E[C] before | E[C] after | CVaR95 before | CVaR95 after | Reserve assignments before → after |
|---|---|---|---|---|---|
| R4 | $96,325 | $95,776 | $113,331 | $112,686 | 53.3 → 51.8 |
| R10 | $174,629 | $174,879 | $191,939 | $191,939 | 125.8 → 124.5 |
| R14 | $200,058 | $200,447 | $213,421 | $213,099 | 145.6 → 144.0 |

Effect on cost is under 0.6%. The 2 h short-call notice rarely binds; the change mainly affects how calls are classified (see IMP-117).

---

## [DONE] IMP-117 — Long-call reserves are either usable or not bought
**Size:** `M` | **Category:** Verify first, then must fix | **Depends on:** IMP-116, Crew Planning answer | **Source:** `configs/base.yaml:185-188,200`, `config.py:422-450`, `configs/policies/R*.yaml`, `data/corpus/d12_agreement_rules.yaml:14`

**As a** planner **I want** every reserve a policy pays for to have a real chance of being used
**so that** R* is not biased by paying for long-call reserves the model can never call.

### Problem
- `long_call_notice_hours` is 14 h in the working tree. It was 12 h in the last commit; the change is uncommitted. The D12 agreement rules say 12 h, and the tests use 12 h.
- Every standby shift is 10–12 h long (`base.yaml:186-188`). `open_question_warnings` (`config.py:422-450`) prints at every load that long-call utilisation is "structurally zero".
- Every policy still buys long-call reserves (R4: 2, R6: 2, R8: 3, R10: 4, R14: 5) at the long-call daily guarantee (`costs_pilots.yaml:15`).
- **The warning's reasoning is not fully right.** It assumes the call and the report fall in the same shift. A reserve on consecutive standby days can be called in one shift for a report in the next, with ≥ 14 h notice. Today they can also slip through the IMP-116 loophole. Actual long-call utilisation is therefore unknown and must be measured first.
- The warning's docstring still describes the old whole-duty-coverage rule (`config.py:427-432`), which OPEN-4 replaced.

### Acceptance Criteria
- [x] Measure first: per policy, the number of long-call reserve-days and long-call assignments over 20 scenarios, before and after IMP-116. Record the numbers in the story sign-off.
- [x] `long_call_notice_hours` agrees with the D12 agreement rules, or the difference is recorded as a decision with a `[CONFIRM: Crew Planning]` note. The uncommitted 12 → 14 change is either committed with that reason or reverted. *Decision (user, October 2026): `configs/base.yaml` is the only source; 14 h is kept and the difference from D12's 12 h is recorded next to the key. The change is still uncommitted.*
- [x] If long-call utilisation is zero (or close to zero) for a policy, the run states it in the KPIs and the report. A reserve type that is paid for and never used is shown, not hidden.
- [x] Following the Crew Planning answer, one of (a) to (c). *Not needed: the measurement below shows long-call reserves are used heavily. The premise that they could never be called was wrong.*
- [x] `open_question_warnings` states the cross-shift case correctly, and its docstring no longer mentions whole-duty coverage.
- [x] Test: a config whose long-call reserves can never be called produces a warning that names the affected policies.

### Verification
*   **Automated:** `pytest tests/reporting/test_kpis.py -k call_type` and `pytest tests/test_config.py -k long_call`
*   **Manual:** `crewsim run --policy R10 --scenarios 20 --kpis`
    *   **Expect:** long-call reserve-days and long-call assignments shown as separate figures
    *   **Fails if:** long-call cost is booked with no way to see whether any long-call reserve was used

### How it was implemented
- **Side table for call types.** `des.Simulation.reserve_call_types` records the SC/LC type behind every RESERVE_STAFFING and RESERVE_UTILIZATION row, keyed by (crew_id, sim_time, event_uid). It is filled by `costs.book_reserve_staffing(call_types=...)` and by both reserve-assignment paths. It is a side table, not a new ledger column, because gate V7 compares ledger hashes.
- **KPI.** `kpis.reserve_usage_by_call_type` and `unused_paid_call_types`, exposed in `compute_kpis` as `reserve_by_call_type` and `unused_paid_call_types`. They are printed by `--kpis` (with a `[WARN]` line if a call type is paid for but never used), added to the API scoreboard, and shown as a new HTML report table, "Reserve usage by call type".
- **Warning text.** `config.open_question_warnings` now describes the cross-shift case and names the policies that buy long-call reserves (`config.policies_buying_long_call`).

**Measured** (`master` seed, 20 scenarios, mean per scenario, measurement window):

| Policy | LC reserve-days paid | LC assignments before IMP-116 | LC assignments after IMP-116 |
|---|---|---|---|
| R4 | 30.0 | 5.25 | 28.40 |
| R10 | 63.0 | 10.80 | 41.00 |
| R14 | 80.0 | 12.05 | 48.10 |

"Before" undercounts long-call usage: a reserve called between shifts was labelled as a line holder at that time. In both columns, long-call reserves are used at every R tested.

---

## [DONE] IMP-118 — The reserve bid rule, its comment and its test agree
**Size:** `S` | **Category:** Must fix | **Depends on:** Crew Planning answer | **Source:** `configs/base.yaml:68-71`, `engine/roster_loader.py:273-279`, `tests/engine/test_headcount.py:103-106`

**As a** planner **I want** reserves to be chosen from the right end of the seniority list
**so that** the crew carved out as reserves (and the lines they give up) match how the bid really resolves.

### Problem
- The working tree sets `reserve_bid_rule: senior_first`. This change is uncommitted; the last commit had `junior_first`.
- The comment on the same key says junior-first is how a seniority bid resolves, and that it is the default.
- The comment in `roster_loader.py:274-277` says the same.
- `tests/engine/test_headcount.py::test_reserve_bid_rule_selects_junior_crew_by_default` **fails** on the working tree (`assert 'senior_first' == 'junior_first'`).
- The rule decides which crew become reserves, and so which pairings are displaced. It changes both cost and R*.

### Acceptance Criteria
- [x] The value is decided with Crew Planning and recorded with a `[CONFIRM]` note or a decision date. *Confirmed by the business owner on 2026-10-20: `senior_first`. In `base.yaml` the `[CONFIRM: Crew Planning]` marker is now `CONFIRMED 2026-10-20`, so it no longer appears in the outstanding-flags list.*
- [x] The YAML comment, the `roster_loader.py` comment and the test all describe the chosen value.
- [x] `pytest tests/engine/test_headcount.py` passes.
- [x] If the value changes from the last commit, before/after E[C], CVaR95 and R* are recorded.

### Verification
*   **Automated:** `pytest tests/engine/test_headcount.py`
*   **Manual:** `crewsim roster summary`
    *   **Expect:** the reserves listed sit at the end of the seniority list that the config names
    *   **Fails if:** the comment and the selected crew disagree

### How it was implemented
- The `base.yaml` and `roster_loader.py` comments now describe `senior_first`.
- In `test_headcount.py`, `test_reserve_bid_rule_default_is_senior_first` asserts the default, and `test_junior_first_bid_rule_inverts_the_selection` checks the other setting.
- `tests/test_cli.py::test_cli_explain_crew_scenario` hard-coded P00448, a crew member who is a reserve only under `junior_first`. It now finds a reserve that was really assigned in scenario 0 under R10.

**Before/after** (`master` seed, 20 scenarios, after IMP-116):

| Policy | E[C] junior_first | E[C] senior_first | CVaR95 junior_first | CVaR95 senior_first |
|---|---|---|---|---|
| R4 | $67,691 | $95,776 | $86,296 | $112,686 |
| R6 | $82,706 | $124,448 | $101,648 | $139,244 |
| R8 | $91,283 | $139,725 | $109,641 | $155,319 |
| R10 | $104,856 | $174,879 | $123,171 | $191,939 |
| R14 | $112,800 | $200,447 | $129,086 | $213,099 |

R* = 4 under both rules (λ = 0 and λ = 1), but `senior_first` raises E[C] by 41–78%. This setting matters a great deal for the absolute cost figures, which is why it needed the confirmation above.

---

## [DONE] IMP-119 — A reserve shortfall is reported, not silent
**Size:** `S` | **Category:** Should | **Depends on:** — | **Source:** `engine/roster_loader.py:242-248,262-291`

**As a** planner **I want** to know when a policy asks for more reserves than the roster can supply
**so that** a policy labelled R14 is never quietly simulated with fewer reserves.

### Problem
- `res = crew_list[:n_res]` (`roster_loader.py:281`) returns fewer reserves when a group has fewer than `n_res` active crew. Nothing is logged and nothing fails.
- The SC/LC split takes the first `sc_n` reserves as short-call (`roster_loader.py:307`). A shortfall therefore comes entirely out of long-call, which hides it further.
- The policy is still reported under its name, and its R is read from the name (IMP-212/IMP-509).

### Acceptance Criteria
- [x] `load_rosters` returns, or logs, the requested and actual reserve count for each (base, fleet, position). *It raises with both counts instead.*
- [x] A shortfall either raises (default), or is allowed by an explicit config flag and then shown in the KPIs and the report. *It always raises. No override flag was added because nothing needs one; add it only if a use appears.*
- [x] Test: a policy asking for more reserves than active crew in a group raises an error naming the group and both counts.

### Verification
*   **Automated:** `pytest tests/engine/test_headcount.py -k shortfall`
*   **Manual:** copy `R14.yaml` with `short_call: 200`, then run `crewsim run --policy <copy> --scenarios 1`
    *   **Expect:** an error naming YUL/A321neoLR/FO, 200 requested, and the number available
    *   **Fails if:** the run completes

### How it was implemented
- `roster_loader._check_reserve_shortfall` runs before the carve-out. It raises `ReserveShortfallError` (a `ValueError`) listing each short group as `base/fleet/position: N requested, M active crew available`.
- Groups outside the current load's own filter are skipped.
- Tests: `test_reserve_shortfall_raises`, and `test_reserve_count_equal_to_headcount_is_not_a_shortfall` (the boundary gate V1 relies on).

---

## [DONE] IMP-213 — Swept and declared parameters have an effect, or say they don't
**Size:** `M` | **Category:** Should | **Depends on:** — | **Source:** `configs/base.yaml:57,81,88`, `gates/v9_sensitivity.py:61-79,91-141`, `cli.py:1153-1156`, `config.py:507-539`

**As a** validator **I want** gate V9 to sweep only parameters that change the result
**so that** a "stable" verdict means robustness, not a parameter that is never read.

### Problem
- `population.roster_size` is not read by the engine. The roster comes from the corpus (about 112 active crew).
- V9 still sweeps it over `[100, 120, 140]` and counts the identical results as stability evidence. A CLI notice (`cli.py:1153-1156`) admits this.
- `demand.pairings_per_bid_period` is declared but not read either (`config.py:507-539`). Its notice is built twice: from the registry and again by hand.

### Acceptance Criteria
- [x] Either `roster_size` drives the roster (by scaling or sub-sampling the active crew, with CRN kept), or it is removed from `sensitivity`. V9 then reports it as "not swept" rather than "stable". *Third option taken: the key stays in `sensitivity`, but on the real V9 path the axis is reduced to the configured value and reported as not swept.*
- [x] V9 refuses to report a parameter as stable if every point in its sweep gives the same result for an engine-invariant reason. As a minimum, the result is marked `NOT_EXERCISED` for such parameters.
- [x] `unconsumed_notices` builds each notice once, from `DECLARED_NOT_YET_CONSUMED` only.
- [x] The `roster_size` comment in `base.yaml` says what the value does today.

### Verification
*   **Automated:** `pytest tests/gates/test_v9_sensitivity.py -k "roster_size or not_exercised or unconsumed"`
*   **Manual:** `crewsim gate v9`
    *   **Expect:** `roster_size` is either reported as changing R*, or listed as not exercised
    *   **Fails if:** it is counted as a stable parameter with no effect on the engine

### How it was implemented
- `v9_sensitivity.ENGINE_INVARIANT_PARAMETERS` names `roster_size` and gives the reason.
- On the real path, `run_v9_gate` reduces that axis to `population.roster_size`. It returns `parameters` (EXERCISED / NOT_EXERCISED per parameter) and `not_exercised` (the reasons).
- `print_v9_report` prints `[NOT_EXERCISED] roster_size: ...` and lists only the parameters actually swept. The old CLI notice was removed.
- An injected `mock_r_function` still sweeps every axis.
- `unconsumed_notices` now builds its notices in one loop over the registry.

---

## [DONE] IMP-412 — The package version is the same whether or not crewsim is installed
**Size:** `S` | **Category:** Should | **Depends on:** — | **Source:** `engine/des.py:50-54`, `scenarios/generator.py:86-105`, `calibration/pipeline.py:78-81`, `__init__.py:6`, `readme.md` (`PYTHONPATH=src`)

**As a** developer **I want** the parameter store found whatever way I run the code
**so that** a run from source never looks for `params_vunknown_*.json`.

### Problem
- Three separate helpers call `importlib.metadata.version("crewsim")`. Each falls back to `"unknown"` when the package is not installed, which is the case when following the README's `PYTHONPATH=src` instructions.
- Calibration then writes `params_vunknown_<season>.json`. An installed run looks for `params_v0.1.0_<season>.json`, and the reverse also fails.
- `crewsim.__version__ = "0.1.0"` exists but is never used as the fallback.

### Acceptance Criteria
- [x] One `crewsim.version()` helper: installed metadata first, then `crewsim.__version__`. Never `"unknown"`. *Named `crewsim.package_version()`.*
- [x] `des.py`, `generator.py` and `pipeline.py` use it. The duplicate helpers are deleted (this overlaps one item in IMP-607).
- [x] A test checks that `__version__` matches `pyproject.toml`'s `version`.
- [x] A test with `importlib.metadata.version` patched to raise checks that the parameter-store path still uses the real version.

### Verification
*   **Automated:** `pytest tests/test_project_structure.py -k version`
*   **Manual:** `$env:PYTHONPATH="src"; python -m crewsim calibrate --emit --season winter_sun` in a fresh venv without crewsim installed
    *   **Expect:** `output/params/params_v0.1.0_winter_sun.json`
    *   **Fails if:** `params_vunknown_winter_sun.json`

### How it was implemented
- `crewsim.package_version()` reads the installed metadata and falls back to `__version__` on `PackageNotFoundError`.
- `config.params_store_filename(season)` and `config.params_store_path(cfg, season)` build the file name in one place. Calibration (the writer), scenario generation, the simulation and provenance (the readers) all use them.
- The three `_package_version`/`"unknown"` copies were deleted.
- The writer joins the file name onto the directory `ensure_dir` returns. Tests redirect that directory to a temp folder, so tests never overwrite the real parameter store.

---

## Already tracked

These correctness issues are already covered by existing stories. No new story was written. Any
detail the existing story lacks is listed in the "Gap" column; add it to that story's acceptance criteria.

| Issue | Evidence | Covered by | Gap |
|---|---|---|---|
| A job cancelled while queued is started anyway | `api/routers/processing.py:201,526`, `calibration.py:78`, `jobs.py:54` | IMP-402 | None. Its first criterion covers `queued → running`. |
| `cost_by_category` does not add up to `expected_cost` (it includes DELAY_AMBIENT) | `reporting/kpis.py:168-187`, `engine/des.py:1179`, `api/routers/processing.py:326-328` | IMP-511 | Also fix the "always sums back to expected_cost" comment at `processing.py:326-328`. |
| V9 findings order changes between runs | `gates/v9_sensitivity.py:144` | IMP-212 | None |
| R is parsed from the policy name instead of `Policy.total_reserves()` | `reporting/recommendation.py:17,46`, `gates/v9_sensitivity.py:44` | IMP-212, IMP-509 | IMP-509 still says "parsed with the shared regex". Prefer reading R from the policy contents in both. |
| Parameter store is written non-atomically | `calibration/pipeline.py:141` | IMP-403 | None |
| Fleet filter uses a regex `contains` | `engine/roster_loader.py:114` | IMP-608 | None |
| Policy fields `dow`, `reserve_selection` and `mode` are never read | `engine/policy.py:22,31,38` | IMP-607 | None |

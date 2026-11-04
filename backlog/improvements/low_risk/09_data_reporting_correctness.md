# IMP-E5 — Data & Reporting Correctness

**11 stories** · **Low risk** (see [README](README.md)). IMP-501 to IMP-503 become must-fix if the
data owner confirms that D4/D3 times are local · Gate: V3 and V4 historical targets recomputed after IMP-501 to
IMP-506, with before/after values recorded. Report and API show identical R* for identical inputs.

The historical targets that the gates compare against are rebuilt from raw data. A time-zone skew
or a biased denominator moves the target itself, so the gate then checks the simulation against the
wrong number.

---

## [TODO] IMP-501 — UTC datetime columns are time-zone aware
**Size:** `S` | **Depends on:** — | **Source:** `data/loaders.py:235-236,249-250`, `data/cascades.py:108-110`

**As a** developer **I want** `*_utc` columns typed as UTC and `*_local` columns left naive
**so that** mixing them is a type error rather than a silent 4–5 hour offset.

### Acceptance Criteria
- [ ] Each schema declares a `datetime_utc` or `datetime_local` kind. Loaders apply `.dt.replace_time_zone("UTC")` to UTC columns.
- [ ] Window bounds used against UTC columns are built time-zone aware (`cascades.py:108-110` and the roster loader)
- [ ] Datetime parsing rejects an unpadded hour (`T4:08`), consistent with the documented format, or the format is widened deliberately with a test

### Verification
*   **Automated:** `pytest tests/data/test_loaders.py -k tz_aware`
*   **Manual:** `crewsim data head --dataset d2_rosters --rows 3`
    *   **Expect:** `start_utc` shown with a `UTC` time zone; `start_local` naive
    *   **Fails if:** both are naive

---

## [TODO] IMP-502 — Absence timestamps use the same clock as crew calendars
**Size:** `M` | **Depends on:** IMP-501 | **Source:** `data/eligibility_target.py:53-56,77`, `engine/replay.py:79-99`, `engine/roster_loader.py:103-104,180-185`

**As a** validator **I want** D4 notification times converted to UTC minutes before they are compared with UTC calendars
**so that** the V3 target and the historical replay are not shifted by the base's UTC offset.

### Acceptance Criteria
- [ ] Each D4 local timestamp is converted using the crew's base time zone (an IANA zone per base, in config), handling DST
- [ ] One shared `to_minutes(ts_utc, anchor_utc)` helper replaces the three anchor implementations (`eligibility_target.py:55`, `roster_loader.py:162`, `replay.py:83-88`)
- [ ] The inclusive/exclusive convention for `absence_end` is documented and tested, and `replay.py:88` follows it
- [ ] The V3 historical mean is recomputed. Before/after values are recorded in the sign-off.

### Verification
*   **Automated:** `pytest tests/data/test_eligibility_table.py -k utc`
*   **Manual:** `crewsim data eligibility-target --window holdout`
    *   **Expect:** the output states "times converted from <zone> to UTC"; the mean differs from the pre-fix value (recorded)
    *   **Fails if:** no conversion is stated

---

## [TODO] IMP-503 — Each D3 duty period uses its own UTC offset
**Size:** `M` | **Depends on:** IMP-501, data-owner answer | **Source:** `engine/roster_loader.py:196-199`

**As a** planner **I want** outstation duty times converted with the outstation's offset
**so that** duty lengths and rest are correct for trips that cross time zones or a DST change.

### Acceptance Criteria
- [ ] The convention for D3 `*_local` times is confirmed and recorded as a `[CONFIRM]` until then
- [ ] Each duty period's report and release times are converted using the departure and arrival station zones (a station → IANA zone map, from D9 stations or config)
- [ ] Test: a YUL→TLS→YUL pairing gives the correct UTC duty lengths. A pairing spanning a DST change keeps its true duration.

### Verification
*   **Automated:** `pytest tests/engine/test_roster_loader.py -k outstation_offset`
*   **Manual:** `crewsim explain-crew --crew <a transatlantic crew> --timeline`
    *   **Expect:** duty lengths match the D3 legs' block plus report/release times
    *   **Fails if:** a duty is several hours too long or too short

---

## [TODO] IMP-504 — The D6/D7 quality gate measures what the reconstruction uses
**Size:** `S` | **Depends on:** — | **Source:** `data/quality.py:12-15,56,81-118,164-186`, `data/drafts.py:48-61`

**As a** data owner **I want** the payroll-join quality gate to apply the same rules as draft reconstruction
**so that** a PASS means reconstruction will actually work.

### Acceptance Criteria
- [ ] Gate reuses `drafts.py` filters (reason codes, `new_block_type`, initiator, pay codes from `cfg.draft_reconstruction`), with no literals
- [ ] D7 premium rows deduplicated on (crew, pairing) before the join; rate is mathematically ≤ 1
- [ ] `d9_completeness` uses distinct station-days
- [ ] `VALID_BLOCK_TYPES` is derived from `BlockType`, or `OPEN` handling is made explicit, so rows are never silently dropped
- [ ] The three copies of the allowed-values check become one helper

### Verification
*   **Automated:** `pytest tests/data/test_quality_gates.py`
*   **Manual:** `crewsim data quality-report`
    *   **Expect:** every rate ≤ 100%, and the D6/D7 line names the codes it used
    *   **Fails if:** any rate exceeds 100%

---

## [TODO] IMP-505 — Draft "recall" is real recall (and precision)
**Size:** `M` | **Depends on:** — | **Source:** `data/drafts.py:81-119`, `data/corpus/_ground_truth.json`

**As a** validator **I want** the reconstruction scored by matching events, not by comparing counts
**so that** false positives can't inflate the score above the 80% gate.

### Acceptance Criteria
- [ ] If the ground truth has event ids, recall = matched ÷ true and precision = matched ÷ found are both reported, each with its own threshold
- [ ] If only counts exist, the metric is renamed `found_to_true_ratio`, capped interpretation documented, and the gate is marked ADVISORY
- [ ] `true_n == 0` gives INCONCLUSIVE, not PASS

### Verification
*   **Automated:** `pytest tests/data/test_draft_reconstruction.py -k precision`
*   **Manual:** `crewsim data draft-events`
    *   **Expect:** recall and precision on separate lines, each ≤ 100%
    *   **Fails if:** a single "recall" above 100% is possible

---

## [TODO] IMP-506 — The cascade target is uncensored, counted once and consistently filtered
**Size:** `M` | **Depends on:** — | **Source:** `data/cascades.py:46-55,86-120`

**As a** validator **I want** the historical cascade rate to be unbiased
**so that** V4 compares the simulation against the right number.

### Acceptance Criteria
- [ ] The follow-on scan sees D6 up to `window_end + cascade_window_days`. Drafts in the last 7 days are not censored.
- [ ] A follow-on event within the windows of two drafts is attributed to one draft (nearest preceding), not counted twice
- [ ] The denominator applies the same `new_block_type == "PAIRING"` filter as the numerator
- [ ] Before/after historical rate recorded. The stale V4 "permanently inconclusive" note in `cascade_analytics.py:24-27` is updated.

### Verification
*   **Automated:** `pytest tests/data/test_cascade_table.py -k "censor or double"`
*   **Manual:** `crewsim data cascade-target`
    *   **Expect:** the output states the scan horizon (window end + 7 d) and a single attribution rule
    *   **Fails if:** the scan stops at the window end

---

## [TODO] IMP-507 — Profile statistics are correct and survive empty windows
**Size:** `M` | **Depends on:** IMP-205 | **Source:** `data/profile.py:113,130,206-244,267-280,301,314-334`

**As a** data owner **I want** the profile to compute the right rates and not crash on sparse data
**so that** I can trust it when exploring a new season.

### Acceptance Criteria
- [ ] Sick calls per regime are averaged over **crew-base** station-days, not all 58 stations
- [ ] SEVERE runs require consecutive **calendar** days, so a missing day ends a run
- [ ] Empty windows, null durations, constant data (σ=0) and null `cancel_rate`/`delay_mean` render as "n/a", with no exception
- [ ] Zero-day durations are either excluded from `n` or included in the fit, consistently

### Verification
*   **Automated:** `pytest tests/data/test_profile_report.py -k "empty or severe_runs or per_base"`
*   **Manual:** `crewsim data profile --dataset d4_absences`
    *   **Expect:** sick-calls-per-day figures in the range of real base daily counts, not about 19× smaller
    *   **Fails if:** NORMAL-day sick calls per day are below 1 when the base averages several a day

---

## [TODO] IMP-508 — Profile narrative claims are computed, not hard-coded
**Size:** `S` | **Depends on:** IMP-507 | **Source:** `data/profile_html.py:42,67-69,145,163,232-234,263-264,365,387`

**As a** reader **I want** each sentence in the profile to be true for the data shown
**so that** the narrative never contradicts the chart beside it.

### Acceptance Criteria
- [ ] "Right-skewed", "all three streams rise" and "clustering holds" are emitted only when the computed condition is true. Otherwise a neutral or contrary sentence is emitted.
- [ ] Unknown outcome labels are shown as "other", not silently counted as 0%
- [ ] The unused `xaxis_title`/`yaxis_title` arguments are applied or removed. Duplicated orders and loops are factored out.

### Verification
*   **Automated:** `pytest tests/data/test_profile_report.py -k narrative`
*   **Manual:** n/a. Tests run the narrative against crafted data where each claim is false.

---

## [TODO] IMP-509 — The report and the API compute R* the same way
**Size:** `S` | **Depends on:** — | **Source:** `reporting/report.py:142,148,160,190-195,207,213-214,226,253-254`, `reporting/recommendation.py:17,54-57,63-76`

**As a** planner **I want** one R* recommendation everywhere
**so that** the HTML report and the web UI never disagree.

### Acceptance Criteria
- [ ] `report.py` calls `recommendation.compute_r_recommendation` (including the service-level exclusion). Its own λ curve is removed.
- [ ] The marked optimum on the trade-off chart is the λ-objective argmin, with the CVaR argmin labelled separately if still shown
- [ ] Guards:
  - empty policy list
  - empty `lambdas`
  - `cfg.sensitivity is None`
  - zero cheapest mean (spread shown as n/a)
  - non-`R<n>` names, parsed with the shared regex
  - duplicate R raising an error
- [ ] Config paths come from `cfg.config_path`/`cfg.costs_file`, and policy paths from the IMP-301 resolver

### Verification
*   **Automated:** `pytest tests/reporting/test_recommendation.py tests/reporting/test_html.py -k rstar`
*   **Manual:** run `crewsim report --policies R4 R6 R8 R10 R14 --scenarios 20`, and a batch with the same inputs in the UI
    *   **Expect:** the same R* for every λ in both
    *   **Fails if:** any λ differs

---

## [TODO] IMP-510 — The event tape shows each arrival once
**Size:** `S` | **Depends on:** — | **Source:** `reporting/tape.py:11-18,148,217-250`

**As a** planner **I want** one tape line per real event
**so that** I can read a scenario without mentally removing duplicates.

### Acceptance Criteria
- [ ] Zero-amount `OPEN_ITEM` marker rows and `DELAY_AMBIENT` rows are excluded from the event list (or `DELAY_AMBIENT` is shown as a daily summary line)
- [ ] The docstring correctly states that `root_event_uid` is the chain root. `_depth_of` is replaced by a parent pointer, or renamed to say it only distinguishes root from descendant.

### Verification
*   **Automated:** `pytest tests/reporting/test_tape.py -k no_duplicates`
*   **Manual:** open a scenario's tape in the UI
    *   **Expect:** each sick call appears exactly once
    *   **Fails if:** "open item — …" appears next to the same arrival

---

## [TODO] IMP-511 — Measurement window and documentation are consistent
**Size:** `S` | **Depends on:** IMP-210 | **Source:** `reporting/kpis.py:96-97,177,183-187`, `reporting/grid.py:62`, `reporting/drilldown.py:51-54`, `data/corpus/README.md:69-91`, `data/eligibility_target.py:80-106,124`

**As a** planner **I want** every displayed figure to state its window, and every doc number to match the data
**so that** side-by-side numbers are comparable.

### Acceptance Criteria
- [ ] Drill-down uncovered roots are restricted to the measurement window (same rule as ranking)
- [ ] If the full-horizon eligibility for V3 is kept, the UI labels it "full horizon"
- [ ] `cost_by_category` either excludes `DELAY_AMBIENT` and `OPEN_ITEM`, or shows a reconciliation line to `expected_cost`
- [ ] Welch diagnostic validates `warmup + measurement <= horizon_days`
- [ ] Eligibility fractions are per absence (duty periods inside the absence window and not finished at notification), returned as a list (JSON-safe)
- [ ] The corpus README figures are regenerated from `_ground_truth.json` by a script, not typed by hand. `_exmaple_data_schema` is renamed `_example_data_schema`.

### Verification
*   **Automated:** `pytest tests/reporting/test_kpis.py tests/reporting/test_drilldown.py -k window`
*   **Manual:** `crewsim run --policy R10 --scenarios 5 --kpis`
    *   **Expect:** category totals reconcile to E[C] (or a reconciliation line is shown)
    *   **Fails if:** they differ with no explanation

# IMP-E2 — Calibration & Statistical Validity

**11 stories** · **Low risk** (see [README](README.md)) · The must-fix IMP-201 is in
[../02_calibration_statistics.md](../02_calibration_statistics.md) · Gate: parameter store reproducible byte-for-byte, and a new
calibration fit-quality gate reporting on the holdout window.

Calibration feeds every scenario, so any bias here reaches every number in the report. The gates
are meant to catch that, but several of their confidence intervals are too narrow, which makes
their verdicts overconfident.

---

## [TODO] IMP-202 — Sick-call model includes an exposure offset
**Size:** `M` | **Depends on:** IMP-201 | **Source:** `calibration/nhpp.py:44-46,63,84`

**As a** modeller **I want** daily sick-call intensity to scale with headcount in each crew cell
**so that** a 112-pilot cell and a 19-pilot cell are not predicted alike.

### Acceptance Criteria
- [ ] The GLM uses `offset(log(headcount))`, with headcount per (base, fleet, position) **as of each date**, not today's ACTIVE flag
- [ ] `predict_intensity` multiplies by the scenario's headcount
- [ ] The store records which exposure definition was used
- [ ] Holdout comparison table, without vs with offset: predicted vs observed daily mean for the scoped cell

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k offset`
*   **Manual:** `crewsim calibrate sick-calls --show-coefficients`
    *   **Expect:** an `offset: log(headcount)` line, and predicted vs observed holdout mean within the stated tolerance
    *   **Fails if:** no offset is shown

---

## [TODO] IMP-203 — Decide and enforce the absence types in the sick-call model
**Size:** `S` | **Depends on:** SME decision | **Source:** `calibration/nhpp.py:66-70,118-123`, `data/profile.py:207`

**As a** planner **I want** the arrival model to cover exactly the absence types that reserves cover
**so that** "sick call" means one thing everywhere.

### Acceptance Criteria
- [ ] `calibration.absence_types` list in `base.yaml` (with `[CONFIRM]` until decided)
- [ ] Counts **and** the duration lognormal both use that filter
- [ ] UI and report labels use the configured name, not a hard-coded "sick call", if the scope is broader

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k absence_types`
*   **Manual:** `crewsim config show`
    *   **Expect:** absence types listed (or flagged `[CONFIRM]`)
    *   **Fails if:** absent

---

## [TODO] IMP-204 — Delay lengths use a distribution with positive support
**Size:** `M` | **Depends on:** — | **Source:** `calibration/delays.py:121-129,179`

**As a** modeller **I want** delay minutes drawn from a distribution that can't go negative
**so that** clipping does not create a fake spike at 1 minute and inflate the mean.

### Acceptance Criteria
- [ ] Replace the Gaussian mixture with a lognormal or gamma mixture (or a GMM on `log(minutes)`)
- [ ] `sample_delay_minutes` needs no `max(1.0, …)` clip, or the clip rate is < 0.1% and reported
- [ ] Fitted vs observed: mean, P50, P90 and P99 on the holdout window, within a stated tolerance
- [ ] The random seed comes from config, not the literal `42`

### Verification
*   **Automated:** `pytest tests/calibration/test_delay_mixture.py -k positive_support`
*   **Manual:** `crewsim calibrate --season winter_sun --emit`, then review the delay QQ summary it prints
    *   **Expect:** simulated P50/P90 within tolerance of observed
    *   **Fails if:** more than 0.1% of draws land at exactly 1.0 minute

---

## [TODO] IMP-205 — Cancelled flights are handled the same way everywhere
**Size:** `S` | **Depends on:** — | **Source:** `calibration/delays.py:67-73`, `calibration/regime.py:78`, `data/profile.py:288,298`

**As a** modeller **I want** one definition of how cancellations count
**so that** the delay probability, regime "chaos" and the profile agree.

### Acceptance Criteria
- [ ] Cancelled flights are excluded from both the numerator and the denominator of `delay_probability` and of the mean delay
- [ ] The cancellation rate is reported separately
- [ ] One shared helper defines "operated flight", used by `delays.py`, `regime.py` and `profile.py`

### Verification
*   **Automated:** `pytest tests/calibration/test_delay_mixture.py -k cancelled`
*   **Manual:** `crewsim data profile --dataset d8_flight_ops`
    *   **Expect:** the cancellation rate is shown separately, and the delay mean excludes cancelled flights
    *   **Fails if:** cancelled rows with non-zero delay feed the mean

---

## [TODO] IMP-206 — Regime model: a correct initial distribution, diagnostics that are kept, and accurate docs
**Size:** `S` | **Depends on:** IMP-201 | **Source:** `calibration/regime.py:97-99,107-129,166-167,185-276`, `calibration/pipeline.py:82-84,105-110`

**As a** modeller **I want** the regime store to say what it is
**so that** nobody reads a filtered marginal as a steady state.

### Acceptance Criteria
- [ ] `pi0` is either the full empirical marginal (all days) or the stationary distribution of `P`. The key name matches the choice.
- [ ] `transition_rows_backed_off` and `quantiles` are copied into the main store
- [ ] If NORMAL is missing or has a zero mean, fitting fails loudly instead of switching multipliers to absolute units
- [ ] The `label_agreement` docstring and the pipeline comment describe the D9-label fit, and the diagnostic uses the same base filter as the fit

### Verification
*   **Automated:** `pytest tests/calibration/test_regime.py`
*   **Manual:** `crewsim calibrate regime --season winter_sun --show-matrix`
    *   **Expect:** `pi0` sums to 1, and backed-off rows are listed
    *   **Fails if:** backed-off rows exist but aren't shown

---

## [TODO] IMP-207 — Calibration fails clearly on empty or degenerate data
**Size:** `M` | **Depends on:** — | **Source:** `calibration/nhpp.py:77,80-88,121-123,193-200`, `calibration/regime.py:61-65,121,127-129`, `calibration/delays.py:86`, `scenarios/generator.py:162,190`

**As a** data owner **I want** a clear error naming the empty or invalid input
**so that** I fix the data rather than debug a statsmodels or numpy stack trace.

### Acceptance Criteria
- [ ] Guard with a clear `CalibrationError`, naming the dataset and window, for each of:
  - empty D4 or exposure grid
  - empty durations
  - D9 with fewer than 2 consecutive days
  - an unknown `disruption_class`
  - a null `disruption_class`
- [ ] `fill_null(0)` is applied only to numeric count columns
- [ ] `sample_count` and `predict_intensity` reject NaN or inf means
- [ ] `json.dump(..., allow_nan=False)` for every store write
- [ ] Parametrised tests, one per guard

### Verification
*   **Automated:** `pytest tests/calibration -k degenerate`
*   **Manual:** n/a. Covered by tests.

---

## [TODO] IMP-208 — Scenario generation refuses an unconverged or holdout-leaking store
**Size:** `S` | **Depends on:** IMP-201 | **Source:** `scenarios/generator.py`, `calibration/pipeline.py:52-54,114-116`

**As a** planner **I want** generation to stop if the parameters are provisional
**so that** an unconverged fit or a fit that saw the holdout cannot feed a recommendation silently.

### Acceptance Criteria
- [ ] `generate_scenarios` raises if `sick_call_nhpp.converged` is false, unless an explicit `--allow-unconverged` flag is passed
- [ ] `run_pipeline` raises if `cfg.windows` is missing, unless `--full-corpus` is passed and recorded in the store
- [ ] The convergence warning uses `logging`/`warnings`, not `print`

### Verification
*   **Automated:** `pytest tests/engine/test_scenario_gen.py -k unconverged`
*   **Manual:** `crewsim scenarios generate --master-seed master --scenarios 5` against a store with `converged: false`
    *   **Expect:** a refusal naming the flag
    *   **Fails if:** a parquet is written

---

## [TODO] IMP-209 — Confidence intervals account for correlation within scenarios
**Size:** `M` | **Depends on:** — | **Source:** `gates/v2_erlang.py:152`, `data/eligibility_target.py:116-118`, `data/cascades.py:72`

**As a** validator **I want** gate intervals that reflect the real sampling unit
**so that** PASS/FAIL verdicts are not overconfident.

### Acceptance Criteria
- [ ] V2: blocking-probability CI from a scenario-level bootstrap (or a cluster-robust interval)
- [ ] V3 historical target: CI clustered by absence (or day)
- [ ] V4 historical target: CI clustered by crew or draft day
- [ ] Number of bootstrap draws and the seed come from config
- [ ] The report states the clustering unit next to each CI

### Verification
*   **Automated:** `pytest tests/gates -k clustered_ci`
*   **Manual:** `crewsim gate v2 --show-comparison`
    *   **Expect:** CI labelled "scenario bootstrap" and wider than the previous Wilson CI
    *   **Fails if:** labelled Wilson/iid

---

## [TODO] IMP-210 — V3 and V4 compare like with like
**Size:** `M` | **Depends on:** IMP-209 | **Source:** `gates/v3_eligibility.py:16-19`, `gates/v4_cascade.py:77,98`, `cli.py:1076,1104`, `data/cascades.py:110`

**As a** validator **I want** each gate to compare equivalent statistics
**so that** a FAIL means the simulation is wrong, not the comparison.

### Acceptance Criteria
- [ ] V3 is a two-sample (or equivalence/TOST) comparison that includes the simulated mean's own uncertainty, with the margin from config
- [ ] V3 with empty or NaN simulated input returns INCONCLUSIVE, not FAIL
- [ ] V3 uses the measurement window on both sides (aligned with `kpis.py:177`)
- [ ] V4 compares a pooled ratio to a pooled ratio (sum of cascading drafts ÷ sum of drafts)
- [ ] V4's recall threshold has its own config key, separate from `d4_link_marginal`
- [ ] `v4_cascade.py:98` uses `len()`

### Verification
*   **Automated:** `pytest tests/gates/test_v3_eligibility.py tests/gates/test_v4_cascade.py`
*   **Manual:** `crewsim gate v3` and `crewsim gate v4`
    *   **Expect:** each prints the test used, both estimates with CIs, and the margin
    *   **Fails if:** V3 shows a point compared against an interval

---

## [TODO] IMP-211 — Calibration fit-quality gate (new)
**Size:** `L` | **Depends on:** IMP-202, IMP-204, IMP-206 | **Source:** no gate validates the calibrated distributions

**As a** validator **I want** a gate that checks the fitted models against the holdout window
**so that** a badly fitted input is caught before it feeds every policy.

### Acceptance Criteria
- [ ] New gate `vcal` (the name must not collide with V8). On holdout it compares:
  - **daily sick-call counts:** predictive coverage of the observed counts (e.g. share of days inside the 90% predictive interval), and NB vs Poisson dispersion
  - **regime chain:** simulated vs observed run-length distribution of SEVERE spells
  - **delays:** a KS or quantile comparison of minutes per regime
- [ ] Thresholds in `configs/base.yaml` under `gates.calibration`
- [ ] Reported in `crewsim report` and the API gate status alongside V1–V9
- [ ] The `report.py` V8 row and the `v2_erlang.py:25` reference are corrected to point to real evidence

### Verification
*   **Automated:** `pytest tests/gates/test_vcal.py`
*   **Manual:** `crewsim gate vcal`
    *   **Expect:** three sections, each with PASS/FAIL and the statistic vs threshold
    *   **Fails if:** any section prints no threshold

---

## [TODO] IMP-212 — V9 sensitivity is stable, reproducible and guarded
**Size:** `S` | **Depends on:** — | **Source:** `gates/v9_sensitivity.py:9,34,36,44,78,131,139,144,172`, `cli.py:1148`

**As a** planner **I want** "unstable recommendation" to mean the same thing on every run
**so that** I can trust the V9 verdict.

### Acceptance Criteria
- [ ] Instability is measured in **grid steps** (index distance), not R units
- [ ] Findings are sorted deterministically (no `list(set(...))`)
- [ ] R is read from the policy's contents, not its file name
- [ ] Ties are broken by lowest R (documented)
- [ ] A minimum scenario count for CVaR95 comes from config; below it the result is INCONCLUSIVE
- [ ] An empty lookup or surface gives a clear error. A missing `cfg.sensitivity` gives a CLI message, not an AttributeError.
- [ ] The result dict includes a `pass` key

### Verification
*   **Automated:** `pytest tests/gates/test_v9_sensitivity.py`
*   **Manual:** run `crewsim gate v9` twice
    *   **Expect:** identical output, including the order of findings
    *   **Fails if:** the findings order differs between runs

# Findings 2 — Model Definition

**3 stories** · Source: calibration-layer analysis (October 2026) · See the [README](README.md) for the evidence table.

These three stories are about what the calibrated model is a model **of**: which absences, which
population, which flights. None of them is a bug in the usual sense. The code does what it says. The
trouble is that the thing it says is undecided or inconsistent, and the answer moves the numbers a
planner reads.

---

<a id="imp-203"></a>
## [TODO] IMP-203 — What counts as a "sick call"
**Size:** `S` | **Category:** Decision needed | **Existing story:** IMP-203 (this adds evidence and options) | **Depends on:** Crew Planning answer
**Source:** `calibration/nhpp.py:51-54,82-87,145-148`, `calibration/regime.py:79-84`, `data/corpus/d4_absences.csv` (`absence_type`)

### Details
D4 carries an `absence_type` column. In the corpus it holds three values, and no fitter looks at it.

| Type | Whole corpus | Fitting window | At YUL (fitting) | Mean duration |
|---|---|---|---|---|
| SICK | 4,712 | 3,047 | 2,206 (59%) | 2.03 d |
| FAMILY | 1,621 | 1,064 | 772 (21%) | 1.97 d |
| INJURY | 1,570 | 1,024 | 748 (20%) | 2.04 d |

All three go into **three places**: the HMM's daily sick-call stream (`regime.py:79-84`), the
negative binomial counts (`nhpp.py:82-87`) and the duration lognormal (`nhpp.py:145-148`). The model,
the API (`goodness_of_fit_note`), the UI and the spec all call them "sick calls".

**Impact.**
- If only SICK needs reserve cover, today's arrival rate is **about 1.7 times too high** (3,047 of
  5,135 in the fitting window is 59%), and reserves look more valuable than they are. R* shifts upward.
- If FAMILY and INJURY *also* need cover, the model is right and only the name is wrong.
- Durations are almost identical across types on the mock, so the duration fit is not sensitive to the
  choice. The effect is a pure change of **rate scale**. On real data, durations may differ (an injury is
  plausibly longer than a family day), so do not assume this carries over.
- The HMM counts the same absences, so the *regime labels* also depend on the choice, not just the
  GLM.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **SICK only** | Filter D4 to `absence_type == "SICK"` in all three places | S | Matches the name; smallest defensible definition | Understates demand if family/injury absences also leave a duty uncovered |
| B | **Configured allow-list** `calibration.absence_types` | One helper applies the list everywhere. Default = all three, marked `[CONFIRM: Crew Planning]`. Store records the list. UI/report label uses the configured name | S | No number changes today; makes the choice visible and reversible; works for real data with other type names | Does not by itself answer the question |
| C | **Model each type separately** | `absence_type` becomes a GLM covariate (or three streams), per-type durations | L | Right if types differ in regime sensitivity or duration (injury is unlikely to rise on a SEVERE weather day) | More parameters to fit and validate; mock shows no difference to justify it yet |
| D | **Status quo, document only** | Rename "sick call" to "unplanned absence" in labels | XS | Zero risk | Leaves the wrong scale in place if A is the truth |

### Recommendation
**B now**, then A, B-as-is or C once Crew Planning answers. B changes no number, and it removes the
hard-coded assumption that three different things are one. Add a sensitivity run of A vs current to
show how far R* moves, so the planner sees the stake when answering.

### Decision needed
Crew Planning: *"Which absence types create a duty that a reserve has to cover?"* Ask also whether
a type should be excluded from the **duration** distribution even if it is counted as an arrival.

### Acceptance criteria (for B)
- [ ] `calibration.absence_types: [SICK, FAMILY, INJURY]  # [CONFIRM: Crew Planning]` in `configs/base.yaml`, validated against the values in D4 (an unknown type raises).
- [ ] One helper, e.g. `data.loaders.counted_absences(cfg, d4)`, used by `regime.load_inputs`, `nhpp.fit_sick_calls` (counts **and** durations). No fitter filters on its own.
- [ ] The store records `absence_types` and `content_hash` changes when the list changes (so the scenario cache rebuilds).
- [ ] UI and report labels read the configured name, not the literal "sick call", when the list is broader than SICK.
- [ ] Sensitivity table in the sign-off: E[C], CVaR95 and R* with `[SICK]` against the full list.

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k absence_types` and `tests/calibration/test_regime.py -k absence_types`
*   **Manual:** `crewsim config show`
    *   **Expect:** `absence_types` listed with its `[CONFIRM]` flag
    *   **Fails if:** a type appears in D4 and not in the list, with no error

---

<a id="imp-202"></a>
## [TODO] IMP-202 — Sick-call model exposure (headcount)
**Size:** `M` | **Category:** Should | **Existing story:** IMP-202 (this adds options) | **Depends on:** IMP-203, Data owner answer
**Source:** `calibration/nhpp.py:57-60,107`, `calibration/hmm.py:229` (the HMM *does* use an exposure), `data/corpus/d1_crew_master.csv` (`hire_date`, `termination_date`)

### Details
The HMM models sick calls as Poisson(`exposure × λ_k`), with exposure = crew on duty that day
(`regime.py:86-106`). The GLM has **no exposure term** (`nhpp.py:107`). It predicts a count per
(base, fleet, position) cell per day from categorical effects alone. The two halves of the same store
therefore disagree about what is being modelled: a *rate per person* in one, a *count per cell* in the other.

What this costs:
- A cell with 112 pilots and a cell with 19 get different intercepts only because the `C(base)`,
  `C(fleet)` and `C(position)` dummies happen to absorb it. The model cannot extrapolate to a new scope.
- Headcount varies in time (hires, terminations; D1 has the dates), but the GLM cell effect is a single
  average. D1 is read only to list which (base, fleet, position) cells exist, filtered on **today's**
  `employment_status == "ACTIVE"` (`nhpp.py:58-60`). Headcount never enters the model. A cell whose
  pilots have all since left disappears from the exposure grid, and its past absences are silently
  dropped by the left join (`nhpp.py:90-94`).
- Anyone who changes `scope` in `base.yaml` gets coefficients that were fitted for a different
  population mix.

### Options

| | Option | Exposure definition | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Headcount offset, as of each date** | `offset(log(headcount[cell, date]))` from D1 hire and termination dates; `predict_intensity` multiplies by the scenario's headcount from the loaded roster | M | A true "at risk" population; works for any scope; matches IMP-202 as written | Needs a point-in-time headcount table; assumes absences hit people not on duty too |
| B | **Crew on duty (D2) as exposure** | Same exposure the HMM already uses, at cell level | M | One definition across the HMM and the GLM; no new data | On-duty counts depend on how the roster was built, and are zero on days off. If an absence is recorded even when the person was not rostered, sick calls land on zero exposure |
| C | **Keep as is and document** | None | XS | No change in any number | A single-cell scope is fine, any other scope is wrong silently |
| D | **Fix exposure at fit time only**, drop D1 point-in-time and use *current* ACTIVE counts | Cell headcount constant | S | Cheapest way to get the offset into the model | Still wrong for turnover; only half an answer |

### Recommendation
**A**, with **B** as the alternative if the data owner says D4 only records absences that hit a
rostered duty. Either way the store must record `exposure_definition`, and the HMM and the GLM should
end up with the same definition (switch the HMM to headcount for A, or keep both on-duty for B).

### Decision needed
Data owner: *"Does D4 contain every absence, or only ones against a duty? Is a pilot on a rest day at
risk of a sick call that the system records?"*

### Acceptance criteria (for A)
- [ ] A function returns headcount per (base, fleet, position, date) from D1, respecting `hire_date` and `termination_date`.
- [ ] The GLM formula has `offset=np.log(headcount)`; rows with zero headcount are dropped or raise.
- [ ] `predict_intensity` takes the scenario's headcount and multiplies; the cell's roster size is what `generator.py` passes.
- [ ] The store records `exposure_definition` (and `content_hash` changes with it).
- [ ] Holdout table: predicted vs observed daily mean for the scoped cell, without and with the offset.
- [ ] Test: doubling the headcount doubles the expected count, all else equal.

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k offset`
*   **Manual:** `crewsim calibrate sick-calls --show-coefficients`
    *   **Expect:** an `offset: log(headcount)` line
    *   **Fails if:** no offset is shown, or `exposure_definition` is missing from the store

---

<a id="imp-205"></a>
## [TODO] IMP-205 — One definition of a delayed / operated flight
**Size:** `S` | **Category:** Optional (**downgraded from Should**) | **Existing story:** IMP-205 | **Depends on:** —
**Source:** `calibration/regime.py:66-77`, `calibration/delays.py:83-88,118`, `data/profile.py`

### Details
Two modules define "a delayed flight" differently:

| | HMM (`regime.py:69-77`) | Delay fit (`delays.py:83-88,118`) |
|---|---|---|
| Delay threshold | `delay_minutes >= 15` (`delay_threshold_minutes`) | `delay_minutes > 0` |
| Cancelled flights | Own category; excluded from "delayed" | Counted in the denominator; 230 cancelled rows carry a delay > 0 |
| Population | All fleets at the base | Scope fleet only |

Measured at YUL / A321neoLR (fitting window): `P(delay > 0)` = 0.1747 against `P(≥ 15 min, not cancelled)`
= 0.1492, a 17% relative gap. 151 of 14,643 flights are cancelled (1.0%).

**Why this is downgraded.** The first analysis called it a medium inconsistency. Tracing the consumers
shows the two numbers **never meet**. The generator reads only `delay_by_regime` and the mixture
(`generator.py:208-217`); the HMM's `delay_probability` is store metadata. `delays.py` is internally
consistent: its probability and its duration mixture are both on delays `> 0`. And the cost it feeds,
`DELAY_AMBIENT`, is excluded from the optimised E[C]/CVaR95 (`engine/des.py:1191`), so R* does not read it.
What remains is **display confusion**: the calibration UI can show SEVERE delay probability as 0.399 (HMM)
and 0.440 (`delay_by_regime`) side by side with no explanation.

### Options

| | Option | Effort | Pros | Cons |
|---|---|---|---|---|
| A | **Shared "operated flight" helper, one threshold** used by `regime.py`, `delays.py`, `profile.py`; delay probability on operated flights only; duration mixture fitted on minutes above the threshold | M | Single meaning everywhere; the IMP-205 text | The mixture then fits a left-truncated distribution (minutes ≥ 15), so IMP-204's choice of family matters and the two should be done together |
| B | **Shared helper for cancelled flights only**; keep two thresholds deliberately, named `otp_delayed` (≥ 15) and `any_delay` (> 0) | S | Fixes the cancelled-in-denominator inconsistency (about 1% of flights); no re-fit of the mixture | Two numbers still exist; needs clear labels in the UI |
| C | **Rename and document only** | XS | No change in any number | Cancelled flights stay in the denominator |
| D | Move the HMM to `> 0` | S | One threshold | Loses the industry 15-minute on-time standard; counts routine 1–14 minute slips (13% of delayed rows) as disruption, which blurs the regimes |

### Recommendation
**B now.** It is the real inconsistency (cancelled flights counted as operated) and costs half a day.
Move to **A** only together with IMP-204, because the threshold and the shape of the mixture are one
modelling decision.

### Decision needed
Data Science: *"Does the ambient delay cost count every minute of lateness, or only delays at or above
the on-time threshold?"* This sets whether `delay_minutes` below 15 are in the model at all.

### Acceptance criteria (for B)
- [ ] One helper (e.g. `data.loaders.operated_flights(d8)`) defines "operated" (not cancelled). Used by `regime.py`, `delays.py` and `profile.py`.
- [ ] `delay_probability` and `mean_flights_per_day` in `delays.py` use operated flights only; the cancellation rate is reported separately in the store.
- [ ] The UI shows the two delay probabilities under two distinct names.
- [ ] Test: a cancelled row with a non-zero delay changes neither the numerator nor the denominator.

### Verification
*   **Automated:** `pytest tests/calibration/test_delay_mixture.py -k cancelled`
*   **Manual:** `crewsim data profile --dataset d8_flight_movements`
    *   **Expect:** cancellation rate shown on its own line; delay mean excludes cancelled flights
    *   **Fails if:** cancelled rows with a non-zero delay feed the mean

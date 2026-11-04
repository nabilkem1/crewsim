# Findings 2 — Statistical Validity

**5 stories** · Source: calibration-layer analysis (October 2026) · See the [README](README.md) for the evidence table.

These stories are about whether the fitted numbers deserve the trust the rest of the pipeline gives
them. Most have a **cheap first step that changes no result** (a diagnostic or a stored number) and
a heavier correction that should be chosen only if the diagnostic shows a gap.

---

<a id="imp-214"></a>
## [TODO] IMP-214 — Parameter uncertainty reaches the results
**Size:** `M` (report only) to `L` (propagated) | **Category:** Should | **Depends on:** IMP-211 (stored diagnostics) | **Source:** `calibration/pipeline.py:114-161`, `scenarios/generator.py:115-148`

### Details
The store holds **point estimates**. Every scenario in every run is drawn from the same transition matrix,
the same GLM coefficients and the same delay mixture. The 95% intervals the reports print for E[C] and
CVaR95 therefore reflect **Monte Carlo noise only**, not the uncertainty in the parameters.

How much data stands behind them (YUL `winter_sun`):
- 303 in-season days in 2 winter sequences.
- 27 free HMM parameters: 12 transition, 3 start, 8 flight-outcome, 4 sick-rate (`hmm.py:102`).
- Individual cells are barely identified. `SEVERE -> CALM` is fitted at 0.009; a handful of
  transitions decide it. These tail transitions are exactly what drives CVaR95.
- The start distribution comes from only 2 sequences. It is stored but never read (the generator
  uses the stationary distribution), which is the right call.

More scenarios will not close this gap. Doubling the scenario count tightens the Monte Carlo interval
and leaves the parameter error untouched. The report can then call a recommendation "stable" when it is
only stable *given these 303 days*.

### Options

| | Option | What is built | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Parametric bootstrap, propagated** | Simulate B datasets from the fitted HMM, refit everything, store the B parameter sets. Scenario *s* uses set `s mod B` | L | End to end: reaches E[C], CVaR95 and R*; the honest interval | The store grows B-fold; assumes the model form is right; B refits of HMM + GLM + delays (one HMM fit is 0.8 s; GLM and delays not measured) |
| B | **Asymptotic draws** | GLM: draw from `N(beta, cov_params())` (statsmodels has it). Transition rows: Dirichlet from expected transition counts. Emissions: from the HMM's information matrix or a short bootstrap | M | Cheap and fast; small store | Approximate; the HMM emission covariance is not available from hmmlearn out of the box |
| C | **Block bootstrap of the data** | Resample whole seasons or weeks, refit | L | Data-driven; makes no model-form assumption | **Only 2 winter sequences**: too few blocks to resample at season level; week blocks break the chain's persistence |
| D | **Report only, not propagated** | Bootstrap (A or C) run once at calibration, stored as `parameter_intervals`, shown in the calibration UI and report. A V9-style sensitivity run recomputes R* at the interval ends | M | No change to scenarios, caches or CRN; shows how much it matters | Does not widen the headline CIs |
| E | **Do nothing, state the limitation** | A sentence in the report | XS | Free | Leaves the overconfident intervals |

### Recommendation
**D first, A later.** D answers the only question that matters before building the rest: *does R*
change inside the parameter interval?* If it does not, A is not needed. If it does, A is justified and
the work is already half done. Prefer a parametric bootstrap over C because of the 2-sequence problem.

**CRN requirement for A.** The parameter-set index must be a deterministic function of the scenario id
and the master seed, **not** of the policy. Every policy then sees the same (scenario, parameters)
pair, so paired comparisons (and gate V7's hash check) stay valid. The store hash covers the whole
ensemble, so the scenario cache rebuilds when it changes. `GENERATOR_EPOCH` should be bumped.

### Decision needed
Product owner: *"Is parameter uncertainty part of the first Air Transat run, or only reported?"*

### Acceptance criteria (for D)
- [ ] Store key `parameter_intervals`: 90% intervals for each P cell, each regime coefficient and the multipliers, with the method and B recorded. In `diagnostics`, so it is out of the hash.
- [ ] The calibration UI and report show the intervals next to the point estimates.
- [ ] `crewsim gate v9` (or a new sensitivity command) recomputes R* at the lower and upper interval ends of the SEVERE row of P, and says whether the recommendation changed.
- [ ] B and the bootstrap seed are in `configs/base.yaml`, the seed derived through `crn.stable_seed`.

### Verification
*   **Automated:** `pytest tests/calibration -k parameter_intervals` (intervals contain the point estimate; same seed gives the same intervals)
*   **Manual:** `crewsim calibrate --season winter_sun --emit`
    *   **Expect:** an interval printed for `SEVERE -> SEVERE`, and a line saying whether R* moves across it
    *   **Fails if:** an interval is missing or has zero width

---

<a id="imp-216"></a>
## [TODO] IMP-216 — Regime labels are not a hard covariate
**Size:** `M` | **Category:** Should | **Depends on:** IMP-211 | **Source:** `calibration/regime.py:234-245`, `calibration/nhpp.py:62-69,107`

### Details
The HMM labels each day with its most likely state (Viterbi). That label is then used as the
categorical covariate `C(regime)` in the sick-call GLM. Two problems follow:

1. **The covariate is built from the response.** The HMM's label for a day is partly *determined by* that
   day's sick calls. Regressing sick calls on a label that was chosen using sick calls is circular, and it
   tends to overstate the regime effect.
2. **The label is treated as known.** `_decode` computes the posterior `p_<STATE>` for every day, then
   `labels_frame` carries it, and the GLM throws it away (`nhpp.py:64-69` selects only `disruption_class`).
   Measured on YUL `winter_sun`: mean max-posterior is 0.875, **25.4% of days are below 0.8 and 6.6% are
   below 0.6**. A quarter of the days are labelled with real doubt.

The effect today is small. The GLM's regime ratios against NORMAL agree with the HMM's own sick-rate
ratios to within 2–10%:

| State | GLM `exp(beta)` vs NORMAL | HMM `lambda_k / lambda_NORMAL` |
|---|---|---|
| CALM | 0.47 | 0.43 |
| DISRUPTED | 1.69 | 1.73 |
| SEVERE | 2.97 | 2.80 |

This is on a mock corpus whose generator is Poisson with four clean states. On real, noisier
data the two estimates can drift apart. They are two estimators of one quantity, and nothing watches
the gap.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Consistency diagnostic only** | Store `regime_effect_consistency`: GLM ratios vs HMM ratios per state, with a warning above a configured tolerance (e.g. 15%) | S | Makes the risk visible; no result changes | Detects the problem; does not fix it |
| B | **Soft labels** | Expand each exposure row to K rows weighted by `p_k` and fit the GLM with those weights | M | Uses the uncertainty that is already computed; removes the "known label" assumption | `smf.negativebinomial` takes no weights argument (check against the installed statsmodels); needs `GLM(family=NegativeBinomial(alpha=...), freq_weights=...)` with alpha fixed or profiled. Still circular, only less so |
| C | **HMM rate as an offset** | Fit the GLM *without* `C(regime)` but with `offset=log(E[m_d])` where `E[m_d] = sum_k p_dk * m_k` from the HMM. The generator multiplies by the sampled state's `m_k`, **using the same HMM multiplier** | M | One source for the regime effect (the HMM); no circular covariate; baseline coefficients are conditional on it | Reverses the deliberate choice at `generator.py:181-188` not to apply a multiplier. It is safe only because the GLM was fitted with that exact offset, so nothing is counted twice. Needs a clear comment and a regression test |
| D | **Regression HMM** | Let the HMM's sick-call emission carry day-of-week, season, base, fleet, position effects, one joint likelihood | XL | The principled answer: regime and covariates estimated together | Loses the closed-form M-step (`hmm.py:162-174`); needs IRLS per EM step; big test surface |
| E | **Two-pass refit** | Refit the HMM on the sick-call residuals after removing the GLM's covariate effects, iterate | L | Partly removes the circularity | Ad hoc; convergence unproven |

### Recommendation
**A now, B if the diagnostic shows a gap above tolerance on real data, C as the long-term shape.** D is
the right model but not worth the cost for a fixed 4-state design. A is half a day and turns an
unmonitored assumption into a number on the calibration page.

### Decision needed
Data Science: the tolerance for "the two estimators agree", and whether the HMM or the GLM is the
source of truth for the regime effect when they do not.

### Acceptance criteria (for A)
- [ ] Store `diagnostics.regime_effect_consistency` with the per-state ratio from each estimator and the relative difference. Excluded from the hash.
- [ ] A warning, through `logging`, above `calibration.regime_effect_tolerance` (a new config key; mark `[CONFIRM: Data Science]`).
- [ ] The UI shows both ratios side by side.
- [ ] Test: a synthetic corpus where the hard-label bias is built in (low-certainty labels) trips the warning.

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k regime_effect_consistency`
*   **Manual:** `crewsim calibrate --season winter_sun --emit`
    *   **Expect:** a consistency line per state with both ratios
    *   **Fails if:** the GLM and HMM ratios differ by more than the tolerance with no warning

---

<a id="imp-217"></a>
## [TODO] IMP-217 — Overdispersion handled consistently
**Size:** `S` (diagnostic) to `M` (negative-binomial emission) | **Category:** Conditional (trigger: real-data var/mean above 1.5) | **Depends on:** — | **Source:** `calibration/hmm.py:228-229`, `calibration/nhpp.py:107-124`, `configs/base.yaml:170`

### Details
The two places that model sick-call counts disagree on the distribution:

- **HMM emission:** Poisson (`hmm.py:229`). Variance equals the mean within a state.
- **GLM:** negative binomial, which allows extra variance (`nhpp.py:107`).

On the mock they agree, because the mock is Poisson. Measured daily var/mean by fitted regime at YUL:
CALM 1.07, NORMAL 0.86, DISRUPTED 1.09, SEVERE 1.21. The GLM's alpha is 1.5e-5, which is Poisson to
five decimal places (the `sample_count` negative-binomial branch still runs, with n = 1/alpha, about
67,000, which is numerically Poisson).

**The risk is on real data.** Real absence counts are almost always overdispersed. A Poisson-emission HMM
reads *extra-Poisson noise as evidence of another state*. Two things go wrong:
1. The HMM invents or sharpens regimes to explain noise, so P and the labels are overfitted.
2. The GLM then sees labels that already absorbed the overdispersion, reports a small alpha, and the
   generator draws counts with too little spread inside each regime. The tail of daily demand, which is
   what CVaR95 reads, is understated.

`calibration.overdispersion_threshold: 1.5` already exists in config but is used by the data profile
(`data/profile.py`), not by the calibration.

### Options

| | Option | Effort | Pros | Cons |
|---|---|---|---|---|
| A | **Diagnostic**: per-regime var/mean stored with the fit; warning above `overdispersion_threshold` | S | Cheap; reuses an existing config key; arms the trigger for B | Detects, does not fix |
| B | **Negative-binomial emission in the HMM** | M | Consistent family in the HMM and the GLM; robust to overdispersion | The dispersion has no closed-form M-step (use a moment estimate or 1-D Newton); more parameters per state (+4); BIC changes meaning |
| C | **Tempered Poisson**: divide the sick log-likelihood by an estimated dispersion factor phi | S | Quick; down-weights the sick stream when it is noisy | A quasi-likelihood, not a likelihood: BIC and the holdout log-likelihood stop being interpretable |
| D | **Drop the sick stream from the HMM**, label regimes from flights only | S | Removes the problem and the circularity of IMP-216 | Loses a signal (sick calls are one of the regime's three symptoms); the spec's design correlates sick calls with the regime *through the data*. Changes the model's meaning |
| E | **Do nothing** | XS | Free | Silent failure on real data |

### Recommendation
**A now**, with **B queued as the planned correction**. Set the trigger explicitly: if any regime's
var/mean on the real fitting window exceeds `overdispersion_threshold`, schedule B before the store is
used for a recommendation.

### Decision needed
Data Science: confirm 1.5 is the right bar for the calibration (it was chosen for the profile).

### Acceptance criteria (for A)
- [ ] Store `diagnostics.sick_call_dispersion_by_regime`: mean, variance and var/mean per regime.
- [ ] A warning, via `logging`, for any regime above `calibration.overdispersion_threshold`.
- [ ] The comment at `hmm.py:229` names the Poisson assumption and points at this story.
- [ ] Test: a synthetic corpus with negative-binomial counts trips the warning.

### Verification
*   **Automated:** `pytest tests/calibration/test_regime.py -k dispersion`
*   **Manual:** `crewsim calibrate regime --season winter_sun`
    *   **Expect:** a var/mean per regime
    *   **Fails if:** a regime above 1.5 produces no warning

---

<a id="imp-204"></a>
## [TODO] IMP-204 — Delay minutes use a positive-support distribution
**Size:** `M` | **Category:** Should | **Existing story:** IMP-204 (this adds measurements and options) | **Depends on:** decide together with IMP-205 | **Source:** `calibration/delays.py:140-160,187-201`

### Details
Delay durations are fitted with a 2-component Gaussian mixture on raw minutes (`delays.py:140-144`).
A Gaussian puts mass below zero, and `sample_delay_minutes` clips those draws to 1.0 minute
(`delays.py:201`).

Measured at YUL / A321neoLR, fitting window, 2,558 delayed flights:

| Model | P50 | P90 | P99 | Share of draws at exactly 1.0 min |
|---|---|---|---|---|
| **Observed** | 49 | 158 | 333 | n/a |
| Gaussian mixture, raw minutes (**current**) | 48.7 | 177.1 | 278.2 | **5.3%** |
| Gaussian mixture, log-minutes (lognormal mixture) | 50.8 | 156.9 | 340.3 | 0.01% |
| Single gamma | 53.6 | 153.4 | 287.4 | 0 |

Two defects, both visible: a **spike at 1 minute** (5%, far above the 0.1% target in the story), and a
**thin right tail** (P99 of 278 against 333 observed, 16% low) with a fat shoulder (P90 177 against
158). BIC also prefers 3 raw components over 2 by 299 points, a sign the raw Gaussians are a poor family
(log-minutes: 21 points).

Priority note: `DELAY_AMBIENT` is priced per minute and excluded from the optimised cost
(`engine/des.py:1191`), so this does not move R*. It does move reported delay cost, and the tail.

The story's "seed is a literal 42" criterion is **already satisfied**: the seed is read from
`calibration.delay_gmm_random_state` (`delays.py:142`).

### Options

| | Option | Effort | Pros | Cons |
|---|---|---|---|---|
| A | **Gaussian mixture on log-minutes** (lognormal mixture), k from config | M | Positive support by construction; no clip; reproduces P50/P90/P99 within about 4% on the mock (3.7%, 0.7%, 2.2%); same sklearn code path | Store schema changes (`family`, `log_mean`, `log_sd`); sampler dispatches on `family`; `GENERATOR_EPOCH` bump; old stores must raise a clear error |
| B | **Gamma (single or mixture)** | M | Positive, smooth | Single gamma under-covers the tail (P99 287); a mixture needs custom EM (sklearn has none) |
| C | **Keep Gaussian, sample truncated** (reject draws below 1) | S | Removes the spike | Biases the mean upward and leaves the tail thin |
| D | **Empirical resampling** by regime | M | No family assumption; exact tail | The store stops being a small set of parameters; cannot extrapolate beyond the observed maximum; k data points per regime |
| E | **Raise k to 3 raw Gaussians** | S | BIC improves by 299 | Still allows negative draws; more parameters; does not fix the cause |

### Recommendation
**A**, choosing k (2 or 3) from BIC on the real data. Decide together with IMP-205: if the delay stream
moves to a threshold of 15 minutes, fit the lognormal mixture to `minutes - 15 + 1` or sample a left-truncated
one. Do it in the same change as any other store-schema change, because it rebuilds every scenario
cache once.

### Decision needed
Data Science: the tail tolerance (P90/P99 within what percentage?), and whether the delay stream
includes lateness below 15 minutes (IMP-205).

### Acceptance criteria (for A)
- [ ] Mixture fitted on `log(minutes)`; store records `family: "lognormal_mixture"`, the components, and the fitting n.
- [ ] `sample_delay_minutes` has no `max(1.0, ...)`; a test asserts no draw is below 1 minute without a clip.
- [ ] On the fitting data and on holdout: P50, P90, P99 and the mean within the configured tolerance; both reported.
- [ ] A store without `family` raises a clear "recalibrate" error, as `generator.py:123-138` does today for older stores.
- [ ] `GENERATOR_EPOCH` bumped; the first run after the change rebuilds caches (note in the sign-off).
- [ ] k chosen by BIC over `calibration.delay_gmm_candidates` (new, default [2, 3]), reported in the store.

### Verification
*   **Automated:** `pytest tests/calibration/test_delay_mixture.py -k positive_support`
*   **Manual:** `crewsim fit-delays --season winter_sun`
    *   **Expect:** simulated P50/P90/P99 next to observed, all within the tolerance
    *   **Fails if:** more than 0.1% of draws sit at one value

---

<a id="imp-218"></a>
## [TODO] IMP-218 — A regime state means the same thing in every fit
**Size:** `M` (diagnostic and scope) to `L` (tied emissions) | **Category:** Verify first | **Depends on:** IMP-220 | **Source:** `calibration/regime.py:264-282`, `calibration/nhpp.py:62-69`, `calibration/hmm.py:365-374,424`

### Details
The sick-call GLM has one coefficient per regime label (`C(regime)[T.SEVERE]` and so on), pooled
across **all bases and all seasons**. But each label comes from a *different* HMM, one per base and season
(nine in all), and a state's meaning is defined only **relative to that fit** (ordered by a composite
severity at `hmm.py:424`). The GLM assumes "SEVERE at YVR in shoulder" and "SEVERE at YUL in winter" are the
same phenomenon.

Measured, nine fits on the fitting window:

| Base | Season | Days | Delay P (C, N, D, S) | Sick rate per crew (C, N, D, S) | Converged / restarts at best |
|---|---|---|---|---|---|
| YUL | shoulder | 184 | .035 .105 .171 .416 | .0058 .0107 .0243 .0379 | yes / 8 |
| YUL | summer_atlantic | 244 | .036 .098 .235 .452 | .0053 .0110 .0208 .0442 | yes / 8 |
| YUL | winter_sun | 303 | .039 .111 .239 .399 | .0068 .0158 .0273 .0444 | yes / 8 |
| YVR | shoulder | 184 | .119 .075 .487 .275 | **.0000** .0089 **.0000** .0417 | **no / 1** |
| YVR | summer_atlantic | 244 | .056 .183 .164 .536 | .0045 .0206 .0138 .0552 | yes / 7 |
| YVR | winter_sun | 303 | .061 .165 .411 .311 | .0074 .0134 .0254 .0528 | yes / 3 |
| YYZ | shoulder | 184 | .011 .070 .087 .244 | .0048 .0106 .0095 .0272 | yes / 4 |
| YYZ | summer_atlantic | 244 | .025 .084 .198 .461 | .0067 .0117 .0217 .0440 | yes / 7 |
| YYZ | winter_sun | 303 | .065 .185 .264 .453 | .0111 .0308 .0235 .0558 | yes / 7 |

What this shows:
- YUL is clean and monotone. The other bases are not. **YVR shoulder is not converged**, only 1 of 8
  restarts reached the best optimum, and two of its states have a fitted sick rate of 0.
- Ordering by a composite score does not give monotone emissions: YVR winter has DISRUPTED delay
  probability 0.411, above SEVERE at 0.311; YVR shoulder has NORMAL below CALM.
- The 184-day shoulder fits rest on 4 short sequences (May; Oct–Nov in two years) and are the weakest.

These fits feed the GLM whose store entry the **YUL winter_sun** scenarios use. A mislabelled YVR shoulder
day shifts the shared regime coefficients that YUL winter_sun is generated from. The *size* of that shift
has not been measured, hence "verify first".

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Scope the GLM to the modelled base** (and all seasons) | Fit the sick-call GLM on `scope.base` only; the other bases' HMMs are no longer needed on the critical path | S | Removes the cross-base assumption and 6 of 9 HMM fits; the scenarios only ever predict for `scope.base` (`generator.py:190-197`) | Less data per coefficient; multi-base Phase 2 will need the question again |
| B | **Tied emissions per base**: fit one HMM on all seasons of a base to get emissions, then refit **transitions only** per season (`params="st"`, which `DisruptionHMM` already supports) | State meaning is fixed per base; seasons differ only in P, as the spec says | M | Principled; reuses `hmm.py`'s existing `params` switch; fewer parameters per season (helps the short shoulder fit) | Assumes emissions do not change by season; two-stage fit; label ordering must come from the pooled fit |
| C | **Tied across bases too** | One emission set for the whole network | L | Strongest guarantee of a shared meaning | A base-level difference (YVR runs later than YUL) becomes noise, not structure |
| D | **Diagnostic only**: report per-fit emission tables, flag a non-monotone or near-zero state | S | No result changes | Does not remove the pooling |
| E | **Per-base GLM** | Fit one GLM per base on its own labels | M | Labels and coefficients share a base | Loses the shared DOW and season effects; 3 coefficient sets to store |

### Recommendation
**D immediately (it is IMP-220), then A as the Phase-1 default.** The simulation models one base, so the
other eight fits are risk without benefit. Move to **B** when multi-base scope arrives, or if the
real-data diagnostic shows the base fits agree. Skip C.

### Decision needed
Data Science: *"Is the Phase 1 sick-call model for the modelled base only, or pooled across bases?"*

### Acceptance criteria (for A)
- [ ] `fit_sick_calls` takes the list of bases to pool; the pipeline passes `[cfg.scope.base]` unless `calibration.glm_pool_bases: all` is configured.
- [ ] The store records which bases the GLM was fitted on.
- [ ] Sensitivity table: YUL `winter_sun` GLM coefficients, pooled over three bases against YUL only, with the regime ratios side by side.
- [ ] Pipeline run time before and after is recorded (6 fewer HMM fits).

### Verification
*   **Automated:** `pytest tests/calibration/test_nhpp.py -k pooled_bases`
*   **Manual:** `crewsim calibrate --season winter_sun --emit` with each setting
    *   **Expect:** the store names its GLM bases, and the regime ratios differ by less than a stated tolerance, or the difference is explained
    *   **Fails if:** an unhealthy fit for a non-scoped base can still change the store silently

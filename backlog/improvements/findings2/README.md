# Findings 2 — Calibration Layer Analysis: Details and Options

**Source:** architecture and calibration-layer analysis of the working tree (October 2026), plus
measurements run on the mock corpus (see [Evidence](#evidence)). Same story format as the rest of
`backlog/improvements/`, with one addition: every story lists **options to choose from**, a
recommendation, and who has to decide.

> These stories are **not yet in `stories.yaml`**, so `verify.py` cannot see them.
> Nothing in this folder has been implemented. It is a decision document.

**Reading guide.** A story keeps its existing id when it already exists in
[low_risk/06_calibration_statistics.md](../low_risk/06_calibration_statistics.md) (marked *existing*).
Where this analysis found new evidence, the story says what changed. New ids continue the epic's
numbering: IMP-214 to IMP-220 (calibration) and IMP-613 (maintainability).

## Story index

| Story | Title | Size | Category | Status | Origin |
|---|---|---|---|---|---|
| [IMP-203](01_model_definition.md#imp-203) | What counts as a "sick call" | S | Decision needed | TODO | existing, **new evidence** |
| [IMP-202](01_model_definition.md#imp-202) | Sick-call model exposure (headcount) | M | Should | TODO | existing, options added |
| [IMP-205](01_model_definition.md#imp-205) | One definition of a delayed / operated flight | S | Optional | TODO | existing, **impact downgraded** |
| [IMP-214](02_statistical_validity.md#imp-214) | Parameter uncertainty reaches the results | M–L | Should | TODO | new |
| [IMP-216](02_statistical_validity.md#imp-216) | Regime labels are not a hard covariate | M | Should | TODO | new |
| [IMP-217](02_statistical_validity.md#imp-217) | Overdispersion handled consistently | S–M | Conditional | TODO | new |
| [IMP-204](02_statistical_validity.md#imp-204) | Delay minutes use a positive-support distribution | M | Should | TODO | existing, **measured** |
| [IMP-218](02_statistical_validity.md#imp-218) | A regime state means the same thing in every fit | M–L | Verify first | TODO | new, **measured** |
| [IMP-211](03_validation_and_guards.md#imp-211) | Calibration fit-quality on holdout | L | Should | TODO | existing, design options |
| [IMP-215](03_validation_and_guards.md#imp-215) | Standalone fitters respect the fitting window | S | Must fix | TODO | new |
| [IMP-220](03_validation_and_guards.md#imp-220) | Health of every regime fit is reported | S | Must fix | TODO | new, **measured** |
| [IMP-208](03_validation_and_guards.md#imp-208) | Provisional stores are marked and gated | S | Should | TODO | existing, options added |
| [IMP-613](04_structure_and_housekeeping.md#imp-613) | Fitting code and sampling code are separate | M | Optional | TODO | new |
| [IMP-219](04_structure_and_housekeeping.md#imp-219) | One hashing scheme, no stale side files | S | Optional | TODO | new |
| [IMP-206](04_structure_and_housekeeping.md#imp-206) | Backlog text refreshed after F-42 | S | Optional | TODO | existing, **now stale** |

| File | Stories | Theme |
|---|---|---|
| [01_model_definition.md](01_model_definition.md) | IMP-203, IMP-202, IMP-205 | What the model is a model *of* |
| [02_statistical_validity.md](02_statistical_validity.md) | IMP-214, IMP-216, IMP-217, IMP-204, IMP-218 | Whether the fitted numbers can be trusted |
| [03_validation_and_guards.md](03_validation_and_guards.md) | IMP-211, IMP-215, IMP-220, IMP-208 | Catching a bad fit before it feeds a recommendation |
| [04_structure_and_housekeeping.md](04_structure_and_housekeeping.md) | IMP-613, IMP-219, IMP-206 | Layering, hashing, stale text |

## Suggested order

1. **IMP-203** first. It is a business decision that changes the scale of every sick-call number, and
   it is the largest single driver of the reserve count.
2. **IMP-220, then IMP-215.** Both are cheap guards. IMP-220 makes unhealthy fits visible before
   anyone argues about IMP-218. IMP-215 closes a hole in the fitting/holdout rule.
3. **IMP-211 (stored diagnostics), then IMP-208.** Gives the numbers that IMP-214 and IMP-216 need to
   show whether they matter.
4. **IMP-214 (report-only), IMP-216 (diagnostic), IMP-217 (diagnostic).** Each has a cheap first step
   that costs nothing in changed results.
5. **IMP-202, IMP-218.** After IMP-203 and IMP-220, because both depend on those answers.
6. **IMP-204, IMP-205, IMP-613, IMP-219, IMP-206.** Independent; do with the next calibration change,
   since IMP-204 bumps `GENERATOR_EPOCH` and rebuilds every scenario cache once.

## Decisions needed

| Story | Question | Owner | Interim decision |
|---|---|---|---|
| IMP-203 | Which D4 `absence_type` values need reserve cover: SICK only, or SICK + FAMILY + INJURY? | Crew Planning | Keep all three, but make the list explicit in `configs/base.yaml` and mark `[CONFIRM: Crew Planning]` |
| IMP-202 | Is D4 every absence, or only absences that hit a duty? Is "at risk" the headcount or the crew on duty? | Data owner | Headcount as of each date |
| IMP-218 | Is YUL / YVR / YYZ regime pooling acceptable for Phase 1, or should the GLM be scoped to the modelled base? | Data Science | Scope-first (see IMP-220 option C) |
| IMP-208 | Should an unconverged or degenerate store block scenario generation on real data? | Data Science | Block on real data, warn on the mock |
| IMP-214 | Is parameter uncertainty in scope for the first Air Transat run, or reported only? | Product owner | Report only |

## Evidence

All figures below were measured on the packaged mock corpus (`src/crewsim/data/corpus`), fitting window
2023-08-01 to 2025-07-31, scope YUL / A321neoLR / FO, `winter_sun`, unless stated. The probes read data and
call the fitters; they write nothing. **The mock generator is itself Poisson with four hidden states, so
agreement on the mock is weaker evidence than it looks. Re-measure on real extracts before relying on any
number below.**

| Quantity | Value | Used in |
|---|---|---|
| D4 absences by type, whole corpus | SICK 4,712 · FAMILY 1,621 · INJURY 1,570 | IMP-203 |
| D4 absences by type, fitting window | SICK 3,047 · FAMILY 1,064 · INJURY 1,024 (SICK = 59%) | IMP-203 |
| D4 at YUL by type | SICK 2,206 · FAMILY 772 · INJURY 748 (SICK = 59%) | IMP-203 |
| Mean duration by type (days) | SICK 2.03 · FAMILY 1.97 · INJURY 2.04 (all medians 1.0) | IMP-203 |
| Delayed flight definition at YUL / A321neoLR | P(delay > 0) = 0.1747 · P(≥ 15 min, not cancelled) = 0.1492 · 151 of 14,643 cancelled | IMP-205 |
| Cancelled rows carrying a delay, whole D8 | 230 | IMP-205 |
| Fitted delay mixture, share of draws clipped to exactly 1.0 min | 4.65% (fitted components); 5.3% (refit on scope, fitting window) | IMP-204 |
| Delay quantiles P50 / P90 / P99 (minutes), observed | 49 / 158 / 333 | IMP-204 |
| … Gaussian mixture on raw minutes (current) | 48.7 / 177.1 / 278.2 | IMP-204 |
| … Gaussian mixture on log-minutes | 50.8 / 156.9 / 340.3 | IMP-204 |
| … single gamma | 53.6 / 153.4 / 287.4 | IMP-204 |
| Delay mixture BIC, k = 2 → 3 | raw: 27,418 → 27,119 · log: 7,293 → 7,272 | IMP-204 |
| Label certainty, YUL winter_sun (303 days) | mean max-posterior 0.875 · 25.4% of days below 0.8 · 6.6% below 0.6 | IMP-216 |
| GLM regime ratios vs NORMAL / HMM sick-rate ratios | DISRUPTED 1.69 / 1.73 · SEVERE 2.97 / 2.80 · CALM 0.47 / 0.43 | IMP-216 |
| Daily sick-call var/mean by fitted regime | CALM 1.07 · NORMAL 0.86 · DISRUPTED 1.09 · SEVERE 1.21 | IMP-217 |
| GLM dispersion | alpha = 1.5e-5 (effectively Poisson) | IMP-217 |
| One HMM fit (303 days, 8 restarts) | 0.8 s; 27 free parameters | IMP-214 |
| HMM label agreement with the mock's hidden truth | 82.4% (243 / 295); every miss is an adjacent state | IMP-216 |
| Regime fits that feed the GLM | 9 (3 bases × 3 seasons). **YVR/shoulder did not converge** (1 of 8 restarts at best); YVR/shoulder has two states with sick rate 0.0000 | IMP-218, IMP-220 |

Per-fit emissions for all nine fits are in [IMP-218](02_statistical_validity.md#imp-218) and
[IMP-220](03_validation_and_guards.md#imp-220).

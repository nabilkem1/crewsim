# Findings 2 — Validation and Guards

**4 stories** · Source: calibration-layer analysis (October 2026) · See the [README](README.md) for the evidence table.

The calibration layer fits well on the mock, and its only out-of-sample check covers one of its three
models. These stories are about **catching a bad fit before it feeds a recommendation**. IMP-215 and
IMP-220 are small and close real gaps in rules the code already claims to enforce.

---

<a id="imp-211"></a>
## [TODO] IMP-211 — Calibration fit-quality on holdout
**Size:** `L` | **Category:** Should | **Existing story:** IMP-211 (this adds design options) | **Depends on:** IMP-202, IMP-204, IMP-206 text refresh
**Source:** `calibration/regime.py:362-384` (the one existing holdout score), `api/routers/calibration.py:186-190`

### Details
The regime HMM reports an out-of-sample score: holdout log-likelihood per day of -6.14, against -9.64
for a one-state model, on 151 holdout days. That is a strong result and a real check.

**Nothing else is checked out of sample.**

| Model | Holdout check today |
|---|---|
| Regime HMM | Yes, log-likelihood per day vs a one-state baseline |
| Sick-call GLM + duration lognormal | **None** |
| Delay probability and duration mixture | **None** |
| The generated chain as a whole (does a simulated season look like a real one?) | **None** |

The API says so itself (`goodness_of_fit_note`: "The sick-call GLM and the delay mixture do not report one
here"). The consequence is that the two models which produce the numbers a planner reads, daily sick
calls and delay minutes, are validated by nothing but their in-sample fit.

**Design choices that decide whether the check is fair:**
- *Which regime labels to use on the holdout.* `decode_window` (`regime.py:304`) labels holdout days with
  the already-fitted models and no refit, which is correct. But a *smoothed* (Viterbi) label on the
  holdout uses that day's own sick calls, so scoring the GLM against it is circular, the same issue as
  IMP-216. A *filtered* label (forward pass only) uses only the past.
- *Conditional or unconditional.* Scoring the GLM given decoded labels tests the GLM alone. Simulating from
  P and comparing marginals tests the whole generative chain, which is what scenarios actually use.
- *Power.* One holdout winter is 151 days. Pass/fail thresholds have to be loose, and each statistic needs
  an interval.

### Options

| | Option | What is built | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **New gate `vcal`** (as in the story) | Three sections with PASS/FAIL and thresholds in `gates.calibration`; shown with V1–V9 | L | A hard sign-off; appears in the report beside the other gates | Thresholds have to be invented, on 151 days of one season; can fail for noise |
| B | **Stored diagnostics, no verdict** | Add a `holdout` block per model to the store (like the HMM already has) and show it in the calibration UI and report | M | Same pattern as today; no thresholds to defend; gives IMP-214 and IMP-216 their numbers | A planner can ignore it |
| C | **B first, then A reading B's numbers** | Diagnostics now; a gate later once real-data thresholds are known | M, then M | Right order: you cannot set a threshold before seeing a distribution | Two steps |
| D | **Unconditional simulation check only** | Simulate many 151-day seasons from the store; compare daily-count distribution and SEVERE run lengths with the holdout | M | Tests the whole chain, including P | Does not isolate which model failed |

### What each section should measure

| Section | Statistic | Notes |
|---|---|---|
| Sick calls | Mean log-score per day against a no-regime GLM; share of holdout days inside the 90% predictive interval; observed var/mean (links to IMP-217) | Use filtered labels, not Viterbi |
| Regime chain | Simulated vs observed run-length distribution of SEVERE spells; stationary-share against the holdout day shares | Weak power; report an interval |
| Delays | Per-regime KS or P50/P90/P99 comparison on holdout minutes; delay probability per regime against holdout frequency | Overlaps IMP-204's quantile table |

### Recommendation
**C.** Build the diagnostics (B) with the fit, so every calibration job reports them. Promote them to a
gate (A) once there is a distribution from real data to set a threshold against. Include D as the
fourth section, since it is the only one that tests the chain the scenarios really use.

### Decision needed
Data Science: the pass thresholds (set after the first real-data run) and whether `vcal` blocks a report
or only warns. The name must not collide with V8.

### Acceptance criteria (for C)
- [ ] `store.diagnostics.holdout` has `sick_calls`, `regime_chain` and `delays` sections, each with the statistic, its interval and the sample size.
- [ ] Holdout labels come from `decode_window` and the **filtered** (forward) posterior; the choice is written in the docstring.
- [ ] The calibration UI and the HTML report show the three sections; the API's `goodness_of_fit_note` is updated to match.
- [ ] No holdout day is used by any fitter (a test asserts the fit inputs exclude the holdout window).
- [ ] Gate thresholds in `configs/base.yaml` under `gates.calibration` are added with the gate, each marked `[CONFIRM: Data Science]`.

### Verification
*   **Automated:** `pytest tests/calibration -k holdout` and, later, `pytest tests/gates/test_vcal.py`
*   **Manual:** `crewsim calibrate --season winter_sun --emit`
    *   **Expect:** three holdout sections, each with a statistic and its interval
    *   **Fails if:** a section prints no interval, or a model reports no holdout figure

---

<a id="imp-215"></a>
## [TODO] IMP-215 — Standalone fitters respect the fitting window
**Size:** `S` | **Category:** Must fix | **Depends on:** — | **Source:** `cli.py:854-858,899-915,938-946`, `calibration/nhpp.py:21-26`, `calibration/delays.py:15-23`

### Details
The pipeline enforces the fitting/holdout separation (AUD-05): `run_pipeline` hands the fitting window to
each fitter. **Two CLI paths do not:**

- `crewsim calibrate sick-calls` calls `nhpp.fit_sick_calls(cfg)` with **no window** (`cli.py:903`).
- `crewsim fit-delays` calls `delays.fit_delays(cfg, args.season)` with **no window** (`cli.py:946`).

Both default to `window=None`, which means the **full corpus, holdout included**. `calibrate sick-calls`
also accepts `--window` (it is a parent option, `cli.py:459`) and silently ignores it. The guard at
`cli.py:856` only rejects the literal value `--window holdout`; it does not stop either fitter from
reading the holdout.

Both paths write files the rest of the system can find: `nhpp_sick_calls.json` and
`delay_mixture_<season>.json` in `params_dir`. These are separate from the store (the store builds its own
dict, `pipeline.py:114-161`), so they cannot corrupt a generated store. But a coefficient table or delay
mixture printed by the CLI looks like "the" calibration result and was fitted on months the validation
gates treat as unseen.

A fitter whose `window=None` default is a silent full-corpus fit is also an easy mistake to repeat in any
new caller.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Pass the window through** | Both CLI handlers resolve `cfg.windows.get(args.window)` as `calibrate regime` already does (`cli.py:869-872`) and pass it | XS | Smallest fix; consistent with the one path that is right | A future caller can still omit it |
| B | **Make `window` required**; `FULL_CORPUS` sentinel for the explicit case | Signature change; the CLI passes the sentinel only with `--full-corpus`; output is stamped `window: full_corpus` | S | Impossible to forget; the exploratory case stays possible and visible | Tests that call the fitters without a window need updating (check `tests/calibration`) |
| C | **Remove the standalone fitters** | Keep `--emit` and `calibrate regime` only | S | One path to maintain; nothing can drift | Loses a debugging handle (`tools/debug/calibrate_steps.py` is a script version) and updates CLI tests and docs |
| D | **Quarantine the output** | Standalone results written to `diagnostics/` with the window in the file name, never `nhpp_sick_calls.json` | XS | Stops a side file being mistaken for a calibration result | Does not fix the window |

### Recommendation
**A and B together, plus D's file naming.** A fixes today's behaviour, B stops the next caller repeating it,
and the file name carries the window so a human reading the folder can tell. Also make the holdout guard
compare resolved windows instead of the string `"holdout"`.

### Decision needed
None. This is a defect against the project's own rule (§6.4).

### Acceptance criteria
- [ ] `calibrate sick-calls` and `fit-delays` accept `--window` (default `fitting`), pass the resolved window, and refuse `holdout` with the same message as `--emit`.
- [ ] `fit_sick_calls` and `fit_delays` require a window or `FULL_CORPUS`; `FULL_CORPUS` is recorded in the returned dict and in the file name.
- [ ] Side files are named with the window (e.g. `nhpp_sick_calls_fitting.json`).
- [ ] Test: with a synthetic corpus whose holdout contains a sentinel row, the standalone fits' inputs exclude it.
- [ ] Test: `crewsim calibrate sick-calls --window holdout` exits 1.

### Verification
*   **Automated:** `pytest tests/test_cli.py -k "calibrate and window"`
*   **Manual:** `crewsim calibrate sick-calls --window holdout`
    *   **Expect:** exit 1 and the refusal message
    *   **Fails if:** it fits

---

<a id="imp-220"></a>
## [TODO] IMP-220 — Health of every regime fit is reported
**Size:** `S` | **Category:** Must fix | **Depends on:** — | **Source:** `calibration/pipeline.py:86-92,163-169`, `calibration/regime.py:264-282,413-426`

### Details
The pipeline fits **nine** regime HMMs (3 bases × 3 seasons, `regime.py:264-282`) and uses all of them: their
labels build the table that the sick-call GLM and the delay fit condition on. But it **inspects only one**.
`fit_regime` summarises the scoped (YUL, requested season) model, and that is the model whose convergence
and degenerate-state flags reach the store and the `[WARN]` lines (`pipeline.py:166-169`).

The other eight run silently. Measured, fitting window:

| Fit | Converged | Restarts at best optimum | Warning-level finding |
|---|---|---|---|
| YUL shoulder / summer / winter | yes | 8 / 8 / 8 | none |
| YVR shoulder | **no** | **1 of 8** | two states with sick rate 0.0000 (hit the 1e-6 floor) |
| YVR summer_atlantic | yes | 7 | NORMAL sick rate (.0206) above DISRUPTED (.0138) |
| YVR winter_sun | yes | 3 | DISRUPTED delay probability (0.411) above SEVERE (0.311) |
| YYZ shoulder | yes | 4 | self-transitions of 0.17 and 0.14 for NORMAL and DISRUPTED; DISRUPTED sick rate (.0095) below NORMAL (.0106) |
| YYZ summer_atlantic | yes | 7 | none notable |
| YYZ winter_sun | yes | 7 | NORMAL sick rate (.0308) above DISRUPTED (.0235) |

A non-converged fit with states that explain "zero sick calls" is a fit that has found a local optimum or
overfitted a few days. Its labels are used as-is. Restarts-at-best below the total also mean the likelihood
surface is rough there, so the labels may change with the seed.

This is the guard that lets IMP-218 (state meaning) be decided on facts, and it is a two-hour change.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Collect and report all fits** | `diagnostics.regime_fits`: per (base, season) `converged`, `restarts_reaching_best`, `degenerate_states`, `min_state_share`, `n_days`, `n_sequences`, and a `[WARN]` per unhealthy fit. In `diagnostics`, so excluded from the hash | S | No result changes; closes the blind spot | Visibility only |
| B | **Fail the calibration** if any fit that feeds the GLM is unhealthy, unless `--allow-unhealthy` | A plus a hard check | S | Nothing unhealthy can reach a store | On the mock YVR shoulder would block every run today, so a threshold decision is needed first |
| C | **Fit only what the scope needs** | Fit the HMM for the scoped base only; the GLM is fitted on that base (IMP-218 option A) | S–M | Removes eight of nine fits, so removes the blind spot | A design change (see IMP-218); defers the pooled model |
| D | **Retry unhealthy fits with more restarts / a different seed** automatically | More restarts when `restarts_reaching_best` is below a threshold | S | Fixes some local optima | Hides the cause; masks genuinely unidentified states |

### Recommendation
**A now.** It is an overdue guard and carries no risk. Then decide B or C with IMP-218. Do not
add D: if 8 restarts cannot find one optimum, the data does not support four states there, and that is information.

### Decision needed
Data Science: the health thresholds, *"how many restarts must agree, and what minimum state share?"* The
existing `min_state_share` (0.01) only catches empty states, not a state holding 40 days with a zero rate.

### Acceptance criteria (for A)
- [ ] `diagnostics.regime_fits` lists every fit the pipeline performed, with the fields above.
- [ ] A `logging` warning (not `print`) for each fit that is unconverged, has `restarts_reaching_best` below `calibration.regime_hmm.min_restart_agreement` (new), or has a state with a rate at the `min_probability` floor.
- [ ] The run log and the calibration UI list unhealthy fits by name.
- [ ] Test: a synthetic base too short to fit produces a named warning and does not abort the others.

### Verification
*   **Automated:** `pytest tests/calibration/test_calibrator_pipeline.py -k fit_health`
*   **Manual:** `crewsim calibrate --season winter_sun --emit`
    *   **Expect:** a warning naming `YVR / shoulder` as unconverged
    *   **Fails if:** an unconverged fit produces no warning

---

<a id="imp-208"></a>
## [TODO] IMP-208 — Provisional stores are marked and gated
**Size:** `S` | **Category:** Should | **Existing story:** IMP-208 (this adds options) | **Depends on:** IMP-220 | **Source:** `calibration/pipeline.py:163-169`, `calibration/nhpp.py:120-124`, `scenarios/generator.py:90-138`

### Details
Today a store can be written and used while provisional:
- A non-converged GLM sets `converged: false` and prints a `[WARN]` (`pipeline.py:163-165`). `print`,
  not `logging`: a headless job loses it. The API captures Python *warnings*, not `print`, so the
  calibration run log may not show it.
- `generate_scenarios` never reads `converged` (`generator.py:90-138`). It will generate from an
  unconverged store without comment.
- The HMM's own `converged`, `degenerate_states` and restart agreement are stored, but nothing reads
  them either.
- If `cfg.windows` is missing, `run_pipeline` silently fits the whole corpus (`pipeline.py:73-80`) and
  still stamps no window.

The old rationale (`nhpp.py:114-119`) is sound: *"a visible flag beats a blocked calibration."* What is
missing is the second half, **someone downstream reading the flag**.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Block generation** unless `--allow-unconverged` | `generate_scenarios` raises on `converged: false` or a missing window | S | Nothing provisional is used by accident | Blocks work on the mock, which is the common case today |
| B | **Mark, do not block** | Store gets `quality: {status: "PROVISIONAL" or "OK", reasons: [...]}`; the report, API and UI show a banner; scenario files carry the status | S | No friction; the reader is told | A banner can be ignored |
| C | **B by default, A on real data** | `calibration.fail_on_provisional: false` for the mock, `true` once real extracts are configured | S | Right default for each situation | One more config switch to get right |
| D | **Retry, then fail** | Longer GLM retries, then raise | M | Fewer provisional stores | Does not address the HMM, nor the missing window |

### Recommendation
**C.** One `quality` block fed by every check (GLM convergence, HMM convergence, degenerate states from
IMP-220, missing window), shown everywhere, and a switch that turns it from a banner into a refusal.
Replace the `print` with `logging.warning` so the job log catches it.

### Decision needed
Data Science: *"Should an unconverged or degenerate store block scenario generation on real data?"*
The recommendation is to block.

### Acceptance criteria (for C)
- [ ] `store.quality = {status, reasons}` built from GLM convergence, HMM health of every fit used, and window handling. In the hash (it describes the parameters), unlike `diagnostics`.
- [ ] `generate_scenarios` raises on `PROVISIONAL` when `calibration.fail_on_provisional` is true, and names the config key and the flag.
- [ ] `run_pipeline` raises if `cfg.windows` is absent unless `--full-corpus` is passed, and records the flag in the store.
- [ ] All warnings use `logging`/`warnings`, not `print`; they appear in the calibration run log.
- [ ] The HTML report and the calibration UI show the status.

### Verification
*   **Automated:** `pytest tests/engine/test_scenario_gen.py -k provisional`
*   **Manual:** `crewsim scenarios generate --master-seed master --scenarios 5` against a store with `converged: false`, with the switch on
    *   **Expect:** a refusal naming the switch
    *   **Fails if:** a parquet is written

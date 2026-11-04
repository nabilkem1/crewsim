# Findings 2 — Structure and Housekeeping

**3 stories** · Source: calibration-layer analysis (October 2026) · See the [README](README.md) for the evidence table.

Nothing here changes a result. These are layering, hashing and stale-text problems that make the calibration
layer harder to change safely. All three are **Optional** by the backlog's definition: do them alongside
the next calibration change, not on their own schedule.

---

<a id="imp-613"></a>
## [TODO] IMP-613 — Fitting code and sampling code are separate
**Size:** `M` | **Category:** Optional | **Depends on:** — | **Source:** `scenarios/generator.py:11,198-199,216`, `calibration/nhpp.py:9,175-228`, `calibration/delays.py:7,187-201`, `calibration/regime.py:35`, `data/profile.py:371`, `tests/test_dependency_rule.py`

### Details
Calibration is meant to be **offline and heavy** (statsmodels, scikit-learn, hmmlearn, scipy). Scenario
generation and the engine are meant to run from a **frozen parameter file**. The code does not keep that line:

| Import | Where | Why it hurts |
|---|---|---|
| `scenarios/generator.py` imports `calibration.nhpp` and `calibration.delays` | `generator.py:11` | Needs only three tiny numpy functions (`predict_intensity`, `sample_count`, `sample_delay_minutes`), but the import pulls in `statsmodels` and `sklearn` (`nhpp.py:9`, `delays.py:7`) |
| `data/profile.py` imports `calibration.regime` | `profile.py:371` | The data layer depends on a layer built on top of it. The HMM-labelled profile needs the regime labels |
| `calibration/regime.py` imports `engine.crn` | `regime.py:35` | An offline layer reaches into the simulation engine for a seeding helper. Harmless in practice (`crn.py` imports only numpy and hashlib), wrong in principle |

Why it matters, concretely:
- The grid runner executes policies as separate processes (`generator.py:231-242` documents this). Each
  worker that imports the generator imports the full fitting stack. *Import time was not measured.*
- A reader cannot tell which functions are **model definition used at generation time** (the prediction
  formula, the samplers) from **fitting routines**. `predict_intensity` must match the patsy encoding the
  fit used, so it is coupled to the fitter's formula, and that coupling lives in one file but crosses a
  layer.
- The one architectural rule that is enforced (`tests/test_dependency_rule.py`: engine must not import
  simpy) shows the project already wants rules like this. No equivalent exists for the layers above.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **Extract the sampling/prediction functions** into a numpy-only module (e.g. `scenarios/models.py`); the calibration modules import *from* it, and re-export the old names for one release | Move 3 functions and their tests | S–M | Generator no longer imports statsmodels or sklearn; smallest useful split | `predict_intensity`'s docs and its statsmodels-parity test must move with it, keeping the test against `res.predict()` |
| B | **A plus import rules in a test** | Extend `tests/test_dependency_rule.py`: `scenarios/` and `engine/` must not import `statsmodels`, `sklearn`, `hmmlearn`; `data/` must not import `calibration/` | M | Keeps the layering from regressing | The `data -> calibration` rule needs fixing first (below) |
| C | **Fix `data -> calibration`**: `profile.py` takes the label frame as an argument instead of fitting the HMM | S | Removes the inversion; the caller (CLI/report) owns the fitting | Changes the profile function signatures and its tests |
| D | **Move `crn.py` to a neutral `crewsim/rng.py`** | Rename and update imports | S | Neutral location for a shared helper | Churn for a cosmetic benefit; `engine.crn` may be cited in the spec and tests |
| E | **Leave as is** | None | XS | Nothing breaks | The coupling grows with every new model |

### Recommendation
**A + B, with C as the prerequisite for B's data rule.** Skip D unless a third consumer of `crn` outside
`engine/` appears. Order: C, A, then B so the rules can pass on day one.

### Decision needed
None. If the owner prefers fewer rules, A on its own is still worth doing.

### Acceptance criteria (for A + B)
- [ ] `scenarios/generator.py` imports no module that imports statsmodels, sklearn or hmmlearn (checked by a test that imports it in a subprocess and inspects `sys.modules`).
- [ ] The three functions live in one numpy-only module, with the statsmodels-parity test (`test_predict_intensity_matches_glm_predict`) kept as is.
- [ ] `data/` does not import `calibration/`; `profile.py` receives labels as an argument.
- [ ] `tests/test_dependency_rule.py` has one test per rule, each with an error message that says what to move where.

### Verification
*   **Automated:** `pytest tests/test_dependency_rule.py tests/calibration/test_nhpp.py`
*   **Manual:** `python -X importtime -c "import crewsim.scenarios.generator"`
    *   **Expect:** no statsmodels or sklearn in the import list
    *   **Fails if:** either appears

---

<a id="imp-219"></a>
## [TODO] IMP-219 — One hashing scheme, no stale side files
**Size:** `S` | **Category:** Optional | **Depends on:** — | **Source:** `calibration/pipeline.py:34-40`, `calibration/nhpp.py:162-171`, `calibration/delays.py:174-183`, `calibration/regime.py:476-489`

### Details
Four hashes are computed over the same kind of object, by two different methods:

| Object | Hash | Where |
|---|---|---|
| Parameter store (the one that matters: keys the scenario cache) | blake2b, 20-byte digest, sorted keys | `pipeline.py:34-40` |
| Sick-call fit | `sha256[:8]` of sorted-key JSON | `nhpp.py:162-163` |
| Delay mixture | `sha256[:8]` | `delays.py:174-175` |
| Regime fit | `sha256[:8]`, with `default=str` | `regime.py:476-477` |

The three short hashes are 32 bits, which is fine for a label but is shown to users as a "[DIGITAL
RECEIPT]" next to the real store hash, so a reader cannot tell which one is authoritative. They also do not
use `allow_nan=False`, so a NaN would hash and serialise as the non-standard token `NaN` (IMP-207 asks for the
strict form on every write).

The same three fitters also write **side files** to `params_dir`: `nhpp_sick_calls.json` (not keyed by
season or window, overwritten by every run), `delay_mixture_<season>.json` and `regimes_winter.json` (a
name that does not match the season id `winter_sun`; it comes from `seasons.yaml`). None is read by
generation, which uses only the store (`generator.py:91-93`). They are leftovers of the pre-pipeline
design, and a stale one is indistinguishable from a fresh one.

**The store hash is unaffected by changing any of this.** The pipeline builds the store from selected keys
(`pipeline.py:114-161`), none of which carries a sub-fit's `content_hash`, so no scenario cache is
invalidated.

### Options

| | Option | What changes | Effort | Pros | Cons |
|---|---|---|---|---|---|
| A | **One shared hash helper** | `pipeline.content_hash` made public and used by every fitter; `allow_nan=False`; sub-fit receipts become blake2b | S | One scheme; strict JSON | The receipt strings printed by the CLI change |
| B | **Drop the side files**; the store is the only artifact; standalone fitters print and write nothing | Remove 3 writes and their callers' use of `_saved_path` | S | Nothing stale can exist | The standalone CLI commands lose their "Saved parameter file" line; `tests/calibration/test_param_store.py` may rely on them |
| C | **Keep the side files, key them** by season and window (links to IMP-215) | Rename files; add `window` and `fitted_at` to each | S | Keeps the debugging handle | Still two places for the same numbers |
| D | **Leave as is** | None | XS | No churn | The "which hash is real" question stays |

### Recommendation
**A + C**, because B removes a feature the CLI advertises and the cost of keeping it is a file name. If
IMP-215 chooses to remove the standalone fitters, take **B** instead and A is then moot for them.

### Decision needed
None beyond IMP-215's choice.

### Acceptance criteria (for A + C)
- [ ] One helper computes every content hash; all writes use `allow_nan=False`.
- [ ] Side files include the window and the season in their names and a `fitted_at`.
- [ ] A test asserts that changing a side file's content does not change the store hash, and the reverse.

### Verification
*   **Automated:** `pytest tests/calibration/test_param_store.py tests/calibration/test_calibrator_pipeline.py`
*   **Manual:** `crewsim calibrate --season winter_sun --emit` twice
    *   **Expect:** the same store `content_hash`, and each side file named with its window
    *   **Fails if:** a side file is overwritten by a different season

---

<a id="imp-206"></a>
## [TODO] IMP-206 — Backlog text refreshed after F-42
**Size:** `S` | **Category:** Optional | **Existing story:** IMP-206 (now stale), parts of IMP-204, IMP-207, IMP-211 | **Depends on:** —
**Source:** `backlog/improvements/low_risk/06_calibration_statistics.md`, `calibration/delays.py:90`, `calibration/regime.py`

### Details
F-42 replaced the D9-label regime fit with a hidden Markov model. The calibration stories written before it
still describe the old design, so a developer picking one up would implement against code that no longer exists.

| Story | Stale text (paraphrased) | What the code does now |
|---|---|---|
| IMP-206 | "`pi0` is a filtered marginal, not a steady state" | `pi0` is the stationary distribution of `P` (`regime.py:420`) |
| IMP-206 | "`transition_rows_backed_off` and `quantiles` are copied into the store" | Back-off is gone; a Dirichlet pseudo-count replaces it (`transition_pseudocount`); the quantiles only seed one EM restart |
| IMP-206 | "If NORMAL is missing or has a zero mean, fail loudly" | NORMAL always exists (the HMM has four fixed states). **The real risk left** is the multiplier division `m.sick_rate_ / m.sick_rate_[normal]` (`regime.py:402`): a NORMAL rate at the `min_probability` floor gives a huge multiplier. Keep this guard |
| IMP-206 | "`label_agreement` docstring describes the D9 fit" | The docstring now describes the optional D9 cross-check accurately |
| IMP-207 | "D9 with fewer than 2 consecutive days; unknown or null `disruption_class`" | D9 is not an input. The analogue is `obs.height < 2` (`regime.py:258`), which already returns `None` and raises a clear error in `fit_regime` |
| IMP-204 | "The random seed comes from config, not the literal `42`" | Already satisfied (`delays.py:142`) |
| IMP-211 | "regime chain: simulated vs observed run-length" | Still valid; the run-length data comes from `decode_window` |

Smaller items found on the way:
- `delays.py:90` rebinds `regime_days` (the function's parameter, already copied to `d9` at line 51) to a
  per-regime day count. It works, but one name for two things invites a bug.
- `configs/base.yaml:149` calls `delay_gmm_random_state` "a literal seed"; it is a config value. The note is
  about it *not being a CRN stream*, which stays true.
- `nhpp.py`'s module docstring still says "(S0-07)" only; the regime dependency and the F-42 label source are
  described in the function docstring, not the module's.

### Options

| | Option | Effort | Pros | Cons |
|---|---|---|---|---|
| A | **Close IMP-206 as superseded by F-42**; open one small story for the multiplier guard; amend the stale lines of IMP-204 and IMP-207 | S | Clean backlog; the one live concern survives | Needs a decision on the ids |
| B | **Rewrite IMP-206 in place** | S | Keeps the id | The story is a different one afterwards, which hides history |
| C | **Add a "superseded by F-42" note to each stale line** and leave the rest | XS | Fastest; keeps history | The stories stay long and partly dead |
| D | **Leave** | XS | Zero effort | Someone implements against a design that is gone |

### Recommendation
**A.** The only live concern, the multiplier denominator, becomes one acceptance line in IMP-220's follow-up or
a new story of its own. Do this before anyone starts IMP-206, IMP-207 or IMP-211.

### Decision needed
None.

### Acceptance criteria (for A)
- [ ] IMP-206 marked superseded, with the F-42 commit or story id.
- [ ] The multiplier-denominator guard recorded as an acceptance criterion where it will be built: raise if the NORMAL sick rate is at or below a configured floor.
- [ ] IMP-204 and IMP-207 text updated to the current code.
- [ ] `delays.py:90` renamed (e.g. `days_per_regime`).

### Verification
*   **Automated:** `python backlog/verify.py` (same result as before the edits)
*   **Manual:** read `low_risk/06_calibration_statistics.md` against `calibration/regime.py`
    *   **Expect:** every acceptance line names code that exists
    *   **Fails if:** a line refers to D9 as an input

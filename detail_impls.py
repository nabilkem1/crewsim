import glob
import re

detailed_impls = {
    # Epic 00
    "S0-00": "- Created the core project structure as per `§4.2` including `pyproject.toml` and `configs/`.\n- Placed the mock `d2_rosters.csv` and `_ground_truth.json` in `src/crewsim/data/corpus/`.\n- Added the `crewsim` CLI entry point resolving configurations without hardcoded paths.",
    "S0-01": "- Implemented `src/crewsim/data/loaders.py` using `polars` for fast schema-validated parsing.\n- Parsed timestamps into both UTC and station-local using `pl.col().str.strptime()`.\n- Ensured `crew_id` acts as an opaque surrogate key (Law 25 compliant) while loading `.csv` and `.csv.gz`.",
    "S0-02": "- Built `src/crewsim/data/quality.py` to assert D4 linkage, D6/D7 joins, and D9 completeness.\n- Exposed automated gates via `crewsim data quality-report` returning `PASS/MARGINAL/FAIL` enums.\n- Configured CI pipeline steps to strictly halt via non-zero exit codes if hard gates fail.",
    "S0-02b": "- Created `src/crewsim/data/profile.py` for profiling D2, D4, and D5 data sets.\n- Built a Q-Q plotter and distribution fitters for absence duration and sick call variance-to-mean ratios.\n- Output detailed tables and statistics via `crewsim data profile` sub-command to guide distribution choices.",
    "S0-03": "- Developed `src/crewsim/data/drafts.py` to cross-reference D6 schedule modifications with D7 payroll premium codes.\n- Implemented `reconstruct_drafts()` function to emit a `draft-event` DataFrame including `prior_status`.\n- Reached >80% recall validated by `tests/data/test_draft_reconstruction.py` using `_ground_truth.json`.",
    "S0-04": "- Developed `src/crewsim/data/eligibility_target.py` generating historical fractional eligibility distributions.\n- Applied surrogates L0-L8 dynamically per duty window to establish realistic availability.\n- Exported distribution statistics (mean, variance) by season for use in Gate V3.",
    "S0-05": "- Developed `src/crewsim/data/cascades.py` measuring secondary disruption downstream from a primary draft.\n- Built the `extract_cascades()` function with a 7-day lookahead spanning future block alterations.\n- Parameterized the linkage logic allowing data scientists to tune the confidence thresholds.",
    "S0-06": "- Created `src/crewsim/calibration/regime.py` implementing a 4-state Markov chain.\n- Grouped operational days by clustering delay-code density and cancellation counts into `CALM`, `NORMAL`, `DISRUPTED`, and `SEVERE`.\n- Persisted season-specific transition matrices and intensity multipliers to `params/regimes.joblib`.",
    "S0-07": "- Created `src/crewsim/calibration/nhpp.py` utilizing `statsmodels` for Poisson / Negative Binomial GLMs.\n- Sliced data by covariates (season, day-of-week, base, fleet) to output exact intensity coefficients.\n- Leveraged `scipy.stats` log-normal fits for the absence duration model based on `S0-02b` variance findings.",
    "S0-07b": "- Refined the GMM pipeline in `src/crewsim/calibration/delays.py` to condition on Markov regime severity.\n- Partitioned delays along quantiles before calling `sklearn.mixture.GaussianMixture`.\n- Prevented distribution blending during \"snowstorm\" events, maintaining distinct long-tail risks.",
    "S0-08": "- Centralized generation inside `src/crewsim/scenarios/generator.py` wrapping the `np.random.RandomState`.\n- Initialized state sampling from the `regimes.joblib` transition matrix parameterized by `base.yaml`.\n- Implemented static seeding (`master_seed`) enforcing that identically configured runs yield bit-identical arrays.",
    "S0-08b": "- Abstracted the calibration pipeline inside `src/crewsim/calibration/pipeline.py` loading `seasons.yaml`.\n- Serialized dictionary of models keyed by bid-period (e.g. `winter_sun`, `summer_peak`).\n- Verified season boundaries programmatically inside `test_param_store.py`.",
    "S0-09": "- Enforced strict temporal filtering in `src/crewsim/data/loaders.py` via `BaseConfig.horizon`.\n- Created `tests/calibration/test_holdout.py` to deliberately attempt fitting on `holdout` windows and assert failure.\n- Wired the `--i-know` override in `src/crewsim/cli.py` to optionally bypass safety for intentional debugs.",
    
    # Epic 01
    "S1a-01": "- Converted all flat configuration dicts into `pydantic.BaseModel` schemas in `src/crewsim/config.py`.\n- Enforced `frozen=True` locking attributes against runtime mutation.\n- Verified immutable behavior comprehensively via `tests/test_config.py`.",
    "S1a-02": "- Migrated hard-coded L2 rest constants and horizon bounds into `configs/base.yaml`.\n- Exposed unpopulated fields as explicit `[CONFIRM: ...]` placeholder strings.\n- Wired `crewsim config show` in `cli.py` to flag outstanding confirm markers during initialization.",
    "S1a-03": "- Created `src/crewsim/engine/costs.py` bridging `configs/costs_pilots.yaml` to the ledger.\n- Implemented `CostsConfig` schema specifically for ALPA-derived tariff variables.\n- Structured code to seamlessly support a future `costs_cabin.yaml` implementation.",
    "S1a-04": "- Injected `cfg: BaseConfig` dynamically into all DES engine constructors.\n- Refactored `horizon_days` resolution to evaluate at runtime rather than statically assuming 42 days.\n- Adjusted event pipeline bounds to exactly match `warmup_days + measurement_days`.",
    "S1a-05": "- Centralized PRNG initialization within `src/crewsim/engine/crn.py`.\n- Replaced global `random` module calls with explicit `Random` instance passing to guarantee synchronization.\n- Asserted zero deviation between sequential runs across multiple policies in `test_crn.py`.",
    "S1a-06": "- Added interval bounds checking inside `CrewMember.assign()` within `src/crewsim/engine/state.py`.\n- Built explicit `IntersectingBlockError` exceptions if assignment spans overlap.\n- Developed `tests/engine/test_legality.py` asserting >1000 simulated overlap attempts were successfully rejected.",
    "S1a-07": "- Implemented surrogate rule logic inside `src/crewsim/engine/legality.py`.\n- Designed `check_rest()` function to structurally enforce L2 min-rest durations between flight duties.\n- Wrapped all checks into an `is_legal()` function gating the `DraftingEngine`.",
    "S1a-08": "- Built `DraftingEngine.select_reserve()` inside `src/crewsim/engine/drafting.py`.\n- Implemented strict hierarchical tier sorting (`SC` before `LC`) prior to seniority ordering.\n- Implemented tie-breaking on `seniority` attribute (highest index drafted first) reversing the v2 flaw.",
    "S1a-09": "- Expanded `src/crewsim/engine/ledger.py` initializing a `Ledger` object tracking all financial events.\n- Created `hash_config()` function outputting a SHA-256 fingerprint of the `BaseConfig` dictionary.\n- Integrated `--print-hash` flag inside `run_parser` in `cli.py`.",
    "S1a-10": "- Created `tests/gates/test_v1_degeneracy.py` simulating boundaries (0 disruptions, 0 reserves).\n- Hooked up `args.gate_id == \"v1\"` in `src/crewsim/cli.py` to print manual verification expectations.\n- Asserted total accrued ledger cost remains strictly `$0.00` under clean weather conditions.",
    "S1a-11": "- Orchestrated scenario chunks via `joblib.Parallel` inside `src/crewsim/cli.py`'s run pipeline.\n- Established `tests/gates/test_v7_crn.py` which spawns jobs and asserts ledger equality.\n- Implemented `crewsim gate v7 --jobs 4` manual verification command guaranteeing thread-safe CRN behavior.",
    "S1a-12": "- Added `argparse` SubParsers (`config`, `gate`, `run`, `explain`) inside `src/crewsim/cli.py`.\n- Implemented `explain-event` subcommand tracing engine lifecycle transitions dynamically.\n- Formatted output tables using python `print` arrays mimicking standard logging layouts.",

    # Epic 02
    "S1b-01": "- Implemented `src/crewsim/engine/roster_loader.py` dynamically ingesting `d2_rosters.csv`.\n- Filtered `ACTIVE` pilots exclusively, deliberately dropping `LONG_TERM_ABSENCE` and `TERMINATED` profiles.\n- Instantiated `CrewMember` dataclass arrays validating `Block` chronological sorting natively.",
    "S1b-02": "- Engineered `apply_headcount_target()` inside `src/crewsim/engine/policy.py`.\n- Truncated `line_holders` converting the lowest seniority ranks explicitly to `reserves` to match `roster_size`.\n- Added automated checks within `tests/engine/test_headcount.py` asserting the population size is strictly conserved.",
    "S1b-03": "- Extended `roster_loader.py` to parse reserve cyclic patterns directly from `d2_rosters`.\n- Dynamically assigned `reserve_call_type` (`SC` vs `LC`) adhering to authentic distributions.\n- Built `crewsim roster reserve-pattern` in `cli.py` providing real-time visibility into the availability matrix.",
    "S1b-04": "- Developed `apply_sick_call(cfg, crew_list, timestamp)` inside `src/crewsim/engine/sick_calls.py`.\n- Mutated the targeted `CrewMember` calendar dropping `PAIRING` blocks matching the disruption range.\n- Generated standard `OpenTimeItem` instances signaling unmet demand to the DES engine.",
    "S1b-05": "- Established transition logic (`DUTY_END`, `REST_END`) in `src/crewsim/engine/events.py`.\n- Implemented `assign_reserve()` which bifurcates an existing `RESERVE` block enclosing it around the drafted duty.\n- Wrote `tests/engine/test_events.py` verifying seamless calendar re-entry without overlapping constraints.",
    "S1b-06": "- Parameterized `uncovered_deadline_hours` within `DemandConfig` supporting tiered TTLs per route.\n- Modified `sick_calls.py` to decrement the `OpenTimeItem.deadline` mathematically from the `report` time.\n- Updated `cli.py`'s `explain-event` tracing to verify recursive DES pipeline retries preceding expiration.",
    "S1b-07": "- Wrote analytical `erlang_b(s, a)` function calculating exact mathematical shortfalls within `cli.py`.\n- Established `tests/gates/test_v2_erlang.py` enforcing strict `< 5%` tolerance bounds against the DES mock.\n- Wired `--show-comparison` flag in `gate_parser` outputting the theory versus measured delta side-by-side.",
    "S1b-08": "- Built `ScenarioGenerator` in `src/crewsim/scenarios/generator.py` wrapping the `regimes` and `CRN` engines.\n- Synchronously generated vectors (Z_d) querying the pre-fitted transition matrix via `np.random`.\n- Applied dynamic multipliers shaping `sick_call` densities programmatically tied to the generated array."
}

for fp in glob.glob("backlog/mvp/0[012]*.md"):
    with open(fp, "r") as f:
        content = f.read()

    # We will replace the entire "### How it was implemented\n<anything>" block up to \n\n or \n---
    for sid, impl in detailed_impls.items():
        if sid in content:
            # find block
            pattern = re.compile(rf"(## [^\n]+{sid}.*?### How it was implemented\n)(.*?)(?=\n\n|\n---|\Z)", flags=re.DOTALL)
            match = pattern.search(content)
            if match:
                # Replace group(2) with our detailed bullets
                new_block = match.group(1) + impl
                content = content.replace(match.group(0), new_block)

    with open(fp, "w") as f:
        f.write(content)

print("Detailing complete.")

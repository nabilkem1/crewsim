"""Step-by-step review of the calibration, from the CLI down to the lines that
load the data and compute each distribution.

Command debugged (default):
    crewsim calibrate --season winter_sun --emit

Every stop is ON THE REAL LINE in src/crewsim/..., just BEFORE it runs, with
that function's own variables in the Variables panel. The text after each step
says what is already computed at that point (so you can look at it) and what
the highlighted line is about to do (F10 to run it, F11 to go into it).

Order of the run:
    CLI      C01-C04   cli._run -> config.load -> pipeline.run_pipeline
    LOAD     C05-C09   loaders.load_dataset: file, header check, CSV read, typing
                       (stops on the FIRST load of each dataset only: d8, d4, d2, d1)
    REGIME   C10-C16   regime HMM (F-42)     -> P, pi0, emissions, day labels (no D9)
    SICK     C17-C26   nhpp.fit_sick_calls   -> NB GLM + lognormal durations
    DELAYS   C27-C34   delays.fit_delays     -> P(delayed) per regime + Gaussian mixture
    STORE    C35-C40   diagnostic, content hash, params_v*.json, back in the CLI

Note: this writes the real parameter store in output/params/ (same content
hash as before if the corpus did not change).

See tools/debug/stepper.py for the keys and the environment variables.
"""
from __future__ import annotations

import sys

from stepper import LineStop, run  # tools/debug/ is on sys.path when this script is run

from crewsim import cli, config
from crewsim.calibration import delays, hmm, nhpp, pipeline, regime
from crewsim.data import loaders

_seen_load: set[str] = set()
_seen_cast: set[str] = set()


def _first_load(frame_locals: dict) -> bool:
    """Loader stops: only the first time each dataset is loaded (11 loads, 4 datasets)."""
    return frame_locals.get("name") not in _seen_load


def _mark_loaded(frame_locals: dict) -> bool:
    _seen_load.add(frame_locals.get("name"))
    return True


def _first_cast(frame_locals: dict) -> bool:
    name = frame_locals.get("name")
    if name in _seen_cast:
        return False
    _seen_cast.add(name)
    return True


LOAD_MAX = 4  # d8, d4, d2 (regime HMM) + d1 (bases / sick calls)

STEPS: list[LineStop] = [
    # ---------------------------------------------------------------- CLI
    LineStop("C01", cli._run, 'if args.cmd == "calibrate":',
             "CLI. `args` is parsed: args.season, args.emit, args.window (default 'fitting'). "
             "Next lines refuse --window holdout, then pick the --emit branch."),
    LineStop("C02", config.load, "path = selected_config_path(config_path)",
             "CONFIG. Finds the config file (arg, $CREWSIM_CONFIG, else configs/base.yaml). F10 x3 "
             "then look at `raw` (the YAML) and `cfg` (validated): cfg.windows, cfg.scope, "
             "cfg.calibration, cfg.paths."),
    LineStop("C03", cli._run, "res = pipeline.run_pipeline(cfg, args.season",
             "CLI -> PIPELINE. `cfg` is loaded. F11 goes into run_pipeline."),
    LineStop("C04", pipeline.run_pipeline, "regime_inputs = regime.load_inputs(cfg)",
             "PIPELINE. `fit_window` = (start, end) of the fitting window from configs/base.yaml: "
             "every fitter only sees data inside it (the holdout is never fitted). Next: regime HMM "
             "per crew base x season, then its day labels feed the two other fitters."),

    # ---------------------------------------------------------------- LOADING (any dataset)
    LineStop("C05", loaders.load_dataset, "schema = DATASET_SCHEMAS[name]",
             "LOAD. `name` = which dataset, `path` = the CSV file found in the corpus.",
             max_stops=LOAD_MAX, when=_first_load),
    LineStop("C06", loaders.load_dataset, "_validate_columns(name, columns, schema",
             "LOAD. `columns` = the CSV header, `schema` = the declared columns and types. "
             "Next line refuses banned (personal-data) columns and schema drift.",
             max_stops=LOAD_MAX, when=_first_load),
    LineStop("C07", loaders.load_dataset, "raw = pl.read_csv(",
             "LOAD. Reads the whole CSV as text columns. F10 then `raw.shape`, `raw.head()`.",
             max_stops=LOAD_MAX, when=_first_load),
    LineStop("C08", loaders.load_dataset, "return _cast(name, raw, schema)",
             "LOAD. Converts each column to its declared type (date, int, float...), strictly. "
             "F11 to go into _cast.",
             max_stops=LOAD_MAX, when=lambda loc: _first_load(loc) and _mark_loaded(loc)),
    LineStop("C09", loaders._cast, "return out.select(list(schema))",
             "LOAD. `out` = the typed DataFrame returned to the fitter: out.schema, out.head().",
             max_stops=LOAD_MAX, when=_first_cast),

    # ---------------------------------------------------------------- PHASE 1: REGIME (HMM, F-42)
    LineStop("C10", regime.load_inputs, "d8 = clean.load_flights(cfg)",
             "REGIME INPUTS. No D9 any more (F-42). Next lines load D8 flights (clean.load_flights), "
             "D4 absences (clean.load_absences) and D2 rosters (stops C05-C09 on each) and "
             "aggregate them per station-day."),
    LineStop("C11", regime.load_inputs, "return RegimeInputs(",
             "REGIME INPUTS. `flights` (n_flights, n_delayed >= threshold, n_cancelled), `sick` "
             "(sick_calls) and `exposure` (crew on PAIRING/RESERVE) per station-day."),
    LineStop("C12", regime.build_daily_observations, "gap = (pl.col(",
             "REGIME. `df` = one row per in-season day at this base: the HMM observation vector "
             "(n_flights, n_delayed, n_cancelled, sick_calls, exposure). Missing days are zeros = "
             "uninformative. Next line splits runs of days into sequences (one per season)."),
    LineStop("C13", hmm.fit_best, "best_ll, best = max(results",
             "HMM. `results` = (log-likelihood, model) for each EM restart (restart 0 = quantile "
             "seed, others random). Next line keeps the best one."),
    LineStop("C14", hmm.fit_best, "bic, aic = float(best.bic(X, lengths))",
             "HMM. `best` is ordered CALM..SEVERE: best.transmat_, best.delay_prob_, "
             "best.cancel_prob_, best.sick_rate_. `reached` = restarts that found the same optimum."),
    LineStop("C15", regime.summarise, "out: dict[str, Any] = {",
             "REGIME RESULT. `P` = transition matrix, `stationary` = pi0, `multipliers` = "
             "sick-call rate / NORMAL's, `emissions` = what each state looks like, `share` = "
             "expected share of days per state."),
    LineStop("C16", regime.fit_regime, "receipt = json.dumps(out",
             "REGIME. `out` adds model_selection (BIC for 1..5 states) and holdout (log-lik per "
             "day vs a 1-state model)."),

    # ---------------------------------------------------------------- PHASE 2: SICK CALLS
    LineStop("C17", nhpp.fit_sick_calls, "combos = d1.filter(",
             "SICK CALLS. d1 (crew), d4 (absences) loaded; `d9` = the COMPUTED regime table "
             "(HMM Viterbi labels, F-42), all windowed."),
    LineStop("C18", nhpp.fit_sick_calls, "exposure = grid.join(combos",
             "SICK CALLS. `combos` = active pilot (base, fleet, position) cells; `grid` = every "
             "station-day with season, regime and day_of_week."),
    LineStop("C19", nhpp.fit_sick_calls, "pdf = df.to_pandas()",
             "SICK CALLS. `df` = design matrix: one row per day x base x fleet x position with "
             "the observed `sick_calls` count (0 when none), sorted for determinism."),
    LineStop("C20", nhpp.fit_sick_calls, "model = smf.negativebinomial(formula, data=pdf)",
             "SICK CALLS. `formula` = the GLM: sick_calls ~ season + day_of_week + base + fleet "
             "+ position + regime. `pdf` = the data. Next lines: build and fit the NB model."),
    LineStop("C21", nhpp.fit_sick_calls, 'converged = bool(res.mle_retvals.get("converged"',
             "SICK CALLS. First fit done: res.params, res.mle_retvals, res.summary(). "
             "If not converged, the next lines retry with Nelder-Mead from these params."),
    LineStop("C22", nhpp.fit_sick_calls, "coefs = res.params.to_dict()",
             "SICK CALLS. `res` = the final fit, `converged` = whether it converged."),
    LineStop("C23", nhpp.fit_sick_calls, "d4_dur = d4.filter(",
             "SICK CALLS RESULT. `coefs` (log-scale effects), `alpha`, `dispersion` = 1 + alpha, "
             "`category_levels` (the reference level of each covariate is the first one)."),
    LineStop("C24", nhpp.fit_sick_calls, "shape, _loc, scale = stats.lognorm.fit(durations",
             "ABSENCE DURATION. `durations` = D4 duration_days > 0 (numpy array). "
             "Next line fits a lognormal with loc fixed at 0."),
    LineStop("C25", nhpp.fit_sick_calls, "out_dict = {",
             "ABSENCE DURATION RESULT. `shape` (sigma) and `scale` (= exp(mu)): "
             "median duration = scale days."),
    LineStop("C26", nhpp.fit_sick_calls, 'with open(out_path, "w"',
             "SICK CALLS. `out_dict` is what goes to nhpp_sick_calls.json (`out_path`)."),

    # ---------------------------------------------------------------- PHASE 3: DELAYS
    LineStop("C27", delays.fit_delays, "base = cfg.scope.base",
             "DELAYS. d8 (flights) loaded; `d9` = the computed regime table (HMM labels). Windowed."),
    LineStop("C28", delays.fit_delays, 'regime_flights = df.group_by("regime")',
             "DELAYS. `grid` = regime of each day at the base; `df` = this base+fleet's flights "
             "joined to the regime of their day."),
    LineStop("C29", delays.fit_delays, "delay_by_regime: dict[str, dict[str, float]] = {}",
             "DELAYS. `regime_stats` = per regime: n_flights, n_delayed, n_days."),
    LineStop("C30", delays.fit_delays, "delayed_flights = df.filter(",
             "DELAYS RESULT 1. `delay_by_regime` = P(delayed) and flights/day for each regime."),
    LineStop("C31", delays.fit_delays, "gmm = GaussianMixture(",
             "DELAY DURATION. `durations` = delay minutes of delayed flights (column vector), "
             "`n_components` from config. Next lines fit the Gaussian mixture."),
    LineStop("C32", delays.fit_delays, "weights = gmm.weights_",
             "DELAY DURATION. `gmm` is fitted: gmm.means_, gmm.weights_, gmm.covariances_."),
    LineStop("C33", delays.fit_delays, "out_dict = {",
             "DELAY DURATION RESULT. `components` = (weight, mean_mins, std_dev), short delay first."),
    LineStop("C34", delays.fit_delays, 'with open(out_path, "w"',
             "DELAYS. `out_dict` is what goes to delay_mixture_<season>.json (`out_path`)."),

    # ---------------------------------------------------------------- PHASE 4: STORE
    LineStop("C35", pipeline.run_pipeline, "version = package_version()",
             "PIPELINE. The 3 fits are done: `regime_res`, `nhpp_res`, `delays_res`."),
    LineStop("C36", regime.label_agreement, "joined = mine.join(d9",
             "DIAGNOSTIC (optional). `mine` = HMM labels of the scoped base, `d9` = a supplied "
             "D9 (mock: the generator's true regime). Next lines measure how often they agree."),
    LineStop("C37", pipeline.run_pipeline, 'if not store["sick_call_nhpp"]["converged"]:',
             "STORE. `store` = the full parameter store, before hashing."),
    LineStop("C38", pipeline.content_hash, "receipt_str = json.dumps(content",
             "HASH. `content` = store without run metadata (fitted_at...). Same content -> same hash."),
    LineStop("C39", pipeline.run_pipeline, 'with open(out_path, "w"',
             "STORE. `out_path` = output/params/params_v<ver>_<season>.json; store['content_hash']."),
    LineStop("C40", cli._run, 'print(f"Successfully generated parameter store',
             "CLI. Back in the CLI: `res` = the store returned by run_pipeline."),
]


if __name__ == "__main__":
    sys.exit(run(STEPS, ["calibrate", "--season", "winter_sun", "--emit"]))

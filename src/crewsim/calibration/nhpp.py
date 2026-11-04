"""Sick-call NHPP calibration (S0-07)."""

import hashlib
import json
from typing import Any

import numpy as np
import polars as pl
import statsmodels.formula.api as smf
from scipy import stats

from .. import config
from ..data import clean, coverage, loaders

# The categorical covariates the GLM formula in fit_sick_calls() is fit
# against, in the order that matters only for readability -- predict_intensity
# looks each one up by name, not position.
_CATEGORICAL_COVARIATES = ("season", "day_of_week", "base", "fleet", "position", "regime")


def fit_sick_calls(
    cfg: config.BaseConfig,
    window: tuple[Any, Any] | None = None,
    *,
    regime_days: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Fits the sick-call intensity GLM and absence duration distribution.

    `window` is an optional (start_date, end_date) pair, both inclusive:
    AUD-05 / §6.4 -- when the pipeline says it fit on the fitting window, the
    fit must actually be restricted to it. None fits on the full corpus
    (explicitly, for exploratory use), and the caller owns saying so.

    `regime_days` (F-42) is the computed station-day regime table from
    calibration.regime (station, date, season, disruption_class) -- the HMM's
    Viterbi labels, which replaced D9. The pipeline passes the table it has
    already fitted; when absent it is computed here for the same window.
    """

    # 1. Load Data
    # D1 crew master (who exists where), D4 absences (the sick calls), and the
    # computed regime of every crew-base day; keep only the fitting window.
    d1 = loaders.load_dataset(cfg, "d1_crew_master")
    # IMP-517: a sick call recorded twice is one sick call.
    d4 = clean.load_absences(cfg)
    if regime_days is None:
        from . import regime

        regime_days = regime.label_station_days(cfg, window)
    d9 = regime_days

    if window is not None:
        w_start, w_end = window
        d4 = d4.filter((pl.col("absence_start") >= w_start) & (pl.col("absence_start") <= w_end))
        d9 = d9.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))

    # IMP-516: only days inside the span D4 was recorded over are days that could
    # have a sick call. A day before D4 starts is not a quiet day, it is no day,
    # and counting it as zero is what teaches the GLM that winters are calm.
    d4_span = coverage.dataset_interval(cfg, "d4_absences", df=d4)
    if d4_span is not None:
        # Whatever the label table typed its dates as (Date, or an ISO string).
        day = pl.col("date").cast(pl.String).str.slice(0, 10).str.to_date("%Y-%m-%d")
        d9 = d9.filter((day >= d4_span.start) & (day <= d4_span.end))
    else:
        d9 = d9.clear()

    # 2. Get active pilot combos (base, fleet, position)
    # These are the crew cells a sick call can come from.
    combos = d1.filter(
        (pl.col("crew_group") == "PILOT") & (pl.col("employment_status") == "ACTIVE")
    ).select(["base", "fleet", "position"]).unique()
    
    # 3. Get all days and regimes from the computed regime table
    # One row per station-day with its season and regime: the days that COULD have sick calls.
    grid = d9.select([
        pl.col("season"),
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
        pl.col("station").alias("base"),
        pl.col("disruption_class").alias("regime")
    ])
    
    # Add day of week (Polars dt.weekday(): 1=Mon .. 7=Sun -- the same 1..7
    # convention generator.py's isoweekday() uses at prediction time)
    grid = grid.with_columns(
        pl.col("date").str.to_date("%Y-%m-%d").dt.weekday().cast(pl.String).alias("day_of_week")
    )
    
    # Cross join: every day/base/regime with every valid fleet/position at that base
    exposure = grid.join(combos, on="base", how="inner")
    
    # 4. Count actual sick calls from D4
    # Number of absences starting on each day, per base / fleet / position.
    d4_counts = d4.filter(
        pl.col("absence_start").is_not_null()
    ).with_columns(
        pl.col("absence_start").cast(pl.String).str.slice(0, 10).alias("date")
    ).group_by(["date", "base", "fleet", "position"]).len().rename({"len": "sick_calls"})
    
    # Merge sick calls onto exposure grid (fill nulls with 0)
    # Result = the design matrix: every exposure row with its observed count (0 = quiet day).
    df = exposure.join(
        d4_counts,
        on=["date", "base", "fleet", "position"],
        how="left"
    ).fill_null(0)

    # IMP-201: fix the design-matrix row order. Polars joins and unique() do
    # not guarantee order, and the optimizer's floating-point path depends on
    # it -- unordered rows could move fitted coefficients in the last bits and,
    # with them, the parameter store's content hash.
    df = df.sort(["date", "base", "fleet", "position", "season", "regime", "day_of_week"])

    # Convert to pandas for statsmodels
    pdf = df.to_pandas()
    
    # We want base to be categorical so that YUL isn't treated as a continuous variable, etc.
    # The C() syntax inside the formula does this automatically.
    formula = "sick_calls ~ C(season) + C(day_of_week) + C(base) + C(fleet) + C(position) + C(regime)"
    
    # Fit Negative Binomial Model
    # NB = Poisson with extra variance (overdispersion alpha); log link, so each
    # coefficient is a multiplicative effect exp(beta) on the expected daily count.
    model = smf.negativebinomial(formula, data=pdf)
    res = model.fit(disp=0, maxiter=200)
    # AUD-28e: the default fit emits ConvergenceWarning on this corpus and the
    # store shipped unconverged coefficients with nothing recording it. Retry
    # from the first attempt's params with a derivative-free optimizer; if it
    # still has not converged, persist the fact in the store rather than
    # raising -- a visible flag beats a blocked calibration, and the report
    # surface is where a human decides.
    converged = bool(res.mle_retvals.get("converged", False))
    if not converged:
        res_retry = model.fit(disp=0, method="nm", maxiter=10000, start_params=res.params)
        if bool(res_retry.mle_retvals.get("converged", False)):
            res, converged = res_retry, True

    # Extract the fitted coefficients (log scale) and the dispersion.
    coefs = res.params.to_dict()
    # In statsmodels NB, alpha is the dispersion parameter
    alpha = coefs.get("alpha", 0.0)
    dispersion = 1.0 + alpha

    # The exact per-variable level sets patsy encoded from (`C(var)` drops the
    # alphabetically-first level as the reference), persisted so a later
    # process holding only the serialized `coefs` dict -- no statsmodels
    # results object, no access to `pdf` -- can reconstruct the fit's dummy
    # encoding exactly instead of re-deriving "alphabetically first" from
    # whatever (possibly narrower) covariate slice it happens to be called
    # with. See predict_intensity().
    category_levels = {
        col: sorted(pdf[col].astype(str).unique().tolist()) for col in _CATEGORICAL_COVARIATES
    }

    # 5. Fit Absence Duration (Lognormal)
    # How many days an absence lasts: lognormal with loc fixed at 0 -> (shape=sigma, scale=exp(mu)).
    d4_dur = d4.filter(
        pl.col("duration_days").is_not_null() & (pl.col("duration_days") > 0)
    )
    durations = d4_dur["duration_days"].to_numpy()
    
    shape, _loc, scale = stats.lognorm.fit(durations, floc=0)
    
    # Package the result, add a short content hash, and write nhpp_sick_calls.json.
    out_dict = {
        "coefficients": coefs,
        "dispersion": dispersion,
        "category_levels": category_levels,
        "duration_lognorm_shape": shape,
        "duration_lognorm_scale": scale,
        "converged": converged,
    }
    
    receipt_str = json.dumps(out_dict, sort_keys=True)
    out_dict["content_hash"] = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]
    
    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / "nhpp_sick_calls.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_dict, f, indent=2)
        
    out_dict["_saved_path"] = str(out_path)
    return out_dict


def predict_intensity(
    coefficients: dict[str, float],
    category_levels: dict[str, list[str]],
    covariates: dict[str, str],
) -> float:
    """Evaluate the fitted sick-call NHPP GLM's linear predictor at explicit
    covariate values and return the expected daily count, exp(eta).

    Reconstructs the exact dummy-variable encoding patsy produced when
    fit_sick_calls() ran `smf.negativebinomial("sick_calls ~ C(season) + ...")`:
    for each categorical variable, the alphabetically-first *observed* level is
    the dropped reference (contributes 0 to eta); every other level looks up
    its own `C(<var>)[T.<level>]` coefficient. `category_levels` -- persisted
    by fit_sick_calls() alongside `coefficients` for exactly this purpose --
    is what lets this function reproduce that encoding without re-deriving
    "alphabetically first" from a different, possibly narrower, covariate
    slice at prediction time (e.g. a single-scope scenario generator calling
    this long after fitting, in a different process, holding only the
    serialized JSON). Correctness is checked directly against statsmodels'
    own `res.predict()`, not just asserted, in
    tests/calibration/test_nhpp.py::test_predict_intensity_matches_glm_predict.
    """
    eta = coefficients.get("Intercept", 0.0)
    for var, value in covariates.items():
        levels = category_levels.get(var)
        if not levels:
            raise KeyError(f"No fitted category levels recorded for covariate {var!r}")
        if value == levels[0]:
            continue  # the dropped reference level -- contributes 0 by construction
        if value not in levels:
            raise ValueError(
                f"Covariate {var}={value!r} was never observed while fitting "
                f"(known levels: {levels}) -- refusing to extrapolate silently"
            )
        eta += coefficients.get(f"C({var})[T.{value}]", 0.0)
    return float(np.exp(eta))


def sample_count(rng: np.random.Generator, mean: float, dispersion: float) -> int:
    """Draw one count from the fitted family: Negative Binomial (NB2,
    Var = mean + alpha*mean^2) when genuinely overdispersed, falling back to
    Poisson as alpha -> 0 -- NB2's `n = 1/alpha` diverges numerically as alpha
    approaches 0, and alpha == 0 *is* the Poisson limit of NB2, not a
    different distribution to special-case away from. `dispersion` is
    `1 + alpha`, exactly as fit_sick_calls() computes and stores it.
    """
    if mean <= 0.0:
        return 0
    alpha = dispersion - 1.0
    if alpha <= 1e-8:
        return int(rng.poisson(mean))
    n = 1.0 / alpha
    p = n / (n + mean)
    return int(rng.negative_binomial(n, p))

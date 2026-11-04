"""Severity regime: computed, not supplied (S0-06, rewritten by F-42 Option B).

The daily regime (CALM / NORMAL / DISRUPTED / SEVERE) is a HIDDEN state. It
used to be read from D9's `disruption_class`, a label Air Transat would have to
produce with a rule nobody had specified. It is now inferred from the data the
regime actually causes, with a hidden Markov model fitted per (base, season):

    observed each day at a base     ->  flights delayed / cancelled (D8),
                                        sick calls (D4), crew on duty (D2)
    hidden, inferred by the HMM     ->  the day's regime, the 4x4 transition
                                        matrix P, and what each regime looks
                                        like (delay / cancel probability,
                                        sick-call rate per crew on duty)

One fit therefore yields everything the old pipeline obtained from three
places: the Markov chain scenario generation walks (P, pi0), the per-day
labels the sick-call GLM and the delay model condition on (Viterbi path), and
the state-level intensities. D9 is no longer an input; if a D9 file happens to
be present it is used only as an optional cross-check (`label_agreement`).

See calibration/hmm.py for the model and the choice of hmmlearn.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

from .. import config
from ..data import clean, coverage, loaders
from ..engine import crn
from . import hmm

STATES = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]

#: D2 block types that put a crew member "on duty" at the base that day --
#: the population that can call in sick against a duty (the Poisson exposure).
ON_DUTY_BLOCK_TYPES = coverage.DUTY_BLOCK_TYPES

#: Exposure modes accepted by configs/base.yaml -> calibration.regime_hmm.
EXPOSURE_MODES = ("crew_on_duty", "constant")


# ================================================================ inputs

@dataclass(frozen=True)
class RegimeInputs:
    """Per (station, date) daily aggregates, computed once from D2/D4/D8 and
    shared by every (station, season) fit."""

    flights: pl.DataFrame   # station, date, n_flights, n_delayed, n_cancelled
    sick: pl.DataFrame      # station, date, sick_calls
    exposure: pl.DataFrame  # station, date, exposure
    # IMP-516: the span each stream was RECORDED over. A day outside it is
    # unknown, not a day with no sick calls. None = not computed (no masking);
    # a dict maps "sick" and "exposure" to an Interval, or to None when that
    # dataset holds nothing at all.
    recorded: dict[str, coverage.Interval | None] | None = None


def load_inputs(cfg: config.BaseConfig) -> RegimeInputs:
    """Load D8, D4 (and D2 when exposure is crew_on_duty) and aggregate them
    to one row per station-day. No D9.

    D8 is read as operated flights on the configured flight day (IMP-515,
    IMP-519) and D4 with repeated absences removed (IMP-517).
    """
    settings = cfg.calibration.regime_hmm
    threshold = settings.delay_threshold_minutes

    d8 = clean.load_flights(cfg)
    cancelled = pl.col("cancelled").fill_null(0) == 1
    delay = pl.col("delay_minutes").fill_null(0)
    flights = (
        d8.filter(pl.col("date").is_not_null())
        .group_by([pl.col("origin").alias("station"), pl.col("date")])
        .agg(
            pl.len().alias("n_flights"),
            (~cancelled & (delay >= threshold)).sum().alias("n_delayed"),
            cancelled.sum().alias("n_cancelled"),
        )
    )

    d4 = clean.load_absences(cfg)
    sick = (
        d4.filter(pl.col("absence_start").is_not_null())
        .group_by([pl.col("base").alias("station"), pl.col("absence_start").alias("date")])
        .agg(pl.len().alias("sick_calls"))
    )
    recorded: dict[str, coverage.Interval | None] = {
        "sick": coverage.dataset_interval(cfg, "d4_absences", df=d4),
    }

    if settings.sick_call_exposure == "crew_on_duty":
        d2 = loaders.load_dataset(cfg, "d2_rosters")
        recorded["exposure"] = coverage.dataset_interval(cfg, "d2_rosters", df=d2)
        exposure = (
            d2.filter(
                pl.col("block_type").is_in(list(ON_DUTY_BLOCK_TYPES))
                & pl.col("start_local").is_not_null()
                & pl.col("end_local").is_not_null()
            )
            .select(
                pl.col("base").alias("station"),
                pl.col("crew_id"),
                pl.col("start_local").dt.date().alias("_s"),
                # end is exclusive: a block ending at 00:00 does not cover that day
                (pl.col("end_local") - pl.duration(minutes=1)).dt.date().alias("_e"),
            )
            .filter(pl.col("_e") >= pl.col("_s"))
            .with_columns(pl.date_ranges("_s", "_e").alias("date"))
            .explode("date", empty_as_null=True)  # never empty: _e >= _s filtered above
            .group_by(["station", "date"])
            .agg(pl.col("crew_id").n_unique().cast(pl.Float64).alias("exposure"))
        )
    else:
        exposure = pl.DataFrame(
            schema={"station": pl.String, "date": pl.Date, "exposure": pl.Float64}
        )
    return RegimeInputs(flights=flights, sick=sick, exposure=exposure, recorded=recorded)


def crew_bases(cfg: config.BaseConfig) -> list[str]:
    """Bases that have active pilots (D1) -- the stations the sick-call GLM
    needs a regime for. The scoped base is always included."""
    return clean.active_pilot_bases(loaders.load_dataset(cfg, "d1_crew_master"), cfg.scope.base)


def build_daily_observations(
    cfg: config.BaseConfig,
    inputs: RegimeInputs,
    station: str,
    season: str,
    window: tuple[Any, Any] | None,
) -> pl.DataFrame:
    """One row per in-season calendar day at `station`, in date order.

    The day spine runs over the station's own data span (first..last day with
    any flight or sick-call record), clipped to `window`, keeping only the
    season's months. A missing day stays in the spine with zero counts -- the
    HMM treats it as uninformative and the chain carries on through it.
    Consecutive runs of dates become separate HMM sequences (one per season
    occurrence, e.g. one per winter).
    """
    months = loaders.load_seasons(cfg)[season]
    fl = inputs.flights.filter(pl.col("station") == station)
    sk = inputs.sick.filter(pl.col("station") == station)
    dates = pl.concat([fl.select("date"), sk.select("date")])
    if window is not None:
        dates = dates.filter((pl.col("date") >= window[0]) & (pl.col("date") <= window[1]))
    empty = pl.DataFrame(schema={
        "date": pl.Date, "n_flights": pl.Float64, "n_delayed": pl.Float64,
        "n_cancelled": pl.Float64, "sick_calls": pl.Float64, "exposure": pl.Float64,
        "sequence": pl.Int64,
    })
    if dates.height == 0:
        return empty
    start, end = dates["date"].min(), dates["date"].max()
    spine = pl.DataFrame({"date": pl.date_range(start, end, "1d", eager=True)}).filter(
        pl.col("date").dt.month().is_in(months)
    )
    if spine.height == 0:
        return empty

    exposure_mode = cfg.calibration.regime_hmm.sick_call_exposure
    df = (
        spine.join(fl.drop("station"), on="date", how="left")
        .join(sk.drop("station"), on="date", how="left")
    )
    if exposure_mode == "crew_on_duty":
        ex = inputs.exposure.filter(pl.col("station") == station).drop("station")
        df = df.join(ex, on="date", how="left")
    else:
        df = df.with_columns(pl.lit(1.0).alias("exposure"))
    df = df.with_columns(
        [pl.col(c).fill_null(0).cast(pl.Float64) for c in hmm.OBS_COLUMNS]
    ).sort("date")
    # IMP-516: a day outside the span a stream was recorded over is UNKNOWN for
    # that stream. Zero exposure AND zero count is exactly how the likelihood
    # says "no information" (Poisson(0) puts probability 1 on 0), whereas a
    # zero count against real exposure says "no sick calls today" -- and made
    # a winter that D4 does not cover read as a winter with none.
    if inputs.recorded:
        observed = pl.lit(True)
        for interval in inputs.recorded.values():
            observed = observed & (
                pl.col("date").is_between(interval.start, interval.end) if interval else pl.lit(False)
            )
        df = df.with_columns(
            pl.when(observed).then(pl.col("exposure")).otherwise(0.0).alias("exposure"),
            pl.when(observed).then(pl.col("sick_calls")).otherwise(0.0).alias("sick_calls"),
        )
    # A sick call on a day with no measured exposure cannot be explained by
    # a rate-per-crew model: that day's sick stream is uninformative.
    df = df.with_columns(
        pl.when(pl.col("exposure") > 0).then(pl.col("sick_calls")).otherwise(0.0).alias("sick_calls")
    )
    gap = (pl.col("date").diff().dt.total_days().fill_null(1) > 1).cast(pl.Int64)
    return df.with_columns(gap.cum_sum().alias("sequence")).select(
        ["date", *hmm.OBS_COLUMNS, "sequence"]
    )


def _matrix_and_lengths(obs: pl.DataFrame) -> tuple[np.ndarray, list[int]]:
    X = obs.select(list(hmm.OBS_COLUMNS)).to_numpy().astype(float)
    lengths = obs.group_by("sequence", maintain_order=True).len()["len"].to_list()
    return X, [int(n) for n in lengths]


# ================================================================== fitting

@dataclass
class RegimeFit:
    station: str
    season: str
    model: hmm.DisruptionHMM
    report: dict[str, Any]
    labels: pl.DataFrame          # date, disruption_class, p_<STATE>...
    states: list[str] = field(default_factory=lambda: list(STATES))


def _seed_sequence(cfg: config.BaseConfig, *key: Any) -> np.random.SeedSequence:
    settings = cfg.calibration.regime_hmm
    return np.random.SeedSequence(crn.stable_seed(["regime_hmm", settings.seed, *key]))


def _fit_obs(
    cfg: config.BaseConfig, obs: pl.DataFrame, n_states: int, *seed_key: Any
) -> tuple[hmm.DisruptionHMM, dict[str, Any]]:
    s = cfg.calibration.regime_hmm
    X, lengths = _matrix_and_lengths(obs)
    if n_states == len(STATES):
        q = cfg.calibration.regime_quantiles
        quantile_seed: list[float] = [q.p_calm, q.p_normal, q.p_disrupted]
    else:
        quantile_seed = np.linspace(0, 1, n_states + 1)[1:-1].tolist()
    return hmm.fit_best(
        X, lengths, n_states,
        seed_sequence=_seed_sequence(cfg, *seed_key, n_states),
        n_restarts=s.n_restarts,
        max_iter=s.max_iter,
        tol=s.tol,
        init_self_transition=s.init_self_transition,
        transition_pseudocount=s.transition_pseudocount,
        min_probability=s.min_probability,
        quantile_seed=quantile_seed,
        restart_agreement_tol=s.restart_agreement_tol,
    )


def _decode(model: hmm.DisruptionHMM, obs: pl.DataFrame) -> pl.DataFrame:
    X, lengths = _matrix_and_lengths(obs)
    with hmm.quiet_hmmlearn():
        path = model.predict(X, lengths)
        post = model.predict_proba(X, lengths)
    cols: dict[str, Any] = {
        "date": obs["date"],
        "disruption_class": [STATES[i] for i in path],
    }
    for k, s in enumerate(STATES):
        cols[f"p_{s}"] = post[:, k]
    return pl.DataFrame(cols)


def fit_station_season(
    cfg: config.BaseConfig,
    inputs: RegimeInputs,
    station: str,
    season: str,
    window: tuple[Any, Any] | None,
) -> RegimeFit | None:
    """Fit the 4-state HMM for one (station, season). None when the station
    has too few informative in-season days in the window (IMP-527: fewer than
    `calibration.regime_hmm.min_days`, and never fewer than two)."""
    obs = build_daily_observations(cfg, inputs, station, season, window)
    if obs.height < 2 or informative_days(obs) < cfg.calibration.regime_hmm.min_days:
        return None
    model, report = _fit_obs(cfg, obs, len(STATES), station, season)
    report.update(_stream_report(cfg, model, obs, report))
    return RegimeFit(station, season, model, report, _decode(model, obs))


def informative_days(obs: pl.DataFrame) -> int:
    """Days that tell the HMM something: flights were operated, or crew were
    on duty to call in sick. A spine day with neither is a gap, not a day."""
    return int(obs.filter((pl.col("n_flights") > 0) | (pl.col("exposure") > 0)).height)


def _stream_report(
    cfg: config.BaseConfig, model: hmm.DisruptionHMM, obs: pl.DataFrame, report: dict[str, Any]
) -> dict[str, Any]:
    """IMP-527: which observation streams carried information, and warnings
    for every fitted number that is a floor rather than an estimate.

    A stream with nothing in it still "converges": cancellations that never
    appear give cancel_probability = min_probability in every state, sick
    calls that never appear give sick_rate = min_probability. Those are not
    findings about the airline; they are the absence of a signal, and the
    store must say so rather than carry them as rates.
    """
    s = cfg.calibration.regime_hmm
    n_flights = float(obs["n_flights"].sum())
    streams = {
        "delays": n_flights > 0,
        "cancellations": float(obs["n_cancelled"].sum()) > 0,
        "sick_calls": float(obs["sick_calls"].sum()) > 0 and float(obs["exposure"].sum()) > 0,
    }
    warnings: list[str] = []
    if n_flights == 0:
        warnings.append("no flights in the fitting window: the regime rests on sick calls alone")
    if not streams["cancellations"] and n_flights > 0:
        warnings.append(
            "no cancellations recorded: cancel_probability is the numerical floor "
            f"({s.min_probability:g}), not an estimate -- check the extract encodes cancellations"
        )
    if float(obs["exposure"].sum()) > 0 and not streams["sick_calls"]:
        warnings.append(
            "crew were on duty but no sick calls were recorded: sick_rate is the floor, not an estimate"
        )
    if float(obs["exposure"].sum()) == 0:
        warnings.append("no day has measured exposure: the sick-call stream is unused")
    if streams["sick_calls"] and bool(np.any(model.sick_rate_ <= s.min_probability)):
        warnings.append(
            "at least one regime has a sick-call rate at the numerical floor: it is separated from "
            "the others by the other streams, not by sick calls"
        )
    share = report["restarts_reaching_best"] / report["restarts"]
    if share < s.min_restart_share:
        warnings.append(
            f"only {report['restarts_reaching_best']} of {report['restarts']} EM restarts reached "
            f"the best optimum: the fit is not stable on this much data"
        )
    return {
        "streams_used": [name for name, used in streams.items() if used],
        "informative_days": informative_days(obs),
        "stream_warnings": warnings,
    }


def fit_station_regimes(
    cfg: config.BaseConfig,
    window: tuple[Any, Any] | None,
    *,
    stations: list[str] | None = None,
    seasons: list[str] | None = None,
    inputs: RegimeInputs | None = None,
) -> dict[tuple[str, str], RegimeFit]:
    """One HMM per (station, season). Defaults: every crew base x every season."""
    inputs = inputs or load_inputs(cfg)
    stations = stations or crew_bases(cfg)
    seasons = seasons or list(loaders.load_seasons(cfg))
    fits: dict[tuple[str, str], RegimeFit] = {}
    for station in stations:
        for season in seasons:
            fit = fit_station_season(cfg, inputs, station, season, window)
            if fit is not None:
                fits[(station, season)] = fit
    return fits


def labels_frame(fits: dict[tuple[str, str], RegimeFit]) -> pl.DataFrame:
    """The computed replacement for D9: station, date, season,
    disruption_class (Viterbi path) and the posterior probability of each state."""
    frames = [
        f.labels.with_columns(
            pl.lit(f.station).alias("station"), pl.lit(f.season).alias("season")
        )
        for f in fits.values()
    ]
    if not frames:
        return pl.DataFrame(schema={
            "station": pl.String, "date": pl.Date, "season": pl.String,
            "disruption_class": pl.String, **{f"p_{s}": pl.Float64 for s in STATES},
        })
    return pl.concat(frames).select(
        ["station", "date", "season", "disruption_class", *[f"p_{s}" for s in STATES]]
    ).sort(["station", "date"])


def decode_window(
    cfg: config.BaseConfig,
    fits: dict[tuple[str, str], RegimeFit],
    window: tuple[Any, Any] | None,
    inputs: RegimeInputs | None = None,
) -> pl.DataFrame:
    """Label ANOTHER window (e.g. holdout) with models fitted elsewhere --
    no refit, so the holdout never informs the parameters."""
    inputs = inputs or load_inputs(cfg)
    frames = []
    for (station, season), fit in fits.items():
        obs = build_daily_observations(cfg, inputs, station, season, window)
        if obs.height == 0:
            continue
        frames.append(
            _decode(fit.model, obs).with_columns(
                pl.lit(station).alias("station"), pl.lit(season).alias("season")
            )
        )
    if not frames:
        return labels_frame({})
    return pl.concat(frames).select(
        ["station", "date", "season", "disruption_class", *[f"p_{s}" for s in STATES]]
    ).sort(["station", "date"])


def label_station_days(
    cfg: config.BaseConfig,
    window: tuple[Any, Any] | None,
    *,
    stations: list[str] | None = None,
    seasons: list[str] | None = None,
) -> pl.DataFrame:
    """Fit and label in one call (exploratory / single-fitter CLI use)."""
    return labels_frame(fit_station_regimes(cfg, window, stations=stations, seasons=seasons))


# ================================================================ summaries

def _as_state_dict(values: np.ndarray) -> dict[str, float]:
    return {s: float(v) for s, v in zip(STATES, values, strict=True)}


def _model_selection(
    cfg: config.BaseConfig, obs: pl.DataFrame, station: str, season: str
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in cfg.calibration.regime_hmm.candidate_n_states:
        if k > obs.height:
            continue
        _, rep = _fit_obs(cfg, obs, k, station, season, "model_selection")
        out[str(k)] = {"log_likelihood": rep["log_likelihood"], "bic": rep["bic"], "aic": rep["aic"]}
    if out:
        best = min(out, key=lambda k: out[k]["bic"])
        return {"by_n_states": out, "bic_preferred_n_states": int(best)}
    return {"by_n_states": {}, "bic_preferred_n_states": None}


def _holdout_score(
    cfg: config.BaseConfig,
    fit: RegimeFit,
    fitting_obs: pl.DataFrame,
    holdout_obs: pl.DataFrame,
) -> dict[str, Any]:
    """Out-of-sample log-likelihood per day of the fitted HMM, next to a
    one-state baseline fitted on the same fitting data. If the regime model
    does not beat "no regime at all" on unseen days, it is not earning its
    place -- this number says so."""
    if holdout_obs.height < 2:
        return {"n_days": int(holdout_obs.height), "loglik_per_day": None,
                "loglik_per_day_one_state": None}
    Xh, lh = _matrix_and_lengths(holdout_obs)
    one_state, _ = _fit_obs(cfg, fitting_obs, 1, fit.station, fit.season, "baseline")
    with hmm.quiet_hmmlearn():
        regime_ll = float(fit.model.score(Xh, lh))
        flat_ll = float(one_state.score(Xh, lh))
    return {
        "n_days": int(holdout_obs.height),
        "loglik_per_day": regime_ll / holdout_obs.height,
        "loglik_per_day_one_state": flat_ll / holdout_obs.height,
    }


def summarise(
    cfg: config.BaseConfig,
    fit: RegimeFit,
    *,
    fitting_obs: pl.DataFrame | None = None,
    holdout_obs: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """The parameter-store view of one (station, season) fit."""
    s = cfg.calibration.regime_hmm
    m = fit.model
    P = m.transmat_
    with hmm.quiet_hmmlearn():
        stationary = m.get_stationary_distribution()
    share = fit.labels.select([pl.col(f"p_{st}").mean() for st in STATES]).row(0)
    normal = STATES.index("NORMAL")
    multipliers = m.sick_rate_ / m.sick_rate_[normal]
    emissions = {
        st: {
            "delay_probability": float(m.delay_prob_[k]),
            "cancel_probability": float(m.cancel_prob_[k]),
            "sick_rate_per_exposure": float(m.sick_rate_[k]),
            "expected_share_of_days": float(share[k]),
            "mean_run_days": float(1.0 / (1.0 - P[k, k])) if P[k, k] < 1.0 else None,
        }
        for k, st in enumerate(STATES)
    }
    out: dict[str, Any] = {
        "season": fit.season,
        "station": fit.station,
        "method": "hidden_markov_model",
        "matrix": {a: {b: float(P[i, j]) for j, b in enumerate(STATES)} for i, a in enumerate(STATES)},
        # The stationary distribution of P: what scenario generation starts
        # day 0 from (the store key has always said "steady state").
        "pi0": _as_state_dict(stationary),
        "startprob": _as_state_dict(m.startprob_),
        "multipliers": _as_state_dict(multipliers),
        "emissions": emissions,
        "fit": fit.report,
        "degenerate_states": [st for k, st in enumerate(STATES) if share[k] < s.min_state_share],
        "settings": {
            "exposure": s.sick_call_exposure,
            "delay_threshold_minutes": s.delay_threshold_minutes,
            "n_restarts": s.n_restarts,
            "transition_pseudocount": s.transition_pseudocount,
        },
    }
    if fitting_obs is not None:
        out["model_selection"] = _model_selection(cfg, fitting_obs, fit.station, fit.season)
    if fitting_obs is not None and holdout_obs is not None:
        out["holdout"] = _holdout_score(cfg, fit, fitting_obs, holdout_obs)
    return out


def fit_regime(
    cfg: config.BaseConfig,
    season: str,
    window: tuple[Any, Any] | None = None,
    *,
    fits: dict[tuple[str, str], RegimeFit] | None = None,
    inputs: RegimeInputs | None = None,
    holdout_window: tuple[Any, Any] | None = None,
) -> dict[str, Any]:
    """The scoped base's regime model for `season`: transition matrix, pi0,
    per-state emissions and multipliers, fit report, BIC model selection and
    (if `holdout_window` is given) the out-of-sample score.

    `window` is an optional inclusive (start, end) pair (AUD-05 / §6.4).
    `fits`, when the pipeline already fitted every base, avoids refitting.
    Also writes the per-season regime file named in configs/seasons.yaml.
    """
    seasons_cfg = loaders.load_seasons(cfg)
    if season not in seasons_cfg:
        raise ValueError(f"Unknown season {season}")
    base = cfg.scope.base
    inputs = inputs or load_inputs(cfg)

    fit = (fits or {}).get((base, season)) or fit_station_season(cfg, inputs, base, season, window)
    if fit is None:
        seen = build_daily_observations(cfg, inputs, base, season, window)
        raise ValueError(
            f"Too few in-season days with flight or sick-call data for station={base!r}, "
            f"season={season!r} in the requested window "
            f"({'any' if window is None else f'{window[0]}..{window[1]}'}): "
            f"{informative_days(seen)} informative day(s), "
            f"calibration.regime_hmm.min_days={cfg.calibration.regime_hmm.min_days} -- "
            f"cannot fit a regime model."
        )
    fitting_obs = build_daily_observations(cfg, inputs, base, season, window)
    holdout_obs = (
        build_daily_observations(cfg, inputs, base, season, holdout_window)
        if holdout_window is not None else None
    )
    out = summarise(cfg, fit, fitting_obs=fitting_obs, holdout_obs=holdout_obs)

    receipt = json.dumps(out, sort_keys=True, default=str)
    out["content_hash"] = hashlib.sha256(receipt.encode()).hexdigest()[:8]

    import yaml  # local: only for the regime_model file name lookup

    seasons_path = config.resolve(cfg, "seasons_file")
    with open(seasons_path, encoding="utf-8") as f:
        season_spec = yaml.safe_load(f)["seasons"][season]
    out_path = config.ensure_dir(cfg, "params_dir") / season_spec.get(
        "regime_model", f"regimes_{season}.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    out["_saved_path"] = str(out_path)
    return out


# ============================================================== diagnostics

def label_agreement(
    cfg: config.BaseConfig,
    season: str,
    window: tuple[Any, Any] | None = None,
    *,
    labels: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """OPTIONAL cross-check of the computed labels against a supplied D9.

    D9 is not an input any more. When a D9 file exists (the mock corpus keeps
    the generator's true hidden regime there) this reports how often the HMM's
    Viterbi label for the scoped base matches it -- on the mock, that is the
    model's regime-recovery accuracy. Without D9 it says so and returns no rate.
    """
    base = cfg.scope.base
    # IMP-528: what agreeing with D9 MEANS depends on where D9 came from. The
    # mock's D9 is the generator's hidden truth, so agreement is the model's
    # recovery accuracy. A D9 derived by a rule from D8 (the real extract's)
    # only says how closely the HMM reproduces that rule.
    d9_source = cfg.data.d9_source
    meaning = {
        "generator_truth": "regime recovery accuracy against the generator's true hidden regime",
        "derived_rule": "similarity to D9, a label DERIVED from D8 by a rule -- not an accuracy",
        "unknown": "agreement with D9 of unknown origin -- not an accuracy",
    }[d9_source]
    empty = {"season": season, "station": base, "source": "d9_optional_crosscheck",
             "d9_source": d9_source, "meaning": meaning,
             "n_days": 0, "agreement_rate": None, "confusion": {}}
    if config.dataset_path(cfg, "d9_station_days") is None:
        return {**empty, "note": "D9 not supplied -- nothing to cross-check against"}
    if labels is None:
        labels = label_station_days(cfg, window, stations=[base], seasons=[season])
    mine = labels.filter((pl.col("station") == base) & (pl.col("season") == season)).select(
        pl.col("date"), pl.col("disruption_class").alias("hmm_state")
    )
    d9 = loaders.load_dataset(cfg, "d9_station_days").filter(pl.col("station") == base).select(
        pl.col("date"), pl.col("disruption_class").alias("d9_state")
    ).unique(subset=["date"])
    joined = mine.join(d9, on="date", how="inner")
    n = joined.height
    if n == 0:
        return {**empty, "note": "no overlapping days between computed labels and D9"}
    agree = joined.filter(pl.col("hmm_state") == pl.col("d9_state")).height
    confusion = {
        f"{a}->{b}": c
        for a, b, c in joined.group_by("hmm_state", "d9_state").len().sort(["hmm_state", "d9_state"]).iter_rows()
    }
    return {**empty, "n_days": n, "agreement_rate": agree / n, "confusion": confusion}

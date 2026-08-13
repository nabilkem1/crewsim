"""Severity-regime labelling and Markov fit (S0-06)."""

from typing import Any

import polars as pl
import yaml

from .. import config
from ..data import loaders

STATES = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]

def fit_regime(
    cfg: config.BaseConfig, season: str, window: tuple[Any, Any] | None = None
) -> dict[str, Any]:
    """Fits the 4x4 Markov transition matrix and intensity multipliers.

    `window` is an optional (start_date, end_date) pair, both inclusive
    (AUD-05 / §6.4): the fit must actually be restricted to the window the
    parameter store claims. None fits the full corpus, explicitly.

    AUD-18: the day-state sequence comes from D9's per-station
    `disruption_class` at cfg.scope.base -- the SAME label source the
    sick-call NHPP's C(regime) covariate and the delay model's per-regime
    split are fit against. The previous implementation clustered its own
    network-wide chaos quantiles into states, so generation drew regimes
    from one labelling and fed them into models fit on another; measured
    agreement between the two was 28.8% with a systematic one-class offset.
    One label source ends that. The chaos-quantile labelling survives in
    `label_agreement` below as the cross-check diagnostic, which is also
    what keeps `calibration.regime_quantiles` a consumed config key.
    """
    seasons_path = config.resolve(cfg, "seasons_file")
    with open(seasons_path) as f:
        seasons = yaml.safe_load(f)["seasons"]

    if season not in seasons:
        raise ValueError(f"Unknown season {season}")

    d4 = loaders.load_dataset(cfg, "d4_absences")
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    d9 = loaders.load_dataset(cfg, "d9_station_days")

    if window is not None:
        w_start, w_end = window
        d4 = d4.filter((pl.col("absence_start") >= w_start) & (pl.col("absence_start") <= w_end))
        d8 = d8.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))
        d9 = d9.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))

    base = cfg.scope.base
    df = (
        d9.filter((pl.col("station") == base) & (pl.col("season") == season))
        .select(
            pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
            pl.col("disruption_class").alias("state"),
        )
        .unique(subset=["date"])
        .with_columns(pl.col("date").str.to_date("%Y-%m-%d").alias("date_obj"))
        .sort("date")
    )
    if df.height == 0:
        raise ValueError(
            f"D9 has no station-days for station={base!r}, season={season!r} "
            f"in the requested window -- cannot fit a regime chain."
        )

    # Intensity multipliers: mean daily chaos (base-scoped sick calls +
    # base-origin flight disruptions) per D9 state, relative to NORMAL.
    # Metadata for the store -- generation does not rescale by these (the
    # NHPP carries its own C(regime) coefficient), but they document how
    # much worse a bad day is in this corpus.
    d4_daily = (
        d4.filter(pl.col("base") == base)
        .with_columns(pl.col("absence_start").cast(pl.String).str.slice(0, 10).alias("date"))
        .group_by("date").len().rename({"len": "sick_calls"})
    )
    d8_daily = (
        d8.filter((pl.col("origin") == base) & ((pl.col("delay_minutes") > 0) | (pl.col("cancelled") == 1)))
        .with_columns(pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"))
        .group_by("date").len().rename({"len": "delays"})
    )
    df = (
        df.join(d4_daily, on="date", how="left")
        .join(d8_daily, on="date", how="left")
        .fill_null(0)
        .with_columns((pl.col("sick_calls") + pl.col("delays")).alias("chaos"))
        .sort("date")
    )

    # The chaos quantile cut points are recorded for reference and for the
    # label_agreement diagnostic's use of the same config keys.
    quantiles = cfg.calibration.regime_quantiles
    p50 = df.select(pl.col("chaos").quantile(quantiles.p_calm)).item()
    p80 = df.select(pl.col("chaos").quantile(quantiles.p_normal)).item()
    p95 = df.select(pl.col("chaos").quantile(quantiles.p_disrupted)).item()

    normal_mean = df.filter(pl.col("state") == "NORMAL").select(pl.col("chaos").mean()).item()
    if normal_mean is None or normal_mean == 0:
        normal_mean = 1.0

    multipliers = {}
    for state in STATES:
        state_mean = df.filter(pl.col("state") == state).select(pl.col("chaos").mean()).item()
        if state_mean is None: state_mean = 0.0
        multipliers[state] = state_mean / normal_mean

    df = df.with_columns(
        pl.col("state").shift(-1).alias("next_state"),
        pl.col("date_obj").shift(-1).alias("next_date_obj")
    ).filter(
        pl.col("next_state").is_not_null() &
        ((pl.col("next_date_obj") - pl.col("date_obj")).dt.total_days() == 1)
    )
    
    counts = {s: dict.fromkeys(STATES, 0) for s in STATES}
    totals = dict.fromkeys(STATES, 0)

    for row in df.iter_rows(named=True):
        i = row["state"]
        j = row["next_state"]
        counts[i][j] += 1
        totals[i] += 1

    # Marginal state distribution, computed BEFORE the matrix so it can serve
    # as the back-off row below.
    pi0 = {}
    total_days = df.height
    for s in STATES:
        pi0[s] = df.filter(pl.col("state") == s).height / total_days if total_days > 0 else 0.0

    matrix = {}
    # States with no observed outgoing transition, backed off to the marginal.
    # Recorded rather than silent: a backed-off row is fitted from no data,
    # and a reader of the store must be able to see which rows those are.
    backed_off: list[str] = []
    uniform = 1.0 / len(STATES)
    for s in STATES:
        if totals[s] > 0:
            matrix[s] = {s2: counts[s][s2] / totals[s] for s2 in STATES}
        else:
            # Back off to the marginal, NOT to the identity row this used to
            # emit. An identity row makes the state ABSORBING: any scenario
            # that ever entered it would stay there for the rest of the
            # horizon, driving the NHPP's C(regime) intensity and that
            # regime's delay probability for weeks and inflating E[C]/CVaR95
            # with a pure modelling artifact. The AUD-18 rewrite makes this
            # reachable -- day states now come from ONE station's D9 rows,
            # season- and window-filtered, so a state observed only on the
            # window's final day has no outgoing transition at all. Backing
            # off to the observed marginal is the standard no-data choice and
            # keeps the row a probability distribution; a degenerate corpus
            # with no days at all falls back to uniform for the same reason.
            backed_off.append(s)
            matrix[s] = (
                dict(pi0) if total_days > 0 else dict.fromkeys(STATES, uniform)
            )

    import hashlib
    import json

    out_dict = {
        "season": season,
        "matrix": matrix,
        "multipliers": multipliers,
        "pi0": pi0,
        "transition_rows_backed_off": backed_off,
        "quantiles": {"p50": p50, "p80": p80, "p95": p95}
    }
    receipt_str = json.dumps(out_dict, sort_keys=True)
    content_hash = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]
    out_dict["content_hash"] = content_hash
    
    # Save to the parameter store
    params_dir = config.ensure_dir(cfg, "params_dir")
    model_filename = seasons[season].get("regime_model", f"regimes_{season}.json")
    out_path = params_dir / model_filename
    
    with open(out_path, "w") as f:
        json.dump(out_dict, f, indent=2)
        
    out_dict["_saved_path"] = str(out_path)
    return out_dict


def label_agreement(
    cfg: config.BaseConfig, season: str, window: tuple[Any, Any] | None = None
) -> dict[str, Any]:
    """AUD-18 diagnostic: how well this module's chaos-quantile day labels
    agree with D9's per-station `disruption_class` at cfg.scope.base.

    Two regime definitions coexist by construction: the transition matrix is
    fit on THIS module's network-wide quantile labels, while the NHPP's
    C(regime) covariate and the delay model condition on D9's station-day
    labels. At generation time, states drawn from the former are fed into
    models fit on the latter -- valid only to the extent the two labelings
    agree. This measures that, per season, and the pipeline persists it in
    the store's diagnostics so a divergence is visible instead of assumed
    away.
    """
    seasons_path = config.resolve(cfg, "seasons_file")
    with open(seasons_path) as f:
        months = yaml.safe_load(f)["seasons"][season]["months"]

    d4 = loaders.load_dataset(cfg, "d4_absences")
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    d9 = loaders.load_dataset(cfg, "d9_station_days")
    if window is not None:
        w_start, w_end = window
        d4 = d4.filter((pl.col("absence_start") >= w_start) & (pl.col("absence_start") <= w_end))
        d8 = d8.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))
        d9 = d9.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))

    # Rebuild the same chaos labels fit_regime uses (duplicating the small
    # labelling recipe here keeps fit_regime's public shape untouched).
    d4_daily = d4.with_columns(
        pl.col("absence_start").cast(pl.String).str.slice(0, 10).alias("date")
    ).group_by("date").len().rename({"len": "sick_calls"})
    d8_daily = (
        d8.filter((pl.col("delay_minutes") > 0) | (pl.col("cancelled") == 1))
        .with_columns(pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"))
        .group_by("date").len().rename({"len": "delays"})
    )

    d9_base = d9.filter(
        (pl.col("station") == cfg.scope.base) & (pl.col("season") == season)
    ).select(
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
        pl.col("disruption_class").alias("d9_state"),
    ).unique(subset=["date"])

    # D9's own in-season days are the day spine, LEFT-joined with the event
    # counts -- not a join of the two event tables. A day with zero sick
    # calls AND zero disruptions is a real, quiet day (typically the
    # highest-agreement CALM day there is); building the spine from the
    # events themselves dropped it entirely, which both truncated the
    # quantile sample from below -- shifting every cut point, and so every
    # label, upward -- and excluded exactly the days the two labelings agree
    # on most. This diagnostic is the evidence for the AUD-18 coupling
    # decision, so its denominator has to be the real day set.
    chaos = (
        d9_base.select("date")
        .join(d4_daily, on="date", how="left")
        .join(d8_daily, on="date", how="left")
        .fill_null(0)
        .with_columns((pl.col("sick_calls") + pl.col("delays")).alias("chaos"))
        .with_columns(pl.col("date").str.to_date("%Y-%m-%d").dt.month().alias("month"))
        .filter(pl.col("month").is_in(months))
    )
    if chaos.height == 0:
        return {"season": season, "n_days": 0, "agreement_rate": None, "confusion": {}}

    q = cfg.calibration.regime_quantiles
    p50 = chaos.select(pl.col("chaos").quantile(q.p_calm)).item()
    p80 = chaos.select(pl.col("chaos").quantile(q.p_normal)).item()
    p95 = chaos.select(pl.col("chaos").quantile(q.p_disrupted)).item()
    chaos = chaos.with_columns(
        pl.when(pl.col("chaos") <= p50).then(pl.lit("CALM"))
        .when(pl.col("chaos") <= p80).then(pl.lit("NORMAL"))
        .when(pl.col("chaos") <= p95).then(pl.lit("DISRUPTED"))
        .otherwise(pl.lit("SEVERE"))
        .alias("chaos_state")
    )

    joined = chaos.join(d9_base, on="date", how="inner")
    n = joined.height
    agree = joined.filter(pl.col("chaos_state") == pl.col("d9_state")).height if n else 0
    confusion = {
        f"{row[0]}->{row[1]}": row[2]
        for row in joined.group_by("chaos_state", "d9_state").len().iter_rows()
    }
    return {
        "season": season,
        "n_days": n,
        "agreement_rate": (agree / n) if n else None,
        "confusion": confusion,
    }

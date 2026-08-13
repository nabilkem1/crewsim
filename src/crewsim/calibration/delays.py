import hashlib
import json
from typing import Any

import numpy as np
import polars as pl
from sklearn.mixture import GaussianMixture

from .. import config
from ..data import loaders

STATES = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]


def fit_delays(
    cfg: config.BaseConfig, season: str, window: tuple[Any, Any] | None = None
) -> dict[str, Any]:
    """Fits the per-regime ambient delay probability, per-regime mean
    flights/day, and the pooled short-delay/long-delay duration mixture.

    `window` is an optional (start_date, end_date) pair, both inclusive
    (AUD-05 / §6.4): None fits the full corpus, explicitly.

    Scoped to THIS simulation's own base+fleet (cfg.scope), not network-wide
    across every station D9 covers -- D8 has no crew-position column, so
    base+fleet is as tight as this can be scoped. D8 also carries no
    per-flight crew linkage, so what this measures is the airline's AMBIENT
    delay exposure for that base+fleet (real flights ran late for whatever
    real-world reason), not delay CAUSED by any particular reserve/draft
    decision this simulation makes -- see engine/costs.py::book_flight_delays
    for how that distinction is priced (as its own DELAY_AMBIENT category,
    excluded from the optimised E[C]/CVaR95 the R* recommendation reads).
    """
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    d9 = loaders.load_dataset(cfg, "d9_station_days")

    if window is not None:
        w_start, w_end = window
        d8 = d8.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))
        d9 = d9.filter((pl.col("date") >= w_start) & (pl.col("date") <= w_end))

    base = cfg.scope.base
    fleet = cfg.scope.fleet

    # Regime-labelled days at THIS base only -- d9_station_days is already
    # per-station (S0-06's own regime fit), the same station-level severity
    # label the roster/scenario machinery uses everywhere else.
    grid = d9.filter(
        (pl.col("season") == season) & (pl.col("station") == base)
    ).select([
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
        pl.col("station").alias("origin"),
        pl.col("disruption_class").alias("regime"),
    ])

    # Flights at this base+fleet only, joined onto their regime day.
    df = (
        d8.filter(pl.col("fleet") == fleet)
        .with_columns(pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"))
        .join(grid, on=["date", "origin"], how="inner")
    )

    # 1. Delay probability AND mean flights/day, PER REGIME -- the same
    # C(regime) split the sick-call NHPP already fits. Fit in, not scaled
    # after: generator.py's own comment records the exact bug class from
    # re-applying a regime effect on top of an already regime-conditional fit.
    regime_flights = df.group_by("regime").len().rename({"len": "n_flights"})
    regime_delayed = (
        df.filter(pl.col("delay_minutes") > 0)
        .group_by("regime")
        .len()
        .rename({"len": "n_delayed"})
    )
    regime_days = grid.group_by("regime").agg(pl.col("date").n_unique().alias("n_days"))

    regime_stats = (
        regime_flights.join(regime_delayed, on="regime", how="left")
        .join(regime_days, on="regime", how="left")
    )

    delay_by_regime: dict[str, dict[str, float]] = {}
    for row in regime_stats.iter_rows(named=True):
        n_flights = row["n_flights"] or 0
        n_delayed = row["n_delayed"] or 0
        n_days = row["n_days"] or 0
        delay_by_regime[row["regime"]] = {
            "delay_probability": (n_delayed / n_flights) if n_flights > 0 else 0.0,
            "mean_flights_per_day": (n_flights / n_days) if n_days > 0 else 0.0,
        }
    # Every state must have an entry -- generator.py looks one up per
    # scenario-day unconditionally, and a regime this base+fleet simply never
    # saw in the fitting window is real information (no data, no draw), not
    # an error to paper over with a fabricated fallback.
    for state in STATES:
        delay_by_regime.setdefault(state, {"delay_probability": 0.0, "mean_flights_per_day": 0.0})

    # 2. Duration mixture (using ALL delays in the season, pooled across
    # regimes -- unchanged decision from before this function was scoped by
    # base+fleet: a delay's LENGTH, unlike whether one happens at all, was
    # never claimed to be regime-dependent).
    delayed_flights = df.filter(pl.col("delay_minutes") > 0)
    durations = delayed_flights["delay_minutes"].to_numpy().reshape(-1, 1)

    # Fit the short-delay / long-delay Gaussian Mixture (configs/base.yaml -> calibration)
    n_components = cfg.calibration.delay_gmm_components
    # An unfittable mixture is a real blocker, named as one. The per-regime
    # probabilities above can honestly report zero for a regime this scope
    # never saw, but a DURATION distribution has no honest empty form: the
    # generator draws from it unconditionally, so a fabricated fallback would
    # put invented delay minutes into every scenario. sklearn raises here
    # anyway -- this states WHICH scope and window came up short, and what
    # to change, instead of "Expected n_samples >= n_components".
    if durations.shape[0] < n_components:
        raise ValueError(
            f"delay-duration mixture needs at least {n_components} delayed flights to fit, "
            f"but {base}/{fleet} in season {season!r}"
            + (f" within {window[0]}..{window[1]}" if window is not None else "")
            + f" has {durations.shape[0]}. Widen the fitting window, widen the scope, or "
            f"lower calibration.delay_gmm_components."
        )
    gmm = GaussianMixture(
        n_components=n_components,
        random_state=cfg.calibration.delay_gmm_random_state,
    )
    gmm.fit(durations)

    weights = gmm.weights_
    means = gmm.means_.flatten()
    std_devs = np.sqrt(gmm.covariances_.flatten())

    # Sort components by mean (short delay first, long delay second)
    sort_idx = np.argsort(means)

    components = []
    for i in sort_idx:
        components.append({
            "weight": float(weights[i]),
            "mean_mins": float(means[i]),
            "std_dev": float(std_devs[i])
        })

    out_dict = {
        "season": season,
        # Kept for the calibration UI's existing "P(delayed | NORMAL-regime
        # day)" copy (ResultsInspector.tsx) -- same NORMAL-only meaning as
        # before, just now measured from the base+fleet-scoped population
        # rather than network-wide across every D9 station.
        "base_delay_probability": delay_by_regime["NORMAL"]["delay_probability"],
        "delay_by_regime": delay_by_regime,
        "components": components
    }

    receipt_str = json.dumps(out_dict, sort_keys=True)
    out_dict["content_hash"] = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]

    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / f"delay_mixture_{season}.json"

    with open(out_path, "w") as f:
        json.dump(out_dict, f, indent=2)

    out_dict["_saved_path"] = str(out_path)
    return out_dict


def sample_delay_minutes(rng: np.random.Generator, components: list[dict[str, float]]) -> float:
    """Draws one flight's delay duration from the fitted short-delay/
    long-delay mixture (this module's own `components`, from `fit_delays`).

    Floored at 1.0: the population this was fit on is `delay_minutes > 0` in
    whole minutes, so 1 is the definitional floor of the fitted support --
    not a fabricated minimum. Without the floor, the short-delay component's
    own Gaussian tail can draw a non-positive duration.
    """
    weights = [c["weight"] for c in components]
    idx = rng.choice(len(components), p=weights)
    comp = components[idx]
    draw = rng.normal(comp["mean_mins"], comp["std_dev"])
    return max(1.0, float(draw))

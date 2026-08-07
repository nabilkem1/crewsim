"""S0-02b -- descriptive data profile (spec Sec 5.2, Sec 6.1, Sec 4.4.1b).

Distributions of every quantity Phase 0 is about to fit, computed straight
from the corpus -- before any calibration story (S0-06/S0-07/S0-07b) commits
to a distribution family. The point is to choose families from evidence and
catch a broken extract here, not three stories downstream inside a fitted
parameter nobody re-checks.

Every statistic is computed **separately for the fitting and holdout windows**
declared in `configs/base.yaml -> windows` (Sec 6.4): this is the first story
that needs a window to slice by, so it is also the first to read that key.
S0-09 is the later story that turns the split into a hard refusal; this one
only needs it to slice dates.

Two distribution families are checked against an explicit overlay, because
they are the two the story's own acceptance check implies a family for:
Negative Binomial for sick-call counts/day (overdispersion, var > mean) and
Lognormal for absence duration. The delay-duration Mixture Normal (Sec
2.5.0 step 5) is deliberately NOT fitted here -- that is S0-07b's own story,
with its own acceptance numbers; duplicating a mixture-model fit here would
be scope this story's check block never asked for.
"""
from __future__ import annotations

import datetime
import math
import pathlib
from dataclasses import dataclass, field

import polars as pl

from .. import config
from . import loaders

# Ordinal severity order used everywhere a disruption_class is displayed or
# grouped -- CALM..SEVERE, never alphabetical.
DISRUPTION_ORDER = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]

WINDOW_ORDER = ["fitting", "holdout"]

# The acceptance-criterion bar for "clearly overdispersed" (var/mean, Sec
# 5.2's NegBin-vs-Poisson check) now lives at configs/base.yaml ->
# calibration.overdispersion_threshold (S1a-02, §4.4). It is threaded
# explicitly into `profile_html.render()` and read directly off `cfg` by the
# test that checks the same bar, rather than a bare Python constant the two
# could silently drift apart from.


# ============================================================== windows

@dataclass(frozen=True)
class Window:
    name: str
    start: datetime.date
    end: datetime.date

    @property
    def label(self) -> str:
        return f"{self.name} ({self.start.isoformat()} .. {self.end.isoformat()})"


def load_windows(cfg: config.BaseConfig) -> list[Window]:
    """The Sec 6.4 fitting/holdout split, declared in configs/base.yaml.

    Not invented here: the boundary is a business decision recorded in
    config (flagged [CONFIRM: Crew Planning / Data Science] there), not a
    default this function should silently supply.
    """
    if cfg.windows is None:
        raise KeyError(
            "configs/base.yaml has no `windows` section -- the fitting/holdout "
            "split (Sec 6.4) must be declared before a profile can be run "
            "per-window. See the `windows:` block added for S0-02b."
        )
    return [
        Window(name, cfg.windows.get(name).start, cfg.windows.get(name).end)
        for name in WINDOW_ORDER
    ]


def _in_window(dates: pl.Expr, window: Window) -> pl.Expr:
    return (dates >= window.start) & (dates <= window.end)


# ========================================================== math helpers
# Method-of-moments fits, pure Python -- no scipy/statsmodels dependency for
# a descriptive overlay. The real fits (with covariates, MLE) are S0-06/07's
# job; this is a sanity check, not the calibration.

def negbin_fit(mean: float, var: float) -> tuple[float, float]:
    """sigma^2 = mu + alpha*mu^2 (Sec 2.5.0) -> NegBin(r, p), r = 1/alpha.

    Raises ValueError if var <= mean: that is exactly the "not overdispersed"
    case the caller must handle explicitly, not paper over with a fallback.
    """
    if var <= mean:
        raise ValueError("variance must exceed the mean for a NegBin fit")
    alpha = (var - mean) / mean**2
    r = 1.0 / alpha
    p = r / (r + mean)
    return r, p


def negbin_pmf(k: int, r: float, p: float) -> float:
    log_pmf = (
        math.lgamma(k + r) - math.lgamma(k + 1) - math.lgamma(r)
        + r * math.log(p) + k * math.log(1 - p)
    )
    return math.exp(log_pmf)


def lognormal_fit(values: list[float]) -> tuple[float, float]:
    logs = [math.log(v) for v in values if v > 0]
    mu = sum(logs) / len(logs)
    var = sum((x - mu) ** 2 for x in logs) / len(logs)
    return mu, math.sqrt(var)


def lognormal_pdf(x: float, mu: float, sigma: float) -> float:
    if x <= 0:
        return 0.0
    return (1.0 / (x * sigma * math.sqrt(2 * math.pi))) * math.exp(
        -((math.log(x) - mu) ** 2) / (2 * sigma**2)
    )


def lognormal_cdf(x: float, mu: float, sigma: float) -> float:
    if x <= 0:
        return 0.0
    return 0.5 * (1 + math.erf((math.log(x) - mu) / (sigma * math.sqrt(2))))


# ============================================================= stat blocks

@dataclass
class SickCallStats:
    n_days: int
    mean: float
    var: float
    var_over_mean: float
    by_season: dict[str, float]
    negbin_r: float | None
    negbin_p: float | None
    daily_counts: list[int] = field(repr=False)


@dataclass
class AbsenceDurationStats:
    n: int
    median: float
    mean: float
    max: int
    lognorm_mu: float
    lognorm_sigma: float
    durations: list[float] = field(repr=False)


@dataclass
class ReserveOutcomeStats:
    n: int
    pct: dict[str, float]


@dataclass
class RegimeGradientStats:
    disruption_classes: list[str]
    sick_mean: list[float]
    cancel_rate: list[float]
    delay_mean: list[float]
    n_station_days: list[int]


@dataclass
class SevereRunStats:
    n_runs: int
    mean_length: float
    max_length: int
    run_lengths: list[int] = field(repr=False)


@dataclass
class WindowProfile:
    window: Window
    sick_calls: SickCallStats
    absence_duration: AbsenceDurationStats
    reserve_outcomes: ReserveOutcomeStats
    regime_gradient: RegimeGradientStats
    severe_runs: SevereRunStats


# ========================================================= stat computation

def _daily_counts(dates: pl.Series, window: Window) -> pl.DataFrame:
    """One row per calendar day in [window.start, window.end], zero-filled.

    Zero-filling matters: a day with no sick call is data (a CALM day), not
    an absence of data. Dropping it would understate variance and bias the
    NegBin fit toward looking less overdispersed than the process really is.
    """
    df = pl.DataFrame({"day": dates}).filter(_in_window(pl.col("day"), window))
    counts = df.group_by("day").agg(pl.len().alias("n"))
    all_days = pl.DataFrame({"day": pl.date_range(window.start, window.end, "1d", eager=True)})
    return all_days.join(counts, on="day", how="left").with_columns(pl.col("n").fill_null(0)).sort("day")


def sick_call_stats(d4: pl.DataFrame, window: Window, seasons: dict[str, list[int]]) -> SickCallStats:
    """D4, ALL absence types, by absence_start -- 'sick call' is this model's
    general term for a notified absence event (Sec 6.1: D4 IS the sick-call
    log), not a filter on absence_type == SICK.
    """
    daily = _daily_counts(d4["absence_start"], window)
    n_days = daily.height
    mean = float(daily["n"].mean())  # type: ignore[arg-type]
    var = float(daily["n"].var())  # type: ignore[arg-type]
    var_over_mean = var / mean if mean else float("nan")

    by_month = daily.with_columns(pl.col("day").dt.month().alias("month"))
    by_season = {
        season: float(by_month.filter(pl.col("month").is_in(months))["n"].mean())  # type: ignore[arg-type]
        for season, months in seasons.items()
    }

    r: float | None
    p: float | None
    try:
        r, p = negbin_fit(mean, var)
    except ValueError:
        r, p = None, None

    return SickCallStats(
        n_days=n_days, mean=mean, var=var, var_over_mean=var_over_mean,
        by_season=by_season, negbin_r=r, negbin_p=p,
        daily_counts=daily["n"].to_list(),
    )


def absence_duration_stats(d4: pl.DataFrame, window: Window) -> AbsenceDurationStats:
    sub = d4.filter(_in_window(pl.col("absence_start"), window))
    dur = sub["duration_days"].cast(pl.Float64)
    values = dur.to_list()
    mu, sigma = lognormal_fit(values)
    return AbsenceDurationStats(
        n=dur.len(), median=float(dur.median()), mean=float(dur.mean()),  # type: ignore[arg-type]
        max=int(max(values)),
        lognorm_mu=mu, lognorm_sigma=sigma, durations=values,
    )


def reserve_outcome_stats(d5: pl.DataFrame, window: Window) -> ReserveOutcomeStats:
    sub = d5.filter(_in_window(pl.col("call_ts").dt.date(), window))
    n = sub.height
    counts = sub.group_by("outcome").agg(pl.len().alias("n"))
    pct = {row["outcome"]: row["n"] / n for row in counts.iter_rows(named=True)} if n else {}
    return ReserveOutcomeStats(n=n, pct=pct)


def regime_gradient_stats(
    d9: pl.DataFrame, d4: pl.DataFrame, d8: pl.DataFrame, window: Window
) -> RegimeGradientStats:
    """Sick-call rate, cancellation rate, and mean delay, per disruption_class.

    The whole point of Sec 5.2's severity regime is that these three streams
    move TOGETHER -- that is what this function exists to show, not derive.
    """
    d9w = d9.filter(_in_window(pl.col("date"), window))

    sick_sd = (
        d4.filter(_in_window(pl.col("absence_start"), window))
        .group_by([pl.col("base").alias("station"), pl.col("absence_start").alias("date")])
        .agg(pl.len().alias("sick_n"))
    )
    sick_joined = (
        d9w.select(["station", "date", "disruption_class"])
        .join(sick_sd, on=["station", "date"], how="left")
        .with_columns(pl.col("sick_n").fill_null(0))
    )
    sick_by_class = sick_joined.group_by("disruption_class").agg(
        pl.col("sick_n").mean().alias("sick_mean"),
        pl.len().alias("n_station_days"),
    )

    mv = (
        d8.filter(_in_window(pl.col("date"), window))
        .group_by([pl.col("origin").alias("station"), pl.col("date")])
        .agg(
            pl.len().alias("n_movements"),
            pl.col("cancelled").sum().alias("n_cancelled"),
            pl.col("delay_minutes").sum().alias("sum_delay"),
        )
    )
    # inner join: a station-day with no movement at all contributes nothing to
    # a rate that is only meaningful where there was flying to disrupt.
    mv_joined = d9w.select(["station", "date", "disruption_class"]).join(
        mv, on=["station", "date"], how="inner"
    )
    mv_by_class = mv_joined.group_by("disruption_class").agg(
        (pl.col("n_cancelled").sum() / pl.col("n_movements").sum()).alias("cancel_rate"),
        (pl.col("sum_delay").sum() / pl.col("n_movements").sum()).alias("delay_mean"),
    )

    merged = sick_by_class.join(mv_by_class, on="disruption_class", how="left")
    by_class = {row["disruption_class"]: row for row in merged.iter_rows(named=True)}
    classes = [c for c in DISRUPTION_ORDER if c in by_class]

    return RegimeGradientStats(
        disruption_classes=classes,
        sick_mean=[by_class[c]["sick_mean"] for c in classes],
        cancel_rate=[by_class[c]["cancel_rate"] for c in classes],
        delay_mean=[by_class[c]["delay_mean"] for c in classes],
        n_station_days=[by_class[c]["n_station_days"] for c in classes],
    )


def severe_run_stats(d9: pl.DataFrame, window: Window) -> SevereRunStats:
    """Consecutive-SEVERE-day run lengths, per station.

    This is the direct evidence for Sec 5.2's claim that the regime produces
    bad WEEKS, not scattered bad days: a mean run length near 1 would mean
    SEVERE days are isolated, which is exactly what the Markov chain's
    self-transition is designed to avoid.
    """
    d9w = d9.filter(_in_window(pl.col("date"), window))
    runs: list[int] = []
    for _station, sub in d9w.sort("date").group_by("station"):
        run_len = 0
        for is_severe in (sub.sort("date")["disruption_class"] == "SEVERE").to_list():
            if is_severe:
                run_len += 1
            else:
                if run_len > 0:
                    runs.append(run_len)
                run_len = 0
        if run_len > 0:
            runs.append(run_len)

    if not runs:
        return SevereRunStats(n_runs=0, mean_length=float("nan"), max_length=0, run_lengths=[])
    return SevereRunStats(
        n_runs=len(runs), mean_length=sum(runs) / len(runs), max_length=max(runs), run_lengths=runs,
    )


def compute_window_profile(
    window: Window,
    seasons: dict[str, list[int]],
    d4: pl.DataFrame,
    d5: pl.DataFrame,
    d8: pl.DataFrame,
    d9: pl.DataFrame,
) -> WindowProfile:
    return WindowProfile(
        window=window,
        sick_calls=sick_call_stats(d4, window, seasons),
        absence_duration=absence_duration_stats(d4, window),
        reserve_outcomes=reserve_outcome_stats(d5, window),
        regime_gradient=regime_gradient_stats(d9, d4, d8, window),
        severe_runs=severe_run_stats(d9, window),
    )


def compute_profiles(cfg: config.BaseConfig) -> dict[str, WindowProfile]:
    """One WindowProfile per declared window (Sec 6.4), each dataset loaded once."""
    seasons = loaders.load_seasons(cfg)
    windows = load_windows(cfg)
    d4 = loaders.load_dataset(cfg, "d4_absences")
    d5 = loaders.load_dataset(cfg, "d5_reserve_callouts")
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    d9 = loaders.load_dataset(cfg, "d9_station_days")
    return {w.name: compute_window_profile(w, seasons, d4, d5, d8, d9) for w in windows}


def write_report(cfg: config.BaseConfig) -> pathlib.Path:
    from . import profile_html

    profiles = compute_profiles(cfg)
    html = profile_html.render(profiles, cfg.calibration.overdispersion_threshold)
    out_dir = config.ensure_dir(cfg, "reports_dir")
    path = out_dir / "data_profile.html"
    path.write_text(html)
    return path

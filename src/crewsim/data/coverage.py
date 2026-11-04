"""Each dataset's valid time interval (IMP-516).

A real extract's datasets do not cover the same days: D4 may start months after
D2 does, D2 may stop being filled in mid-June, D8 may run on as a schedule
after the last real movement. A day OUTSIDE a dataset's interval is not a day
with zero events -- it is a day nobody recorded. Treating it as zero is how a
fit reports "no sick calls all winter" or "3.5 sick calls per crew-day".

The interval of a dataset is where its smoothed daily row count stays at or
above `data.coverage.min_share` of its busy level. It is detected, not assumed,
and `data.coverage.explicit` overrides it once the data owner states the real
extraction period. The mock corpus spans the same period in every dataset, so
its intervals are its whole span.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import polars as pl

from .. import config
from . import clean, loaders

#: D2 block types that put a crew member on duty at a base on a given day.
#: The days a roster is "filled in" are judged on these, not on days off.
DUTY_BLOCK_TYPES = ("PAIRING", "RESERVE")


class CoverageError(ValueError):
    """A window the data cannot support, named with the intervals that are."""


@dataclass(frozen=True)
class Interval:
    dataset: str
    start: datetime.date
    end: datetime.date
    #: Days inside [start, end] whose smoothed volume is below the threshold.
    gap_days: int
    #: Rows the dataset has per covered day, typically (the busy level).
    busy_level: float

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, day: datetime.date) -> bool:
        return self.start <= day <= self.end

    def label(self) -> str:
        return f"{self.start}..{self.end}"


def detect_interval(
    dataset: str, dates: pl.Series, *, min_share: float, reference_quantile: float, smooth_days: int
) -> Interval | None:
    """The span where `dates` (one entry per row) is recorded at a normal rate.

    None for an empty series. A series whose volume is one steady level (every
    mock dataset) returns its first..last day.
    """
    dates = dates.drop_nulls()
    if dates.len() == 0:
        return None
    first, last = dates.min(), dates.max()
    spine = pl.DataFrame({"date": pl.date_range(first, last, "1d", eager=True)})  # type: ignore[arg-type]
    counts = dates.to_frame("date").group_by("date").len().rename({"len": "n"})
    daily = (
        spine.join(counts, on="date", how="left")
        .with_columns(pl.col("n").fill_null(0).cast(pl.Float64))
        .sort("date")
        .with_columns(
            pl.col("n").rolling_mean(window_size=smooth_days, center=True, min_samples=1).alias("s")
        )
    )
    positive = daily.filter(pl.col("s") > 0)["s"]
    if positive.len() == 0:
        return None
    busy = float(positive.quantile(reference_quantile, "linear"))  # type: ignore[arg-type]
    covered = daily.filter(pl.col("s") >= min_share * busy)
    if covered.height == 0:
        return None
    start, end = covered["date"].min(), covered["date"].max()
    inside = daily.filter((pl.col("date") >= start) & (pl.col("date") <= end))
    gap_days = inside.filter(pl.col("s") < min_share * busy).height
    return Interval(dataset, start, end, gap_days, busy)  # type: ignore[arg-type]


def _dates_d2(df: pl.DataFrame) -> pl.Series:
    return df.filter(
        pl.col("block_type").is_in(list(DUTY_BLOCK_TYPES)) & pl.col("start_local").is_not_null()
    )["start_local"].dt.date()


def _date_extractors(cfg: config.BaseConfig) -> dict[str, Callable[[pl.DataFrame], pl.Series]]:
    return {
        "d2_rosters": _dates_d2,
        "d3_pairings": lambda df: df["start_date"],
        "d4_absences": lambda df: clean.dedupe_absences(df)["absence_start"],
        "d5_reserve_callouts": lambda df: df["call_ts"].dt.date(),
        "d6_schedule_changes": lambda df: df["change_ts"].dt.date(),
        "d7_pay_register": lambda df: df["duty_date"],
        "d8_flight_movements": lambda df: clean.operated_flights(cfg, df)["date"],
        "d10_positioning_invoices": lambda df: df["date"],
    }


#: Datasets an interval can be computed for.
DATASETS: tuple[str, ...] = (
    "d2_rosters", "d3_pairings", "d4_absences", "d5_reserve_callouts", "d6_schedule_changes",
    "d7_pay_register", "d8_flight_movements", "d10_positioning_invoices",
)

# A detected interval is expensive (it reads the dataset) and select_template_window
# asks for one on every roster load, so it is kept per file version. A loader that
# has been replaced (a test hand-feeding frames) is never cached: its answer is
# not a function of the file.
_CACHE: dict[tuple[Any, ...], Interval | None] = {}


def _cache_key(cfg: config.BaseConfig, name: str) -> tuple[Any, ...] | None:
    if loaders.load_dataset.__module__ != loaders.__name__:
        return None
    path = config.dataset_path(cfg, name)
    if path is None:
        return None
    stat = path.stat()
    c = cfg.data
    return (str(path), stat.st_mtime_ns, stat.st_size, c.flight_day, c.cutoff, c.require_actuals,
            c.coverage.min_share, c.coverage.reference_quantile, c.coverage.smooth_days)


def dataset_interval(
    cfg: config.BaseConfig, name: str, df: pl.DataFrame | None = None
) -> Interval | None:
    """The valid interval of dataset `name` (None if it is empty or absent).

    `data.coverage.explicit` wins over detection. `df` may be passed already
    loaded, which also bypasses the cache.
    """
    explicit = cfg.data.coverage.explicit or {}
    if name in explicit:
        w = explicit[name]
        return Interval(name, w.start, w.end, 0, 0.0)
    extractor = _date_extractors(cfg).get(name)
    if extractor is None:
        raise KeyError(f"no interval rule for dataset {name!r}; known: {list(DATASETS)}")

    key = _cache_key(cfg, name) if df is None else None
    if key is not None and key in _CACHE:
        return _CACHE[key]
    try:
        frame = df if df is not None else loaders.load_dataset(cfg, name)
    except FileNotFoundError:
        return None
    c = cfg.data.coverage
    interval = detect_interval(
        name, extractor(frame), min_share=c.min_share,
        reference_quantile=c.reference_quantile, smooth_days=c.smooth_days,
    )
    if key is not None:
        _CACHE[key] = interval
    return interval


def all_intervals(cfg: config.BaseConfig) -> dict[str, Interval | None]:
    """Every dataset's interval, in a stable order."""
    return {name: dataset_interval(cfg, name) for name in DATASETS}


def intersect(*intervals: Interval | None) -> tuple[datetime.date, datetime.date] | None:
    """The span every given interval shares, or None if they share none.
    An absent dataset (None) is ignored: it constrains nothing it cannot see."""
    present = [i for i in intervals if i is not None]
    if not present:
        return None
    start = max(i.start for i in present)
    end = min(i.end for i in present)
    return (start, end) if start <= end else None


def describe(intervals: dict[str, Interval | None]) -> str:
    """One line per dataset, for an error message or a report."""
    return "; ".join(
        f"{name}: {i.label() if i else 'no data'}" for name, i in intervals.items()
    )


def require_window_supported(
    cfg: config.BaseConfig, window: tuple[datetime.date, datetime.date], *,
    datasets: tuple[str, ...], what: str,
) -> None:
    """Refuse a window that none of the named datasets' intervals overlaps.

    A fit over days nobody recorded does not fail -- it quietly fits zeros.
    That is what this stops, naming the intervals that ARE supported.
    """
    found = {n: dataset_interval(cfg, n) for n in datasets}
    overlapping = {
        n: i for n, i in found.items()
        if i is not None and i.start <= window[1] and i.end >= window[0]
    }
    if len(overlapping) < len(found):
        missing = sorted(set(found) - set(overlapping))
        raise CoverageError(
            f"{what} window {window[0]}..{window[1]} has no recorded data in "
            f"{', '.join(missing)}. Data covers: {describe(found)}. "
            f"Move the window (configs: windows.*) or set data.coverage.explicit."
        )

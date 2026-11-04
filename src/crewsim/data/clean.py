"""Cleaning rules every consumer of D4 and D8 shares (IMP-515, IMP-517, IMP-519).

A real extract differs from the generated mock in ways the fitters must not
read as signal:

* D4 carries the same absence more than once (a real extract held up to 36
  identical rows), so counting rows counts the extraction, not the sick calls.
* D8 carries SCHEDULED-ONLY flights after the extraction cut-off: no actual
  times, `delay_minutes = 0`, `cancelled = 0`. Read as data they are a run of
  perfectly on-time flights -- a calm month that never happened.
* D8 `date` is not always the local departure date, while D2 and D4 use local
  dates, so one day would mean two things in one fit.

Every rule is a no-op on the mock corpus (no duplicates, every non-cancelled
flight has actual times, `date` is the local date), so the mock reads as before.
Each function also tolerates a frame that lacks the columns it would use,
because several callers hand it small purpose-built frames.
"""
from __future__ import annotations

from typing import Any

import polars as pl

from .. import config
from . import loaders

#: What makes two D4 rows the same absence. `absence_id` and `notification_ts`
#: are left out: an extraction that repeats a row can stamp each copy with
#: its own id or time.
ABSENCE_KEY = ("crew_id", "absence_start", "absence_end", "absence_type", "affected_pairing_id")

#: What makes two D8 rows the same flight.
FLIGHT_KEY = ("flight_no", "date", "origin", "destination")


def dedupe_absences(d4: pl.DataFrame) -> pl.DataFrame:
    """D4 with repeated absences removed (first occurrence kept, order kept).

    Only applied when the frame identifies a crew member's absence at all --
    without `crew_id` and `absence_start`, identical rows are legitimately
    distinct events (a hand-built frame of "three calls at YUL on one day").
    """
    if "crew_id" not in d4.columns or "absence_start" not in d4.columns:
        return d4
    key = [c for c in ABSENCE_KEY if c in d4.columns]
    return d4.unique(subset=key, keep="first", maintain_order=True)


def load_absences(cfg: config.BaseConfig) -> pl.DataFrame:
    """D4 de-duplicated: the one place sick-call counts should start from."""
    return dedupe_absences(loaders.load_dataset(cfg, "d4_absences"))


def apply_flight_day(cfg: config.BaseConfig, d8: pl.DataFrame) -> pl.DataFrame:
    """D8 with `date` set to the configured operating day (IMP-519).

    `data.flight_day = sched_dep_local` replaces `date` with the local calendar
    day of the scheduled departure; `date` leaves the column as supplied.
    """
    if cfg.data.flight_day == "sched_dep_local" and "sched_dep_local" in d8.columns:
        return d8.with_columns(pl.col("sched_dep_local").dt.date().alias("date"))
    return d8


def operated_flights_report(
    cfg: config.BaseConfig, d8: pl.DataFrame
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """D8 reduced to flights that happened or were cancelled, one row per flight
    (IMP-515), with a report of what was dropped and why.

    * scheduled-only: not cancelled and no actual departure (`require_actuals`)
    * after the cut-off: `data.cutoff`, else the last day with an actual departure
    * self-loops: origin equals destination (only when `data.drop_self_loop_flights`)
    * repeated: the same flight, day, origin and destination more than once
    """
    settings = cfg.data
    out = apply_flight_day(cfg, d8)
    report: dict[str, Any] = {
        "rows_in": d8.height, "scheduled_only": 0, "after_cutoff": 0, "duplicates": 0,
        "self_loops": 0, "cutoff": None, "flight_day": settings.flight_day,
    }
    if settings.drop_self_loop_flights and {"origin", "destination"} <= set(out.columns):
        # Before the duplicate rule: a self-loop is not a repeat of the real flight,
        # and `unique(keep="first")` must not be free to keep it instead.
        before = out.height
        out = out.filter(pl.col("origin") != pl.col("destination"))
        report["self_loops"] = before - out.height
    has_actual = "actual_dep_local" in out.columns and "cancelled" in out.columns

    if settings.require_actuals and has_actual:
        before = out.height
        cancelled = pl.col("cancelled").fill_null(0) == 1
        out = out.filter(cancelled | pl.col("actual_dep_local").is_not_null())
        report["scheduled_only"] = before - out.height

    if "date" in out.columns:
        cutoff = settings.cutoff
        if cutoff is None and has_actual and out["actual_dep_local"].null_count() < out.height:
            # Auto-detected, and only the days AFTER it go: a corpus that simply
            # ends (the mock) loses nothing.
            cutoff = out["actual_dep_local"].max().date()  # type: ignore[union-attr]
        if cutoff is not None:
            before = out.height
            out = out.filter(pl.col("date") <= cutoff)
            report["after_cutoff"] = before - out.height
            report["cutoff"] = cutoff.isoformat()

    key = [c for c in FLIGHT_KEY if c in out.columns]
    if len(key) == len(FLIGHT_KEY):
        before = out.height
        out = out.unique(subset=key, keep="first", maintain_order=True)
        report["duplicates"] = before - out.height

    report["rows_out"] = out.height
    return out, report


def operated_flights(cfg: config.BaseConfig, d8: pl.DataFrame) -> pl.DataFrame:
    """`operated_flights_report`, frame only."""
    return operated_flights_report(cfg, d8)[0]


def load_flights(cfg: config.BaseConfig) -> pl.DataFrame:
    """D8 as every fitter should read it: operated flights, on the configured day."""
    return operated_flights(cfg, loaders.load_dataset(cfg, "d8_flight_movements"))


def active_pilot_bases(d1: pl.DataFrame, scope_base: str) -> list[str]:
    """Bases that have ACTIVE pilots, plus the scoped base (IMP-513).

    The bases a station-day gate or the regime fit should look at. A base that
    only terminated pilots ever belonged to is a station nobody crews today;
    counting it fails a coverage gate for days nothing could have happened.
    """
    bases = set(
        d1.filter(
            (pl.col("crew_group") == "PILOT") & (pl.col("employment_status") == "ACTIVE")
        )["base"].to_list()
    )
    bases.add(scope_base)
    return sorted(b for b in bases if b)

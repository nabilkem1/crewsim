"""replay -- S1e-06 (gate V5) / S1e-07 (gate V6): prepare REAL historical D4
absences and a real, calendar-anchored roster for an arbitrary date range,
then hand off to des.run_historical_replay for the actual recovery-pipeline
run.

No simpy import here (S0-00b: only des.py may) -- this module's job is data
preparation only: which period has the most real disruption (or which
calendar month, for V6), and which real D4 rows fall inside it, converted to
the engine's minutes-since-window-start convention. des.run_scenario/
run_policy_crn draw sick-call arrivals from the calibrated NHPP scenario
cache (_load_daily_sick_calls), keyed by (master_seed, scenario_id), never
by a real calendar date. Historical replay needs the opposite -- the exact
real absences that happened on exact real dates, for exactly one specific
crew member each, not a random draw from a distribution.
"""
from __future__ import annotations

import copy
import datetime
from collections import Counter
from typing import Any

import polars as pl

from .. import config
from ..data import loaders
from .des import Simulation
from .des import run_historical_replay as _run_historical_replay
from .policy import Policy
from .roster_loader import load_rosters


def _scope_filter(df: pl.DataFrame, cfg: config.BaseConfig) -> pl.DataFrame:
    return df.filter(
        (pl.col("base") == cfg.scope.base)
        & (pl.col("fleet") == cfg.scope.fleet)
        & (pl.col("position") == cfg.scope.position)
    )


def find_peak_disruption_week(cfg: config.BaseConfig) -> datetime.date:
    """The Monday-starting week, within D4's real corpus dates restricted to
    cfg.scope, with the most real absences.

    Stand-in for spec Sec9.2's "real, memorable disruption week": the corpus
    is entirely mock (tools/generate_mock_corpus.py), so there is no real
    Air Transat history to pick from. User-confirmed disposition (S1e-06's
    backlog note): use the mock corpus's own highest-disruption week,
    labelled as such wherever it's shown -- never presented as real history.
    """
    d4 = _scope_filter(loaders.load_dataset(cfg, "d4_absences"), cfg)
    counts: Counter[datetime.date] = Counter()
    for row in d4.iter_rows(named=True):
        day: datetime.date = row["absence_start"]
        monday = day - datetime.timedelta(days=day.weekday())
        counts[monday] += 1
    if not counts:
        raise ValueError(
            f"no D4 absences found for scope {cfg.scope.base}/{cfg.scope.fleet}/{cfg.scope.position}"
        )
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _load_real_absences(
    cfg: config.BaseConfig, period_start: datetime.date, period_end: datetime.date
) -> list[dict[str, Any]]:
    """Real D4 rows whose absence_start falls in [period_start, period_end),
    restricted to cfg.scope, converted to minutes since period_start.

    notification_ts (when the absence was reported) drives WHEN the
    OpenTimeItem is created and the recovery pipeline starts -- the real
    moment the disruption becomes known -- while [absence_start, absence_end)
    is the real window searched for pairings the absence breaks. These are
    two different real timestamps D4 already carries; the synthetic
    scenario generator conflates them into one draw, but real data doesn't
    have to.
    """
    d4 = _scope_filter(loaders.load_dataset(cfg, "d4_absences"), cfg).filter(
        (pl.col("absence_start") >= period_start) & (pl.col("absence_start") < period_end)
    ).sort("notification_ts")

    anchor = datetime.datetime.combine(period_start, datetime.time.min)
    out = []
    for row in d4.iter_rows(named=True):
        notified_min = (row["notification_ts"] - anchor).total_seconds() / 60.0
        start_min = (datetime.datetime.combine(row["absence_start"], datetime.time.min) - anchor).total_seconds() / 60.0
        end_min = (datetime.datetime.combine(row["absence_end"], datetime.time.min) - anchor).total_seconds() / 60.0
        out.append({
            "absence_id": row["absence_id"],
            "crew_id": row["crew_id"],
            "absence_type": row["absence_type"],
            # Clamp to 0: a notice given the evening before a period boundary
            # still needs to surface at sim start, not at a negative time
            # simpy can't schedule.
            "notified_min": max(notified_min, 0.0),
            "start_min": start_min,
            "end_min": end_min,
        })
    return out


def run_historical_period(
    cfg: config.BaseConfig, costs: Any, policy: Policy, period_start: datetime.date, period_end: datetime.date,
    trace: bool = True, verbose_trace: bool = True,
) -> Simulation:
    """Replay every real D4 absence in [period_start, period_end) for
    cfg.scope, through the real recovery pipeline -- an arbitrary date
    range, not fixed to 7 days: S1e-07 (V6) uses this directly with one
    full real calendar month, aligned to D7's pay_period granularity."""
    active, _ = load_rosters(
        cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position,
        policy=policy, window=(period_start, period_end),
    )
    active = copy.deepcopy(active)
    roster = [c for c in active if not getattr(c, "_is_reserve", False)]
    reserves = [c for c in active if getattr(c, "_is_reserve", False)]

    absences = _load_real_absences(cfg, period_start, period_end)
    horizon_minutes = (period_end - period_start).days * 1440.0
    return _run_historical_replay(
        cfg, costs, policy, roster, reserves, absences, horizon_minutes, trace=trace, verbose_trace=verbose_trace,
    )


def run_historical_week(
    cfg: config.BaseConfig, costs: Any, policy: Policy, week_start: datetime.date
) -> Simulation:
    """S1e-06 (V5): the one-week case of run_historical_period, always
    trace=True/verbose_trace=True (an SME walkthrough always wants the full
    alternative-set logging)."""
    week_end = week_start + datetime.timedelta(days=7)
    return run_historical_period(cfg, costs, policy, week_start, week_end)

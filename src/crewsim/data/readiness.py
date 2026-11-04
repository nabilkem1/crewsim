"""`crewsim data readiness`: can this extract be calibrated and simulated? (IMP-529)

One answer instead of five commands that each fail differently. It gathers, for
the configured corpus and configuration:

* the span each dataset is actually recorded over (IMP-516);
* whether the configured fitting and holdout windows overlap that data;
* whether a template window for the roster exists (the simulation needs one);
* how many active pilots the configured scope really holds;
* every quality gate (Sec 6.2 and the defect gates), with its verdict.

It exits non-zero unless every one of those holds, and says which one did not.
Reading is cheap and nothing is written.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import polars as pl

from .. import config
from . import clean, coverage, limitations, loaders, quality


@dataclass
class WindowStatus:
    name: str
    window: tuple[datetime.date, datetime.date]
    #: dataset -> does its recorded span overlap the window
    overlaps: dict[str, bool]

    @property
    def supported(self) -> bool:
        return all(self.overlaps.values())


@dataclass
class Readiness:
    banner: str
    intervals: dict[str, coverage.Interval | None]
    shared_span: tuple[datetime.date, datetime.date] | None
    windows: list[WindowStatus]
    template: tuple[bool, str]
    scope_crew: int
    scope_label: str
    checks: list[quality.QualityCheckResult]
    problems: list[str] = field(default_factory=list)
    #: What the extract could not support / what was assumed to read it.
    limitations: list[limitations.Limitation] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.problems


#: The datasets each window's fit reads. D2 is not listed: without it the
#: sick-call stream is simply uninformative (IMP-516), it does not block a fit.
_FIT_DATASETS = ("d8_flight_movements", "d4_absences")


def _window_status(
    cfg: config.BaseConfig, name: str, intervals: dict[str, coverage.Interval | None]
) -> WindowStatus | None:
    if cfg.windows is None:
        return None
    w = cfg.windows.get(name)
    overlaps = {
        d: (i := intervals.get(d)) is not None and i.start <= w.end and i.end >= w.start
        for d in _FIT_DATASETS
    }
    return WindowStatus(name, (w.start, w.end), overlaps)


def _scope_crew(cfg: config.BaseConfig) -> tuple[int, str]:
    s = cfg.scope
    fleets = sorted(config.fleet_members(cfg, s.fleet))
    d1 = loaders.load_dataset(cfg, "d1_crew_master")
    n = d1.filter(
        (pl.col("crew_group") == "PILOT")
        & (pl.col("employment_status") == "ACTIVE")
        & (pl.col("base") == s.base)
        & pl.col("fleet").is_in(fleets)
        & (pl.col("position") == s.position)
    ).height
    return n, f"{s.base}/{'+'.join(fleets)}/{s.position}"


def compute(cfg: config.BaseConfig) -> Readiness:
    from ..engine import roster_loader

    intervals = coverage.all_intervals(cfg)
    shared = coverage.intersect(*(intervals[d] for d in ("d2_rosters", *_FIT_DATASETS)))
    windows = [w for n in ("fitting", "holdout") if (w := _window_status(cfg, n, intervals))]

    try:
        start, end = roster_loader.select_template_window(cfg)
        template = (True, f"{start}..{end}")
    except ValueError as exc:
        template = (False, str(exc))

    scope_crew, scope_label = _scope_crew(cfg)
    checks = quality.compute_quality_checks(cfg)

    problems: list[str] = []
    for w in windows:
        missing = sorted(d for d, ok in w.overlaps.items() if not ok)
        if missing:
            problems.append(f"{w.name} window {w.window[0]}..{w.window[1]} has no data in {', '.join(missing)}")
    if not template[0]:
        problems.append(f"no roster template window: {template[1]}")
    if scope_crew == 0:
        problems.append(f"scope {scope_label} holds no ACTIVE pilot in D1")
    failing = [c.name for c in checks if c.status == "FAIL"]
    if failing:
        problems.append(f"{len(failing)} quality gate(s) FAIL: " + "; ".join(failing))
    return Readiness(
        config.corpus_banner(cfg), intervals, shared, windows, template, scope_crew, scope_label,
        checks, problems, limitations.collect(cfg),
    )


def run_readiness_report(cfg: config.BaseConfig) -> int:
    """Print the readiness report; 0 when the extract can be calibrated and simulated."""
    try:
        r = compute(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"Failed to load datasets: {exc}")
        return 1

    print(r.banner)
    print("\nWhere each dataset is recorded (IMP-516):")
    for name, interval in r.intervals.items():
        if interval is None:
            print(f"  {name:<28} no data")
        else:
            gaps = f", {interval.gap_days} quiet day(s) inside" if interval.gap_days else ""
            print(f"  {name:<28} {interval.label()}  ({interval.days} days{gaps})")
    shared = f"{r.shared_span[0]}..{r.shared_span[1]}" if r.shared_span else "none"
    print(f"  span shared by D2, D4 and D8: {shared}")

    print("\nConfigured windows against that data:")
    for w in r.windows:
        status = "ok" if w.supported else "NO DATA in " + ", ".join(d for d, ok in w.overlaps.items() if not ok)
        print(f"  {w.name:<8} {w.window[0]}..{w.window[1]}  {status}")
    print(f"  roster template window: {'ok ' + r.template[1] if r.template[0] else 'NOT AVAILABLE'}")
    if not r.template[0]:
        print(f"    {r.template[1]}")
    print(f"  scope {r.scope_label}: {r.scope_crew} ACTIVE pilot(s) in D1")
    if cfg.scope.fleet_resolution:
        print(f"    ({cfg.scope.fleet_resolution})")

    d8_report = clean.operated_flights_report(cfg, loaders.load_dataset(cfg, "d8_flight_movements"))[1]
    print(f"\nD8: {d8_report['rows_out']} of {d8_report['rows_in']} rows are operated flights "
          f"(cut-off {d8_report['cutoff']}, flight day = {d8_report['flight_day']})")

    print("\nQuality gates:")
    for c in r.checks:
        print(f"  [{c.status:<8}] {c.name}: {c.details}")
        if c.note:
            print(f"             note: {c.note}")
    print(f"  score {quality.quality_score(r.checks)}/100")

    print("\nLimitations of this data load:")
    print(limitations.format_limitations(r.limitations))

    if r.ready:
        print("\nREADY: windows, template window, scope and gates all hold.")
        return 0
    print("\nNOT READY:")
    for p in r.problems:
        print(f"  - {p}")
    return 1

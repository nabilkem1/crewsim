"""Gate V5 -- Trace Validation (spec Sec9.2): replay a real disruption week
and render an hour-by-hour operational timeline an SME can walk through in
a 60-90 minute session.

MOCK CORPUS DATA. There is no real Air Transat history in this repo
(tools/generate_mock_corpus.py generates D1-D12 entirely) -- per the
project's own "ask before changing design" convention, this was raised to
the user rather than silently substituted; the confirmed disposition is to
replay the mock corpus's own highest-disruption week and label it as such
everywhere it's shown, never presented as real history. V5 is genuinely
un-passable as a gate in the spec's own sense here: the spec's PASS
condition is a human IOC duty manager saying "yes, I would have done this"
in a real walkthrough, which this repo cannot produce regardless of data
realism. This module produces the artifact that walkthrough needs; it does
not, and cannot, self-certify a PASS.
"""
import datetime
import re
from typing import Any

from ..engine import replay
from ..engine.des import Simulation
from ..engine.policy import Policy

MOCK_DATA_CAVEAT = (
    "MOCK CORPUS DATA -- this is the mock corpus's own highest-disruption week, "
    "not a real Air Transat event. There is no real historical data in this repo "
    "to replay (see gates/v5_trace.py's module docstring)."
)

_TIME_RE = re.compile(r"^\[t=(\d+)\]\s*(.*)$")


def format_timeline(sim: Simulation, week_start: datetime.date) -> str:
    """sim.trace grouped into hour-by-hour buckets anchored to week_start
    (Monday 00:00) -- readable prose, not a raw log dump (S1e-06's AC)."""
    week_end = week_start + datetime.timedelta(days=7)
    lines = [
        f"V5 Trace Walkthrough -- week of {week_start.isoformat()} to {week_end.isoformat()}",
        MOCK_DATA_CAVEAT,
        "Ask: \"would you have actually done this?\" -- not \"is this number right\" (spec Sec9.2).",
        "=" * 78,
    ]
    current_hour: datetime.datetime | None = None
    for raw in sim.trace:
        m = _TIME_RE.match(raw)
        if not m:
            continue
        minute, text = int(m.group(1)), m.group(2)
        dt = datetime.datetime.combine(week_start, datetime.time.min) + datetime.timedelta(minutes=minute)
        hour_key = dt.replace(minute=0, second=0, microsecond=0)
        if hour_key != current_hour:
            current_hour = hour_key
            lines.append("")
            lines.append(f"-- {dt.strftime('%a %Y-%m-%d %H:00')} --")
        lines.append(f"  {dt.strftime('%H:%M')}  {text}")
    if current_hour is None:
        lines.append("\n(no disruption events in this window)")
    return "\n".join(lines)


def run_v5_gate(
    cfg: Any, costs: Any, policy: Policy, week_start: datetime.date | None = None
) -> tuple[Simulation, datetime.date, str]:
    """week_start=None (default): the mock corpus's own peak-disruption
    week for cfg.scope (see replay.find_peak_disruption_week's own
    docstring for why this stands in for a real memorable week)."""
    if week_start is None:
        week_start = replay.find_peak_disruption_week(cfg)
    sim = replay.run_historical_week(cfg, costs, policy, week_start)
    return sim, week_start, format_timeline(sim, week_start)

"""One scenario, one policy, as a time-ordered event tape.

The scoreboard reports what a policy cost; this reports what it *did*. Same
run, replayed as the sequence a planner would have lived through: an absence
arrives, the legal reserve pool is checked, someone is dispatched or drafted,
that draft opens another hole, an item eventually cancels.

Two sources, joined on the item uid -- which is the same integer in both, so
this is a typed join and not prose matching:

  * `sim.ledger.rows` is the spine. Typed, and carries `root_event_uid`, which
    is the PARENT item rather than merely the origin, so a cascade is a real
    chain (item 150's root is 149, the item whose draft broke it) rather than
    a flat "caused by" label.
  * `sim.trace` supplies the events that cost nothing and therefore never
    reach the ledger -- above all the arrival itself. A sick call books no
    money; without the trace the tape would open on a draft with no visible
    cause.

RESERVE_STAFFING is deliberately not an event. It is a structural daily
accrual per reserve -- 264 of the 505 ledger rows in a typical scenario, all
identical -- and emitting a line per row would bury the twenty decisions that
actually happened. It is reported as a background total instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .. import config
from ..engine import des
from ..engine.policy import Policy

# Engine time is minutes since the horizon start (S1d-04b), the same convention
# legality.py and costs.py use.
_MINUTES_PER_DAY = 1440
_MINUTES_PER_HOUR = 60

#: Booked rows that are background accrual rather than an operational decision.
_BACKGROUND_CATEGORIES = frozenset({"RESERVE_STAFFING"})

#: Parsed out of `sim.trace`. These are the only places the engine formats
#: these lines (des.py::sick_call_source / recovery_pipeline / _cascade), and
#: `tests/reporting/test_tape.py` pins each pattern against a real run so a
#: reworded log line fails loudly instead of silently emptying the tape.
_RE_SICK_CALL = re.compile(r"^\[t=(?P<t>\d+)\] SICK_CALL: (?P<crew>\S+) -> item (?P<item>\d+) \((?P<pairing>[^)]*)\)")
_RE_DISPLACED = re.compile(r"^\[t=(?P<t>\d+)\] DISPLACED_LINE: (?P<crew>\S+) bid reserve -> item (?P<item>\d+) \((?P<pairing>[^)]*)\)")
_RE_CASCADE = re.compile(r"^\[t=(?P<t>\d+)\]\s+CASCADE: draft of (?P<crew>\S+) broke their future pairing "
    r"(?P<pairing>\S+).*?-> item (?P<item>\d+)")

#: How each ledger category reads on the tape.
_LABELS: dict[str, str] = {
    "RESERVE_UTILIZATION": "reserve dispatched",
    "CANCELLATION": "cancelled at deadline, still uncovered",
    "APPR_COMPENSATION": "statutory passenger compensation",
    "TERMINAL_PENALTY": "still open at horizon end",
    "DEADHEAD": "positioned from another base",
    "HOTEL": "hotel night for that positioning",
    "TRANSPORT": "ground transport for that positioning",
}


def _label(category: str) -> str:
    if category.startswith("DRAFT_TIER"):
        return f"drafted (tier {category.removeprefix('DRAFT_TIER')})"
    return _LABELS.get(category, category.lower().replace("_", " "))


def _clock(minutes: float) -> tuple[int, str]:
    """(day index, HH:MM) for a simulated minute."""
    day = int(minutes // _MINUTES_PER_DAY)
    within = int(minutes % _MINUTES_PER_DAY)
    return day, f"{within // _MINUTES_PER_HOUR:02d}:{within % _MINUTES_PER_HOUR:02d}"


@dataclass
class _ItemContext:
    """What the trace knows about an open-time item that the ledger does not."""

    pairing: str | None = None
    origin: str | None = None       # SICK_CALL | DISPLACED_LINE | CASCADE
    origin_crew: str | None = None  # who fell sick / bid reserve / was drafted


def _item_context(
    trace: list[str], warmup_end: float, measurement_end: float
) -> tuple[dict[int, _ItemContext], list[dict[str, Any]]]:
    """Item metadata, and the arrival events that never reach the ledger.

    Arrivals are grouped by (minute, crew): one absence commonly breaks several
    pairings and logs a line per resulting item, and a tape that repeated
    "P00367 went sick" four times at the same minute would read as four
    absences.
    """
    context: dict[int, _ItemContext] = {}
    grouped: dict[tuple[int, str, str], list[int]] = {}

    for line in trace:
        for pattern, origin in (
            (_RE_SICK_CALL, "SICK_CALL"),
            (_RE_DISPLACED, "DISPLACED_LINE"),
            (_RE_CASCADE, "CASCADE"),
        ):
            if not (m := pattern.match(line)):
                continue
            t, crew = int(m["t"]), m["crew"]
            uid, pairing = int(m["item"]), m["pairing"]
            context[uid] = _ItemContext(pairing, origin, crew)
            # A cascade-created item is not its own arrival -- it is a
            # consequence, and the ledger row for the draft that caused it
            # already carries the timing. Grouping it here would show the
            # cascade twice.
            if origin != "CASCADE":
                grouped.setdefault((t, crew, origin), []).append(uid)
            break

    arrivals: list[dict[str, Any]] = []
    for (t, crew, origin), uids in grouped.items():
        day, clock = _clock(t)
        n = len(uids)
        arrivals.append(
            {
                "t": float(t),
                "day": day,
                "clock": clock,
                "kind": origin,
                "category": origin,
                "crew": crew,
                "item": min(uids),
                "items": sorted(uids),
                "root": min(uids),
                "amount": None,
                "in_window": warmup_end <= float(t) < measurement_end,
                "depth": 0,
                "text": (
                    f"{crew} called in sick"
                    if origin == "SICK_CALL"
                    else f"{crew} bid reserve, giving up their line"
                )
                + (f" — {n} pairing{'s' if n != 1 else ''} now open" if n else ""),
            }
        )
    return context, arrivals


def _depth_of(uid: int, parent: dict[int, int]) -> int:
    """How far an item sits below the absence that started the chain.

    Guarded against a cycle rather than trusting the data: this walks a
    relationship the engine builds at runtime, and an infinite loop here would
    hang a request rather than fail it.
    """
    depth = 0
    seen = {uid}
    cur = uid
    while (up := parent.get(cur)) is not None and up != cur and up not in seen:
        seen.add(up)
        cur = up
        depth += 1
    return depth


def build_tape(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    scenario_id: int,
    master_seed: str,
    n_scenarios: int,
) -> dict[str, Any]:
    """Re-run one scenario and return its event tape.

    Re-running rather than storing every event is only viable because the
    engine is deterministic -- `run_scenario(scenario_id=n, master_seed=s)`
    reproduces byte-identical output, the property gate V7 already guards. One
    scenario is ~1.5s, against ~7 MB per job to store them all.
    """
    sim = des.run_scenario(
        cfg, costs, policy, scenario_id=scenario_id, master_seed=master_seed,
        n_scenarios=n_scenarios, trace=True,
    )

    # Which rows E[C] is actually built from. The tape covers the WHOLE
    # horizon, but `expected_cost` is the measured window only -- warm-up
    # excluded, cool-down attributed back when its causal chain starts inside
    # (des.rows_in_measurement_window). Marking each event lets the running
    # total reconcile with the scoreboard instead of quietly exceeding it.
    warmup_end, measurement_end = des.measurement_window_bounds(cfg)
    measured_rows = des.rows_in_measurement_window(cfg, sim)
    # Identity, not equality: LedgerRow is a frozen dataclass, so two genuinely
    # distinct rows with the same values would compare equal and a set of rows
    # would silently collapse them.
    in_window = {id(r) for r in measured_rows}
    # Same exclusion des.measured_window_costs applies (DELAY_AMBIENT does
    # not vary by policy and is deliberately kept out of E[C]/CVaR95) -- this
    # must reconcile with that figure, not independently re-sum every row in
    # the window and silently include what E[C] excludes.
    measured_cost = sum(
        r.amount for r in measured_rows if r.category not in des.EXCLUDED_FROM_OPTIMISED_COST
    )

    context, events = _item_context(sim.trace, warmup_end, measurement_end)

    parent = {
        r.event_uid: r.root_event_uid
        for r in sim.ledger.rows
        if r.root_event_uid != r.event_uid
    }

    background_total = 0.0
    background_rows = 0
    total_cost = 0.0
    drafts = dispatches = uncovered = 0

    for row in sim.ledger.rows:
        total_cost += row.amount
        if row.category in _BACKGROUND_CATEGORIES:
            background_total += row.amount
            background_rows += 1
            continue

        if row.category.startswith("DRAFT_TIER"):
            drafts += 1
        elif row.category == "RESERVE_UTILIZATION":
            dispatches += 1
        elif row.category in ("CANCELLATION", "TERMINAL_PENALTY"):
            uncovered += 1

        ctx = context.get(row.event_uid, _ItemContext())
        day, clock = _clock(row.sim_time)
        events.append(
            {
                "in_window": id(row) in in_window,
                "t": float(row.sim_time),
                "day": day,
                "clock": clock,
                "kind": row.category,
                "category": row.category,
                "crew": row.crew_id,
                "item": row.event_uid,
                "items": [row.event_uid],
                "root": row.root_event_uid,
                "amount": float(row.amount),
                "depth": _depth_of(row.event_uid, parent),
                "text": _label(row.category)
                + (f" — {ctx.pairing}" if ctx.pairing else ""),
            }
        )

    # Chronological, and an arrival before its own consequences when they share
    # a minute: an absence and the draft answering it are frequently logged at
    # the same simulated minute, and showing the draft first would invert cause
    # and effect.
    events.sort(key=lambda e: (e["t"], e["depth"], 0 if e["amount"] is None else 1))

    return {
        "scenario": scenario_id,
        "policy": policy.policy_id,
        "master_seed": master_seed,
        "horizon_minutes": cfg.horizon.horizon_days * _MINUTES_PER_DAY,
        "horizon_days": cfg.horizon.horizon_days,
        "events": events,
        "window": {
            "warmup_end": warmup_end,
            "measurement_end": measurement_end,
            "note": (
                "E[C] and CVaR95 are measured over this window only. Events outside "
                "it are shown because they happened, not because they are counted."
            ),
        },
        "totals": {
            "cost": total_cost,
            "measured_cost": measured_cost,
            "drafts": drafts,
            "reserve_dispatches": dispatches,
            "uncovered": uncovered,
        },
        # Reported, not hidden: it is a real and often dominant share of the
        # cost, it simply is not a decision anyone made during the scenario.
        "background": {
            "category": "RESERVE_STAFFING",
            "total": background_total,
            "rows": background_rows,
            "note": (
                "Structural daily accrual per reserve. Included in the cost total, "
                "excluded from the tape because it is not an operational event."
            ),
        },
    }

"""Structural (non-event-driven) cost booking -- the §4.2 `crewsim.engine.costs`
module.

A pure function over plain dataclasses, like every engine module except des.py:
it takes a ledger, the reserve pool and the tariff, and books rows. des.py owns
*when* this runs (once, at Simulation construction); this module owns *what*
gets booked.

History worth keeping: this module used to hold a SECOND, simplified staffing
implementation -- flat rate, synthetic `R001..` crew ids, a caller-supplied
`horizon_days` -- that nothing in the engine called. des.py had its own real
version, and `tests/engine/test_costs.py` plus `explain-cost` both exercised the
copy, so S1a-04's entire verification passed without touching the code that
actually books staffing (the fourth instance of that pattern in this project).
The real implementation now lives here and des.py delegates to it, so the test
and the engine are the same thing.
"""
from __future__ import annotations

from typing import Any

from .ledger import CostLedger
from .state import BlockType, CrewMember

MINUTES_PER_DAY = 1440.0


def book_reserve_staffing(
    ledger: CostLedger,
    scenario_id: int,
    policy_id: str,
    reserves: list[CrewMember],
    rates: Any,
    horizon_minutes: float,
    call_types: dict[tuple[str | None, float, int], str] | None = None,
) -> None:
    """Book RESERVE_STAFFING once per reserve per covered day, at that day's own rate.

    `call_types`, if given, receives the SC/LC type each booked row was paid
    at, keyed like `des.Simulation.reserve_call_types` -- (crew_id, sim_time,
    event_uid) -- so KPIs can split reserve-days by call type (IMP-117)
    without adding a column to the ledger (whose content hash gate V7 pins).

    Fixes D1: one row per (reserve, day) stamped with THAT day's timestamp, so
    the warm-up filter prorates staffing exactly as it prorates every other
    category. The v2 defect booked the whole staffing cost as a single lump at
    t=0, which the warm-up filter then discarded entirely.

    Not a flat rate per reserve: 8 of 12 reserves in the current template window
    carry both short-call and long-call blocks across the window, so "this
    reserve is SC" is not a well-defined per-crew label. The day-level block
    type is well-defined, so each (reserve, day) is paid off whichever RESERVE
    block actually covers that day.

    `rates` is costs.reserve.guarantee_per_day (a .short_call/.long_call pair).
    A day with no covering RESERVE block is not booked at all -- reserve lines
    have days off, and paying for them would silently inflate every policy's
    staffing by the same factor.
    """
    n_days = int(horizon_minutes // MINUTES_PER_DAY)
    for reserve in reserves:
        for day in range(n_days):
            day_start = day * MINUTES_PER_DAY
            day_end = day_start + MINUTES_PER_DAY
            covering = [
                b for b in reserve.blocks_in(day_start, day_end) if b.btype == BlockType.RESERVE
            ]
            if not covering:
                continue
            # Prefer the block already running at the day's start; otherwise the
            # first to begin during it. A day split across an SC and an LC block
            # is paid once, at the rate in force when the day opened.
            at_start = [b for b in covering if b.start <= day_start < b.end]
            block = at_start[0] if at_start else covering[0]
            call_type = block.reserve_call_type or "SC"
            rate = rates.short_call if call_type == "SC" else rates.long_call
            if call_types is not None:
                call_types[(reserve.crew_id, day_start, 0)] = call_type
            ledger.book(
                scenario_id=scenario_id,
                policy_id=policy_id,
                sim_time=day_start,
                event_uid=0,        # structural: no originating event
                root_event_uid=0,   # and therefore no causal chain
                crew_id=reserve.crew_id,
                category="RESERVE_STAFFING",
                amount=rate,
            )


# The category is DELAY_AMBIENT, not DELAY: this prices real-world flight
# lateness measured from historical D8 flight movements for this base+fleet
# (calibration/delays.py::fit_delays), which happens regardless of any
# reserve/draft decision this simulation makes -- it is NOT delay caused by
# a drafted crew member positioning late, which nothing in the engine
# detects or prices yet (that would be a policy-dependent DELAY category,
# and would belong in the optimised cost; this one deliberately does not --
# see measured_window_costs' own exclusion of this category).
def book_flight_delays(
    ledger: CostLedger,
    scenario_id: int,
    policy_id: str,
    daily_delay_minutes: list[float],
    delay_per_minute: float,
) -> None:
    """Book DELAY_AMBIENT once per day that had any delayed flights, at that
    day's own timestamp -- same per-day stamping as book_reserve_staffing,
    for the same reason (the warm-up filter prorates by sim_time; a lump
    booked at t=0 would be discarded by it entirely). A day with zero
    delayed flights is not booked at all, matching book_reserve_staffing's
    own "nothing to book, no row" convention.
    """
    for day, minutes in enumerate(daily_delay_minutes):
        if minutes <= 0:
            continue
        day_start = day * MINUTES_PER_DAY
        ledger.book(
            scenario_id=scenario_id,
            policy_id=policy_id,
            sim_time=day_start,
            event_uid=0,
            root_event_uid=0,
            crew_id=None,
            category="DELAY_AMBIENT",
            amount=minutes * delay_per_minute,
        )

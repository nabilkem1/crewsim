"""S1a-04 -- reserve staffing accrues per reserve-day (fixes defect D1).

Exercises the SAME book_reserve_staffing the engine calls (des.py's
Simulation._book_reserve_staffing delegates straight to it), and then asserts
end-to-end against a real Simulation. The previous version of this file tested a
second, simplified copy of the staffing rule that lived in engine/costs.py and
that nothing in the engine ever called -- so it passed regardless of what the
DES actually booked.
"""
from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine import des
from crewsim.engine.costs import book_flight_delays, book_reserve_staffing
from crewsim.engine.ledger import CostLedger
from crewsim.engine.policy import load_policy
from crewsim.engine.state import Block, BlockType, CrewMember


class _Rates:
    """Stands in for costs.reserve.guarantee_per_day -- two distinct rates so a
    flat-rate regression cannot pass."""
    short_call = 250.0
    long_call = 180.0


def _reserve(crew_id: str, blocks: list[Block]) -> CrewMember:
    return CrewMember(
        crew_id=crew_id, base="YUL", fleet_quals={"A321neoLR"}, position="FO",
        seniority=1, calendar=blocks,
    )


def _day(d: int) -> tuple[float, float]:
    return d * 1440.0, (d + 1) * 1440.0


def test_one_row_per_reserve_per_covered_day_at_that_days_timestamp() -> None:
    """D1's actual fix: a row per (reserve, day) stamped with THAT day's time.

    v2 booked one lump at t=0, which the warm-up filter then ate whole.
    """
    ledger = CostLedger()
    # Two reserves, on reserve for days 0-2 inclusive (3 days each).
    reserves = [
        _reserve("R001", [Block(start=0.0, end=3 * 1440.0, btype=BlockType.RESERVE,
                                reserve_call_type="SC")]),
        _reserve("R002", [Block(start=0.0, end=3 * 1440.0, btype=BlockType.RESERVE,
                                reserve_call_type="LC")]),
    ]
    book_reserve_staffing(ledger, 0, "P", reserves, _Rates(), horizon_minutes=3 * 1440.0)

    assert len(ledger.rows) == 6  # 2 reserves x 3 days
    # Each day's rows carry that day's own timestamp -- nothing piles up at t=0.
    assert sorted({r.sim_time for r in ledger.rows}) == [0.0, 1440.0, 2880.0]
    assert all(r.category == "RESERVE_STAFFING" for r in ledger.rows)
    # Structural cost has no causal chain (des.py's root_event_uid==0 sentinel).
    assert all(r.root_event_uid == 0 for r in ledger.rows)


def test_each_day_is_paid_at_its_own_call_type_rate() -> None:
    """SC and LC are priced differently, so staffing cannot be a flat rate."""
    ledger = CostLedger()
    reserves = [_reserve("R001", [
        Block(start=0.0, end=1440.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
        Block(start=1440.0, end=2880.0, btype=BlockType.RESERVE, reserve_call_type="LC"),
    ])]
    book_reserve_staffing(ledger, 0, "P", reserves, _Rates(), horizon_minutes=2 * 1440.0)

    by_time = {r.sim_time: r.amount for r in ledger.rows}
    assert by_time == {0.0: 250.0, 1440.0: 180.0}


def test_days_off_are_not_paid() -> None:
    """A reserve line has days off; billing them would inflate every policy."""
    ledger = CostLedger()
    reserves = [_reserve("R001", [
        Block(start=0.0, end=1440.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
        Block(start=1440.0, end=2880.0, btype=BlockType.DAY_OFF),
        Block(start=2880.0, end=4320.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
    ])]
    book_reserve_staffing(ledger, 0, "P", reserves, _Rates(), horizon_minutes=3 * 1440.0)

    assert len(ledger.rows) == 2
    assert sorted(r.sim_time for r in ledger.rows) == [0.0, 2880.0]


def test_staffing_scales_linearly_with_reserve_count() -> None:
    """S1a-04's own AC: the staffing component scales with R x measured days."""
    def total_for(n_reserves: int) -> float:
        ledger = CostLedger()
        reserves = [
            _reserve(f"R{i:03d}", [Block(start=0.0, end=5 * 1440.0, btype=BlockType.RESERVE,
                                         reserve_call_type="SC")])
            for i in range(n_reserves)
        ]
        book_reserve_staffing(ledger, 0, "P", reserves, _Rates(), horizon_minutes=5 * 1440.0)
        return ledger.total_cost()

    assert total_for(2) == 2 * total_for(1)
    assert total_for(6) == 6 * total_for(1)


def test_warmup_filter_prorates_staffing_like_any_other_category() -> None:
    """The D1 regression in one assertion: filtering out the warm-up window must
    remove exactly the warm-up days' staffing, not all of it and not none."""
    ledger = CostLedger()
    reserves = [_reserve("R001", [Block(start=0.0, end=10 * 1440.0, btype=BlockType.RESERVE,
                                        reserve_call_type="SC")])]
    book_reserve_staffing(ledger, 0, "P", reserves, _Rates(), horizon_minutes=10 * 1440.0)

    warmup_end = 3 * 1440.0
    assert ledger.total_cost() == 10 * 250.0
    assert ledger.total_cost(min_time=warmup_end) == 7 * 250.0


@pytest.mark.parametrize("policy_name", ["R6"])
def test_real_simulation_books_staffing_through_this_module(policy_name: str) -> None:
    """End-to-end: the figure a real run reports comes from the code above.

    Reconstructs the Simulation's own RESERVE_STAFFING total from its rows and
    checks it against an independent call to book_reserve_staffing over the same
    reserve pool -- if des.py ever grows a private copy of this rule again, the
    two stop agreeing.
    """
    cfg = config.load()
    # displaced_flying=absorb: this test recomputes staffing from the
    # POST-simulation reserve calendars and compares it to what was booked at
    # construction from the PRE-simulation ones. With displaced flying on, those
    # legitimately differ -- a drafted reserve's RESERVE block gets split -- so
    # the comparison would be measuring assign_reserve, not staffing.
    cfg = cfg.model_copy(
        update={"population": cfg.population.model_copy(update={"displaced_flying": "absorb"})}
    )
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / f"{policy_name}.yaml")
    sim = des.run_scenario(cfg, costs, policy, daily_sick_calls=[0] * cfg.horizon.horizon_days)

    engine_rows = [r for r in sim.ledger.rows if r.category == "RESERVE_STAFFING"]
    assert engine_rows, "a real R6 run booked no reserve staffing at all"

    independent = CostLedger()
    book_reserve_staffing(
        independent, sim.scenario_id, policy.policy_id, sim.reserves,
        costs.reserve.guarantee_per_day, sim.horizon_minutes,
    )
    assert len(independent.rows) == len(engine_rows)
    assert independent.total_cost() == sum(r.amount for r in engine_rows)


# ==================================================== book_flight_delays
class _DelayRate:
    delay_per_minute = 55.0


def test_delay_booked_once_per_day_at_that_days_own_timestamp() -> None:
    """Same D1-shaped rule as RESERVE_STAFFING: one row per day, stamped with
    THAT day's own time, not a single lump at t=0 the warm-up filter would
    then discard whole."""
    ledger = CostLedger()
    book_flight_delays(ledger, 0, "P", [10.0, 0.0, 30.0], delay_per_minute=55.0)

    assert len(ledger.rows) == 2  # day 1 (0.0 minutes) is not booked at all
    by_time = {r.sim_time: r.amount for r in ledger.rows}
    assert by_time == {0.0: 10.0 * 55.0, 2 * 1440.0: 30.0 * 55.0}
    assert all(r.category == "DELAY_AMBIENT" for r in ledger.rows)
    # Structural cost has no causal chain and no crew tie -- it is not any
    # particular crew member's delay.
    assert all(r.root_event_uid == 0 and r.crew_id is None for r in ledger.rows)


def test_zero_delay_days_are_not_booked() -> None:
    """A day with no delayed flights books nothing at all, matching
    book_reserve_staffing's own "days off are not paid" convention."""
    ledger = CostLedger()
    book_flight_delays(ledger, 0, "P", [0.0, 0.0, 0.0], delay_per_minute=55.0)
    assert ledger.rows == []


def test_warmup_filter_prorates_delay_like_any_other_category() -> None:
    """The D1 regression, for delay: filtering out the warm-up window must
    remove exactly the warm-up days' delay cost, not all of it and not none."""
    ledger = CostLedger()
    daily = [10.0] * 10  # 10 minutes/day for 10 days
    book_flight_delays(ledger, 0, "P", daily, delay_per_minute=55.0)

    warmup_end = 3 * 1440.0
    assert ledger.total_cost() == 10 * 10.0 * 55.0
    assert ledger.total_cost(min_time=warmup_end) == 7 * 10.0 * 55.0


def test_real_simulation_books_delay_ambient_through_this_module() -> None:
    """End-to-end: a real Simulation given explicit daily_delay_minutes books
    exactly what an independent call to book_flight_delays computes over the
    same input -- if des.py ever grows a private copy of this rule, the two
    stop agreeing."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    daily_delay = [0.0] * cfg.horizon.horizon_days
    daily_delay[5] = 42.0
    daily_delay[20] = 137.5

    sim = des.run_scenario(
        cfg, costs, policy, daily_sick_calls=[0] * cfg.horizon.horizon_days,
        daily_delay_minutes=daily_delay,
    )

    engine_rows = [r for r in sim.ledger.rows if r.category == "DELAY_AMBIENT"]
    assert len(engine_rows) == 2

    independent = CostLedger()
    book_flight_delays(
        independent, sim.scenario_id, policy.policy_id, daily_delay,
        delay_per_minute=costs.disruption.delay_per_minute,
    )
    assert independent.total_cost() == sum(r.amount for r in engine_rows)


def test_delay_ambient_excluded_from_measured_window_costs() -> None:
    """User-confirmed disposition: DELAY_AMBIENT is real and shown in
    cost_by_category, but must never move E[C]/CVaR95/the R* recommendation
    -- it does not vary by reserve policy, so folding it in would inject
    scenario-to-scenario variance unrelated to reserve-policy tail risk."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    daily_delay = [0.0] * cfg.horizon.horizon_days
    # Well inside the measurement window (warmup_days=7), not day 0 -- a
    # warm-up-booked row would be filtered out regardless of category, which
    # would make this test pass for the wrong reason.
    daily_delay[cfg.horizon.warmup_days + 1] = 500.0

    with_delay = des.run_scenario(
        cfg, costs, policy, daily_sick_calls=[0] * cfg.horizon.horizon_days,
        daily_delay_minutes=daily_delay,
    )
    without_delay = des.run_scenario(
        cfg, costs, policy, daily_sick_calls=[0] * cfg.horizon.horizon_days,
        daily_delay_minutes=[0.0] * cfg.horizon.horizon_days,
    )

    assert any(r.category == "DELAY_AMBIENT" for r in with_delay.ledger.rows)
    measured = des.measured_window_costs(cfg, [with_delay, without_delay])
    assert measured[0] == measured[1], (
        "DELAY_AMBIENT leaked into the optimised cost figure"
    )

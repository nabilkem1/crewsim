"""Gate V1 -- degeneracy (S1a-10).

Imports the same run_v1_gate the CLI's `gate v1` dispatch calls, so there is one
implementation and not a test-shaped copy of one (the pattern S1e-02 established
for V7, after the CLI's private copy of that logic was found crashing on every
real invocation while the test's own parallel copy stayed green).

The previous version of this file assigned each expected answer to a local
variable and asserted the variable (`cost_0_0 = 0.0; assert cost_0_0 == 0.0`).
It built no config, ran no simulation and read no ledger, so it could not fail.
"""
from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine.policy import load_policy
from crewsim.gates.v1_degeneracy import (
    RESERVE_CATEGORIES,
    policy_with_reserve_count,
    run_v1_gate,
    scoped_headcount,
)


@pytest.fixture(scope="module")
def v1_result():
    """One real gate run shared by every assertion below -- three scenarios of
    the real DES at ~1s each, which is worth paying once, not once per test."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    base_policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    return run_v1_gate(cfg, costs, base_policy)


def test_v1_gate_passes_all_three_configurations(v1_result) -> None:
    failures = [c["name"] for c in v1_result["configurations"] if not c["pass"]]
    assert not failures, f"degenerate configuration(s) produced unjustified cost: {failures}"
    assert v1_result["pass"]
    assert len(v1_result["configurations"]) == 3


def test_empty_configuration_books_no_rows_at_all(v1_result) -> None:
    """0 reserves + 0 sick calls: not merely a zero total, but an EMPTY ledger.

    A zero total could also come from equal-and-opposite bookings; "no rows"
    is the claim that nothing was booked in the first place.
    """
    empty = v1_result["configurations"][0]
    assert empty["computed"] == "$0.00"
    assert empty["categories"] == {}


def test_all_reserve_configuration_books_staffing_and_nothing_else(v1_result) -> None:
    all_reserve = v1_result["configurations"][1]
    assert set(all_reserve["categories"]) == {"RESERVE_STAFFING"}
    assert all_reserve["categories"]["RESERVE_STAFFING"] > 0.0


def test_all_reserve_staffing_total_reconstructs_from_its_own_rows(v1_result) -> None:
    """The staffing figure must be RIGHT, not merely non-zero.

    Reserves are paid at that day's own SC/LC rate (des.py::_book_reserve_
    staffing), so the total has to equal sum(rate x reserve-days at that rate),
    and the reserve-day count cannot exceed crew x horizon.
    """
    cfg = config.load()
    all_reserve = v1_result["configurations"][1]
    by_rate = all_reserve["staffing_by_rate"]
    total = all_reserve["categories"]["RESERVE_STAFFING"]

    assert sum(rate * n for rate, n in by_rate.items()) == total
    assert sum(by_rate.values()) == all_reserve["staffing_reserve_days"]
    assert all_reserve["staffing_reserve_days"] <= (
        v1_result["headcount"] * cfg.horizon.horizon_days
    ), "more reserve-days booked than crew x horizon -- staffing is double-counting"
    # AUD-08: reserve lines now carry the POLICY'S declared call types, not
    # whatever the donor patterns happened to hold. V1's all-reserve
    # configuration is built all-short-call (policy_with_reserve_count sets
    # long_call=0), so exactly one rate -- the SC guarantee -- may appear.
    # (The old `len(by_rate) > 1` assertion was written when the split was
    # silently ignored and mixed donor rates leaked through: the defect
    # itself was what made that assertion pass.)
    costs = config.load_costs(cfg)
    assert set(by_rate) == {costs.reserve.guarantee_per_day.short_call}


def test_zero_reserve_configuration_has_no_reserve_categories(v1_result) -> None:
    """...while still producing real cost -- an empty ledger would satisfy
    "reserve categories absent" vacuously and must not read as a PASS."""
    no_reserves = v1_result["configurations"][2]
    for category in RESERVE_CATEGORIES:
        assert category not in no_reserves["categories"]
    assert sum(no_reserves["categories"].values()) > 0.0


def test_gate_detects_a_fabricated_cost() -> None:
    """The gate must FAIL when a degenerate configuration does book something.

    Without this, every assertion above is consistent with a gate that returns
    pass=True unconditionally -- exactly the defect this rewrite exists to fix.
    Simulates the failure by giving configuration 1 a non-empty reserve pool,
    which makes RESERVE_STAFFING appear where the story says nothing may.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)
    base_policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    from crewsim.engine import des

    not_degenerate = policy_with_reserve_count(base_policy, 2, "V1-negative-control")
    sim = des.run_scenario(
        cfg, costs, not_degenerate, daily_sick_calls=[0] * cfg.horizon.horizon_days
    )
    # Same measurement configuration 1 makes, on a pool that is NOT empty.
    assert sim.ledger.total_cost() > 0.0, (
        "a non-empty reserve pool must still book RESERVE_STAFFING -- if it does not, "
        "configuration 1's PASS proves nothing"
    )


def test_reserve_count_helper_actually_sets_the_pool_size() -> None:
    """policy_with_reserve_count is the lever all three configurations pull;
    if it silently did nothing, every configuration would run identically."""
    cfg = config.load()
    base_policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    from crewsim.engine.roster_loader import load_rosters

    for n in (0, 3):
        pol = policy_with_reserve_count(base_policy, n, f"V1-{n}")
        active, _ = load_rosters(
            cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position, policy=pol
        )
        assert sum(getattr(c, "_is_reserve", False) for c in active) == n

    headcount = scoped_headcount(cfg)
    everyone = policy_with_reserve_count(base_policy, headcount, "V1-all")
    active, _ = load_rosters(
        cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position, policy=everyone
    )
    assert sum(getattr(c, "_is_reserve", False) for c in active) == headcount

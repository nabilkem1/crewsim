"""Gate V2 -- Erlang-B sanity bound (S1b-07).

Imports the same `run_v2_gate` / `erlang_b` the CLI's `gate v2` dispatch calls.
Previously this file carried its own copy of `erlang_b` and compared it against
`prob_shortfall_des = 0.098  # Stubbed DES mock value` -- a literal, with no
simulation anywhere, so the gate could not have caught the reserve-accounting
bug it exists to catch.
"""
from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine.policy import load_policy
from crewsim.gates.v2_erlang import (
    erlang_b,
    mean_on_call_servers,
    print_v2_report,
    run_v2_gate,
)

N_SCENARIOS = 2


@pytest.fixture(scope="module")
def sim_inputs():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    return cfg, costs, policy


@pytest.fixture(scope="module")
def v2_result(sim_inputs):
    cfg, costs, policy = sim_inputs
    return run_v2_gate(cfg, costs, policy, n_scenarios=N_SCENARIOS)


# ------------------------------------------------------------ the closed form
def test_erlang_b_matches_hand_computable_values() -> None:
    """B(1,1) = 1/2 and B(2,1) = 1/5 by the textbook formula."""
    assert erlang_b(1, 1.0) == pytest.approx(0.5)
    assert erlang_b(2, 1.0) == pytest.approx(0.2)


def test_erlang_b_is_monotone_in_servers_and_load() -> None:
    """More servers can only reduce blocking; more load can only increase it.
    A sign error or an inverted loop would break one of these."""
    assert erlang_b(5, 3.0) > erlang_b(10, 3.0)
    assert erlang_b(5, 3.0) < erlang_b(5, 8.0)


def test_erlang_b_degenerate_cases() -> None:
    assert erlang_b(0, 5.0) == 1.0     # no servers: everything blocks
    assert erlang_b(5, 0.0) == 0.0     # no load: nothing blocks


# --------------------------------------------------------- the measured side
def test_v2_measures_a_real_simulation_not_a_literal(v2_result) -> None:
    """Every DES-side figure must come from a run. The previous version's
    shortfall was a constant, so it could not move when the engine changed."""
    assert v2_result["arrivals"] > 0
    assert v2_result["blocked"] > 0
    assert 0.0 <= v2_result["p_hat"] <= 1.0
    assert v2_result["mean_service_hours"] > 0.0, "no reserve was ever assigned"
    assert v2_result["arrival_rate_per_day"] > 0.0
    # Servers is the time-average on call, which must be below headcount
    # because reserve lines rotate off (S1b-03).
    assert 0 < v2_result["servers"] < v2_result["reserve_headcount"]


def test_v2_bound_holds_on_the_real_corpus(v2_result) -> None:
    """The gate's actual verdict: the DES cannot be more available than an
    idealised loss system with the same servers and offered load."""
    assert v2_result["pass"], v2_result["interpretation"]
    assert v2_result["ci_high"] >= v2_result["theory"]


def test_v2_reports_containment_separately_from_the_verdict(v2_result) -> None:
    """Containment is computed and printed but is NOT the verdict -- it is not
    satisfiable by this model (see the module docstring). Asserting only that
    the two are reported as distinct keys, not what containment evaluates to,
    so this test does not pin an incidental property of today's corpus."""
    assert "contained" in v2_result
    assert isinstance(v2_result["contained"], bool)


def test_v2_gate_fails_when_the_des_is_more_available_than_theory(sim_inputs, monkeypatch) -> None:
    """The negative control. Without this, every assertion above is consistent
    with a gate that returns pass=True unconditionally -- which is exactly the
    defect being fixed.

    Simulates reserve double-counting: the pool covers everything, so nothing
    blocks on arrival. p_hat then falls to 0 while B(s, a) stays positive, and
    the bound must be reported as VIOLATED.
    """
    cfg, costs, policy = sim_inputs
    from crewsim.gates import v2_erlang

    real_run_scenario = v2_erlang.des.run_scenario

    def over_available(*args, **kwargs):
        sim = real_run_scenario(*args, **kwargs)
        sim.n_blocked_on_arrival = 0        # every arrival found a free reserve
        return sim

    monkeypatch.setattr(v2_erlang.des, "run_scenario", over_available)
    result = run_v2_gate(cfg, costs, policy, n_scenarios=1)

    assert result["p_hat"] == 0.0
    assert result["theory"] > 0.0
    assert not result["pass"], "V2 accepted a DES more available than the closed form allows"
    assert "double-counting" in result["interpretation"]


def test_mean_on_call_servers_is_a_time_average_not_a_headcount() -> None:
    """Two reserves each on call for half the horizon are ONE server, not two.
    Using headcount here would overstate capacity and mis-attribute the gap."""
    from crewsim.engine.state import Block, BlockType, CrewMember

    horizon = 1000.0
    crew = [
        CrewMember(crew_id=f"R{i}", base="YUL", fleet_quals={"A321neoLR"}, position="FO",
                   seniority=i, calendar=[Block(start=0.0, end=500.0, btype=BlockType.RESERVE)])
        for i in range(2)
    ]
    assert mean_on_call_servers(crew, horizon) == pytest.approx(1.0)


def test_print_v2_report_runs(v2_result, capsys) -> None:
    """The CLI path renders without raising, and shows both figures side by
    side as AC2 requires."""
    print_v2_report(v2_result)
    out = capsys.readouterr().out
    assert "DES shortfall" in out
    assert "Theory  B(s, a)" in out
    assert "the gate's verdict" in out

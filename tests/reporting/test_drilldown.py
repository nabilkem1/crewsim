import types

from crewsim import config
from crewsim.engine import des
from crewsim.engine.ledger import CostLedger
from crewsim.engine.policy import load_policy
from crewsim.reporting.drilldown import (
    build_scenario_drilldown,
    root_chain,
    select_exemplar_scenarios,
)


def _fake_sim(scenario_id, rows, trace):
    ledger = CostLedger()
    for row in rows:
        ledger.book(scenario_id=scenario_id, policy_id="P", **row)
    return types.SimpleNamespace(scenario_id=scenario_id, ledger=ledger, trace=trace)


def test_select_exemplar_scenarios_costliest_and_typical():
    cfg = config.load()
    sims = [
        types.SimpleNamespace(scenario_id=i, ledger=CostLedger(), trace=[])
        for i in range(5)
    ]
    # costs: 10, 20, 30, 40, 100 -- median 30, so scenario 2 (cost 30) must
    # be the single closest "typical" pick, and scenario 4 (cost 100) must
    # be the top "costliest" pick.
    for sim, amount in zip(sims, [10.0, 20.0, 30.0, 40.0, 100.0], strict=False):
        warmup_end, _ = des.measurement_window_bounds(cfg)
        sim.ledger.book(scenario_id=sim.scenario_id, policy_id="P", sim_time=warmup_end + 1.0,
                         event_uid=1, root_event_uid=1, crew_id=None, category="CANCELLATION", amount=amount)

    costliest, typical = select_exemplar_scenarios(cfg, sims, k=2)
    assert [s.scenario_id for s, _ in costliest] == [4, 3]
    assert typical[0][0].scenario_id == 2

def test_root_chain_matches_ledger_rows_and_trace_lines():
    trace = [
        "[t=100] SICK_CALL: C1 -> item 7 (PAIR1)",
        "[t=100] SICK_CALL: C2 -> item 8 (PAIR2)",  # unrelated item, must not leak in
        "[t=300] item 7 (PAIR1) CANCELLED at deadline, still uncovered",
    ]
    sim = _fake_sim(0, rows=[
        {"sim_time": 300.0, "event_uid": 7, "root_event_uid": 7, "crew_id": None,
             "category": "CANCELLATION", "amount": 25000.0},
        {"sim_time": 100.0, "event_uid": 8, "root_event_uid": 8, "crew_id": "C2",
             "category": "RESERVE_UTILIZATION", "amount": 250.0},  # different root, must not leak in
    ], trace=trace)

    chain = root_chain(sim, root_uid=7)
    assert chain["root_event_uid"] == 7
    assert len(chain["rows"]) == 1
    assert chain["rows"][0].category == "CANCELLATION"
    assert len(chain["trace_lines"]) == 2
    assert all("item 7" in line for line in chain["trace_lines"])
    assert not any("item 8" in line for line in chain["trace_lines"])

def test_build_scenario_drilldown_finds_uncovered_chains_only():
    sim = _fake_sim(3, rows=[
        {"sim_time": 100.0, "event_uid": 1, "root_event_uid": 1, "crew_id": "C1",
             "category": "RESERVE_UTILIZATION", "amount": 250.0},  # resolved, not uncovered
        {"sim_time": 200.0, "event_uid": 2, "root_event_uid": 2, "crew_id": None,
             "category": "CANCELLATION", "amount": 25000.0},
        {"sim_time": 300.0, "event_uid": 3, "root_event_uid": 3, "crew_id": None,
             "category": "TERMINAL_PENALTY", "amount": 37500.0},
    ], trace=["line a", "line b"])

    cfg = config.load()
    d = build_scenario_drilldown(cfg, sim, cost=62750.0)
    assert d["scenario_id"] == 3
    assert d["cost"] == 62750.0
    assert d["trace"] == ["line a", "line b"]
    roots = {c["root_event_uid"] for c in d["chains"]}
    assert roots == {2, 3}  # the resolved RESERVE_UTILIZATION root (1) must not appear

def test_drilldown_real_scenarios_end_to_end():
    """Real, small-scale integration: root_event_uid actually traces a real
    cancellation back to its real sick call, using the real trace."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    sims = des.run_policy_crn(cfg, costs, policy, 3, "master", trace=True)

    costliest, typical = select_exemplar_scenarios(cfg, sims, k=2)
    assert len(costliest) == 2
    assert len(typical) == 2
    assert costliest[0][1] >= costliest[1][1]  # sorted descending by cost

    sim, cost = costliest[0]
    d = build_scenario_drilldown(cfg, sim, cost)
    assert d["trace"], "a real scenario must produce a non-empty trace"
    if d["chains"]:
        chain = d["chains"][0]
        assert chain["rows"]
        assert chain["trace_lines"], "a real uncovered leg must have matching trace lines"
        # Two legitimate origins since S1b-02 AC2: an absence (SICK_CALL) or a
        # reserve bidder's displaced line (DISPLACED_LINE). Both must be
        # traceable; what must NOT happen is a chain with no origin at all.
        assert any(
            "SICK_CALL" in line or "DISPLACED_LINE" in line
            for line in chain["trace_lines"]
        )

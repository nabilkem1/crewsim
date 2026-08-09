import simpy

from crewsim import config
from crewsim.engine import des
from crewsim.engine.policy import load_policy
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


def _run(scenario_id=0, master_seed="unittest", trace=False):
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy("configs/policies/R10.yaml")
    return des.run_scenario(
        cfg, costs, policy, scenario_id=scenario_id, master_seed=master_seed,
        n_scenarios=1, trace=trace,
    )


def test_run_scenario_resolves_every_item():
    """Every OpenTimeItem must end in exactly one of reserve/draft/cancel --
    none left dangling in open_items once the horizon has run out."""
    sim = _run()
    assert len(sim.ledger.rows) > 0, "Should book at least the structural reserve-staffing cost"
    assert sim.open_items == {}, "No item should still be open after env.run() completes"


def test_run_scenario_produces_mixed_outcomes():
    """A degenerate pipeline (everything hits the same outcome) means a wiring
    bug upstream, not a real recovery process -- see S1d-04b2's history: before
    that fix, every single item failed legality and 100% cancelled."""
    sim = _run()
    categories = {row.category for row in sim.ledger.rows}
    assert "RESERVE_STAFFING" in categories, "Structural reserve cost must always be booked"
    assert categories & {"RESERVE_UTILIZATION", "DRAFT_TIER1", "DRAFT_TIER2", "DRAFT_TIER3",
                          "DRAFT_TIER4", "DRAFT_TIER5"}, (
        "At least one item should be resolved by reserve or draft, not just cancelled"
    )


def test_run_scenario_reproducible_under_crn():
    """Same master_seed + scenario_id must replay identically -- CRN is the
    whole point of paired-scenario comparison in S1d-04d."""
    sim1 = _run(master_seed="reproducible-key")
    sim2 = _run(master_seed="reproducible-key")
    rows1 = [(r.sim_time, r.event_uid, r.crew_id, r.category, r.amount) for r in sim1.ledger.rows]
    rows2 = [(r.sim_time, r.event_uid, r.crew_id, r.category, r.amount) for r in sim2.ledger.rows]
    assert rows1 == rows2


def test_different_master_seed_changes_outcome():
    """Sanity check that the rng is actually wired in, not a fixed sequence."""
    sim1 = _run(master_seed="seed-a")
    sim2 = _run(master_seed="seed-b")
    rows1 = [(r.sim_time, r.event_uid, r.crew_id, r.category, r.amount) for r in sim1.ledger.rows]
    rows2 = [(r.sim_time, r.event_uid, r.crew_id, r.category, r.amount) for r in sim2.ledger.rows]
    assert rows1 != rows2


def test_cascade_items_get_distinct_nonzero_uids():
    """cascade.py hands back OpenTimeItems with uid=0 by design ('engine must
    re-assign uid') -- the pipeline must give each a real, unique uid before
    booking, or two cascades from the same draft would collide in the ledger."""
    sim = _run(master_seed="cascade-uid-check")
    # (event_uid, category), not event_uid alone: since S1b-06 a cancellation
    # books TWO rows for the same event -- CANCELLATION and APPR_COMPENSATION,
    # a different payee and a different tariff. The invariant being guarded is
    # that two distinct ITEMS never share a uid, which duplicate
    # (uid, category) pairs would still catch: two colliding cascades would
    # each book the same category under the same uid.
    keys = [(row.event_uid, row.category) for row in sim.ledger.rows if row.event_uid != 0]
    assert len(keys) == len(set(keys)), "Two ledger rows share an (event_uid, category)"
    assert sim.n_cascading_drafts <= sim.n_drafts


def test_cascade_path_fires_end_to_end():
    """Over the real corpus at R10, the tier-1 (day-off) candidate pool is
    never exhausted, so n_cascading_drafts is 0 in every run_scenario() call
    above -- that leaves the cascade path (_attempt_resolution's `cascaded`
    branch, dataclasses.replace-based uid reassignment, _delayed_pipeline's
    visibility-lag wait) untouched by those tests. Force it directly: a
    single-candidate roster whose only legal draft choice also holds a future
    PAIRING inside the drafted duty's mandatory-rest window (same setup as
    test_cascade.py::test_future_pairing_mandatory_rest_cascade, which proves
    compute_draft_delta's own logic) -- draft has no choice but to break that
    pairing and cascade it.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)

    crew = CrewMember(
        crew_id="C1", base="YUL", fleet_quals={"A321neoLR"}, position="FO", seniority=1,
        calendar=[Block(start=1050.0, end=1200.0, btype=BlockType.PAIRING, pairing_id="P_FUTURE")],
    )
    item = OpenTimeItem(
        uid=1, pairing_id="P_DRAFT", base="YUL", fleet="A321neoLR", position="FO",
        start=800.0, end=900.0, deadline=700.0, origin="SICK_CALL", root_event_uid=1,
    )

    env = simpy.Environment()
    sim = des.Simulation(
        env, cfg, costs, policy_id="TEST", scenario_id=0, roster=[crew], reserves=[],
        rng=None, horizon_minutes=2000.0, trace=True,
    )
    # sick_call_source normally allocates item.uid via self._uid before the
    # item is created; mirror that here so next_uid() (used for the cascade)
    # doesn't hand out the uid this test already assigned to `item`.
    sim._uid = item.uid

    resolved = sim._attempt_resolution(item)
    assert resolved, "The only candidate is legal for the original item and must be drafted"
    assert sim.n_drafts == 1
    assert sim.n_cascading_drafts == 1, "Drafting C1 breaks their future P_FUTURE pairing -- must cascade"

    # The cascaded item was scheduled via env.process in _attempt_resolution;
    # it hasn't run yet. Drive the env far enough to resolve it (crew is now
    # fully booked -- DRAFTED_DUTY + REST cover P_FUTURE's slot -- so it can
    # only end in CANCELLATION at its own deadline, P_FUTURE.start - 60).
    env.run(until=2000.0)

    categories = [row.category for row in sim.ledger.rows]
    assert "CANCELLATION" in categories, "The cascaded item has nowhere to go once C1 is booked"
    event_uids = [row.event_uid for row in sim.ledger.rows]
    keys = [(uid, cat) for uid, cat in zip(event_uids, categories, strict=True)]
    assert len(keys) == len(set(keys)), "Original item (uid=1) and its cascade must not collide"
    assert 1 in event_uids
    assert any(uid not in (0, 1) for uid in event_uids), (
        "The cascaded item must get a real uid distinct from the original item it came from"
    )


def test_trace_only_recorded_when_enabled():
    sim_off = _run(trace=False)
    assert sim_off.trace == []

    sim_on = _run(trace=True)
    assert len(sim_on.trace) > 0

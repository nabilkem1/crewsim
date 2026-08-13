import types

from crewsim import config
from crewsim.engine import des
from crewsim.engine.ledger import CostLedger
from crewsim.reporting.cascade_analytics import compute_cascade_analytics


def _sim(scenario_id, rows, n_drafts=0, n_cascading_drafts=0,
         n_reserve_loss_cascades=0, n_reserve_blocks_lost=0):
    ledger = CostLedger()
    for row in rows:
        ledger.book(scenario_id=scenario_id, policy_id="P", **row)
    return types.SimpleNamespace(
        scenario_id=scenario_id, ledger=ledger, trace=[],
        n_drafts=n_drafts, n_cascading_drafts=n_cascading_drafts,
        n_reserve_loss_cascades=n_reserve_loss_cascades,
        n_reserve_blocks_lost=n_reserve_blocks_lost,
    )


def _row(t, event_uid, root_event_uid, category, amount, crew_id=None):
    return {"sim_time": t, "event_uid": event_uid, "root_event_uid": root_event_uid,
            "crew_id": crew_id, "category": category, "amount": amount}


def _in_window(cfg):
    warmup_end, _ = des.measurement_window_bounds(cfg)
    return warmup_end + 1.0


def test_amplification_compares_cascading_against_simple_chains():
    """The §5.5 claim as a number: a chain that cascaded against one that did not.

    Chain 1 is one item resolved by one draft ($500). Chain 2 shares a root
    across two items -- the draft that broke a future pairing, and the draft
    that then covered it ($800 + $700 = $1500). Amplification must be 3.0x,
    computed from the rows, not from any cascade parameter.
    """
    cfg = config.load()
    t = _in_window(cfg)
    sim = _sim(0, rows=[
        _row(t, 1, 1, "DRAFT_TIER1", 500.0),
        _row(t, 2, 2, "DRAFT_TIER2", 800.0),
        _row(t + 10, 3, 2, "DRAFT_TIER1", 700.0),  # cascade item, same root
    ], n_drafts=3, n_cascading_drafts=1)

    a = compute_cascade_analytics(cfg, [sim])
    assert a["n_chains"] == 2
    assert a["n_cascading_chains"] == 1
    assert a["mean_cost_simple_chain"] == 500.0
    assert a["mean_cost_cascading_chain"] == 1500.0
    assert a["amplification_ratio"] == 3.0
    assert a["chain_size_histogram"] == {"1": 1, "2": 1}
    assert a["max_chain_size"] == 2


def test_no_chain_sentinel_rows_are_never_grouped_into_a_chain():
    """root_event_uid == 0 means "no causal chain", not "one shared chain".

    RESERVE_STAFFING is booked daily regardless of any open item. Grouping
    those by root would collapse every background booking in the run into a
    single enormous fake cascade -- so this asserts they form no chain at all,
    which is the trap des.rows_in_measurement_window documents.
    """
    cfg = config.load()
    t = _in_window(cfg)
    sim = _sim(0, rows=[
        _row(t, 0, 0, "RESERVE_STAFFING", 250.0),
        _row(t + 1, 0, 0, "RESERVE_STAFFING", 250.0),
        _row(t + 2, 0, 0, "RESERVE_STAFFING", 250.0),
        _row(t + 3, 5, 5, "DRAFT_TIER1", 500.0),
    ], n_drafts=1)

    a = compute_cascade_analytics(cfg, [sim])
    assert a["n_chains"] == 1, "only the real chain counts; sentinel rows form none"
    assert a["n_cascading_chains"] == 0
    assert a["max_chain_size"] == 1


def test_amplification_is_none_rather_than_one_when_no_cascade_observed():
    """"None observed" and "cascades are free" are different statements.

    A 1.0x amplification would read as the second. This pins the first.
    """
    cfg = config.load()
    t = _in_window(cfg)
    sim = _sim(0, rows=[_row(t, 1, 1, "DRAFT_TIER1", 500.0)], n_drafts=1)

    a = compute_cascade_analytics(cfg, [sim])
    assert a["n_cascading_chains"] == 0
    assert a["amplification_ratio"] is None
    assert a["mean_cost_cascading_chain"] is None


def test_burstiness_is_reported_separately_from_the_mean_rate():
    """Cascades concentrate in a minority of scenarios, so the mean hides them.

    Two scenarios: one with no cascades, one where 4 of 10 drafts cascade. The
    mean rate (0.2) understates the only scenario that actually had any, so the
    concentration has to be carried alongside it.
    """
    cfg = config.load()
    sims = [
        _sim(0, rows=[], n_drafts=10, n_cascading_drafts=0),
        _sim(1, rows=[], n_drafts=10, n_cascading_drafts=4),
    ]
    a = compute_cascade_analytics(cfg, sims)
    assert a["cascade_rate_mean"] == 0.2
    assert a["cascade_rate_max"] == 0.4
    assert a["n_scenarios_with_cascade"] == 1
    assert a["share_of_scenarios_with_cascade"] == 0.5


def test_cascade_rate_uses_whole_simulation_counters_not_window_rows():
    """The rate and the economics come from different populations, on purpose.

    Here every ledger row sits in warm-up, so the measurement window has no
    chains at all -- but the counters still report the drafts, exactly as
    kpis.py's cascade_rate_mean and gate V4 do (those counters carry no
    root_event_uid, so they cannot be window-attributed). If this ever starts
    reporting 0.0, the two populations have been silently merged.
    """
    cfg = config.load()
    sim = _sim(0, rows=[_row(1.0, 1, 1, "DRAFT_TIER1", 500.0)],
               n_drafts=10, n_cascading_drafts=2)

    a = compute_cascade_analytics(cfg, [sim])
    assert a["n_chains"] == 0, "warm-up rows are outside the measurement window"
    assert a["cascade_rate_mean"] == 0.2, "but the counters are whole-simulation"
    assert a["drafts_total"] == 10


def test_scenario_with_no_drafts_does_not_become_a_zero_rate():
    """A scenario that never drafted has no cascade rate -- not a rate of 0.

    Averaging a 0 in for it would drag the mean toward zero using scenarios
    that could not have cascaded by construction (kpis.py guards this the same
    way with `if sim.n_drafts > 0`).
    """
    cfg = config.load()
    sims = [
        _sim(0, rows=[], n_drafts=0, n_cascading_drafts=0),
        _sim(1, rows=[], n_drafts=4, n_cascading_drafts=2),
    ]
    a = compute_cascade_analytics(cfg, sims)
    assert a["n_scenarios_with_drafts"] == 1
    assert a["cascade_rate_mean"] == 0.5
    assert a["per_scenario"][0]["rate"] is None


def test_uncovered_chain_is_flagged_and_exemplars_rank_by_cost():
    cfg = config.load()
    t = _in_window(cfg)
    sim = _sim(0, rows=[
        # cheap cascading chain
        _row(t, 1, 1, "DRAFT_TIER2", 800.0),
        _row(t + 1, 2, 1, "DRAFT_TIER1", 500.0),
        # expensive cascading chain, ending uncovered
        _row(t, 3, 3, "DRAFT_TIER2", 800.0),
        _row(t + 1, 4, 3, "CANCELLATION", 25000.0),
    ], n_drafts=3, n_cascading_drafts=2)

    a = compute_cascade_analytics(cfg, [sim])
    assert a["n_uncovered_chains"] == 1
    assert [c["root_event_uid"] for c in a["exemplar_chains"]] == [3, 1]
    assert a["exemplar_chains"][0]["cost"] == 25800.0
    assert a["exemplar_chains"][0]["uncovered"] is True
    assert a["exemplar_chains"][1]["uncovered"] is False


def test_output_is_json_serialisable_so_it_survives_the_joblib_boundary():
    """grid._run_one_policy returns this across a joblib process boundary and
    the API stores it as JSON; a numpy scalar or a Counter would break one or
    both, and only at runtime."""
    import json

    cfg = config.load()
    t = _in_window(cfg)
    sim = _sim(0, rows=[
        _row(t, 1, 1, "DRAFT_TIER2", 800.0),
        _row(t + 1, 2, 1, "DRAFT_TIER1", 500.0),
        _row(t, 3, 3, "DRAFT_TIER1", 500.0),  # a simple chain, so a ratio exists
    ], n_drafts=3, n_cascading_drafts=1)

    round_tripped = json.loads(json.dumps(compute_cascade_analytics(cfg, [sim])))
    assert round_tripped["amplification_ratio"] == 2.6
    assert round_tripped["chain_size_histogram"] == {"1": 1, "2": 1}

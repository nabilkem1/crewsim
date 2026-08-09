import types

from crewsim import config
from crewsim.engine import des
from crewsim.engine.eligibility import EligibilityEngine
from crewsim.engine.ledger import CostLedger
from crewsim.engine.policy import load_policy
from crewsim.reporting.kpis import _gini, compute_kpis


def _fake_sim(cfg, rows, eligibility_samples_with_time=(), n_drafts=0, n_cascading_drafts=0):
    ledger = CostLedger()
    for row in rows:
        ledger.book(scenario_id=0, policy_id="P", **row)
    elig = EligibilityEngine()
    for f, t in eligibility_samples_with_time:
        elig.samples.append(f)
        elig._sample_times.append(t)
    return types.SimpleNamespace(ledger=ledger, elig=elig, n_drafts=n_drafts, n_cascading_drafts=n_cascading_drafts)


def test_gini_perfectly_even_is_zero():
    assert _gini([5, 5, 5, 5]) == 0.0

def test_gini_single_recipient_is_near_one():
    # All drafts go to one of n crew -- Gini approaches (n-1)/n as the count grows.
    g = _gini([0, 0, 0, 10])
    assert g > 0.7

def test_gini_empty_is_zero():
    assert _gini([]) == 0.0

def test_compute_kpis_excludes_warmup_and_attributes_cooldown():
    """S1e-01's own acceptance criterion, exercised end-to-end through
    compute_kpis (not just measured_window_costs): a warm-up-booked
    CANCELLATION must not count as an uncovered leg, and a cool-down-booked
    draft whose root event fired in-window must still count as a draft."""
    cfg = config.load()
    warmup_end, measurement_end = des.measurement_window_bounds(cfg)

    rows = [
        # warm-up: booked and excluded
        {"sim_time": 0.0, "event_uid": 1, "root_event_uid": 1, "crew_id": None,
             "category": "CANCELLATION", "amount": 25000.0},
        # in-window: a draft, counted
        {"sim_time": warmup_end + 5.0, "event_uid": 2, "root_event_uid": 2, "crew_id": "C1",
             "category": "DRAFT_TIER1", "amount": 500.0},
        # in-window: a reserve dispatch, counted
        {"sim_time": warmup_end + 6.0, "event_uid": 3, "root_event_uid": 3, "crew_id": "C2",
             "category": "RESERVE_UTILIZATION", "amount": 250.0},
        # cool-down, root fired in-window (a cascade's terminal penalty realized late) -- counted
        {"sim_time": measurement_end + 200.0, "event_uid": 4, "root_event_uid": 2, "crew_id": None,
             "category": "TERMINAL_PENALTY", "amount": 37500.0},
        # cool-down, root ALSO in cool-down (a brand-new sick call) -- excluded
        {"sim_time": measurement_end + 10.0, "event_uid": 5, "root_event_uid": 5, "crew_id": "C3",
             "category": "DRAFT_TIER1", "amount": 500.0},
    ]
    sim = _fake_sim(cfg, rows, n_drafts=2, n_cascading_drafts=1)
    result = compute_kpis(cfg, [sim])

    # 1 CANCELLATION excluded (warm-up) + 1 TERMINAL_PENALTY included (cool-down, in-window root) = 1
    assert result["uncovered_legs_mean"] == 1.0
    # C1's in-window draft counted; C3's cool-down-originated draft excluded
    assert result["total_draft_events"] == 1
    assert result["draft_counts_by_crew"] == {"C1": 1}
    assert result["reserve_dispatches_mean"] == 1.0
    assert result["reserve_dollars_mean"] == 250.0
    # cost: 500 (draft) + 250 (reserve) + 37500 (terminal penalty pulled back) = 38250
    assert result["expected_cost"] == 38250.0

def test_compute_kpis_eligibility_window_filtered():
    cfg = config.load()
    warmup_end, measurement_end = des.measurement_window_bounds(cfg)
    sim = _fake_sim(
        cfg, rows=[],
        eligibility_samples_with_time=[
            (0.9, warmup_end - 1.0),          # warm-up, excluded
            (0.5, warmup_end + 1.0),          # in-window, included
            (0.1, measurement_end + 1.0),     # cool-down, excluded (eligibility has no root-attribution)
        ],
    )
    result = compute_kpis(cfg, [sim])
    assert result["eligibility_n_samples"] == 1
    assert result["eligibility_mean"] == 0.5

def test_compute_kpis_no_drafts_or_eligibility_events():
    """Empty inputs must not crash -- report n/a rather than div-by-zero."""
    cfg = config.load()
    sim = _fake_sim(cfg, rows=[], n_drafts=0)
    result = compute_kpis(cfg, [sim])
    assert result["draft_gini"] == 0.0
    assert result["draft_max"] == 0
    assert result["eligibility_mean"] is None
    assert result["cascade_rate_mean"] is None

def test_compute_kpis_real_scenarios():
    """Real, small-scale smoke test: the real CRN pipeline end to end,
    proving the window filter does non-trivial real work (fewer window-
    attributed draft events than the whole-horizon n_drafts counter)."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    sims = des.run_policy_crn(cfg, costs, policy, 2, "master")

    result = compute_kpis(cfg, sims)
    assert result["n_scenarios"] == 2
    assert result["expected_cost"] > 0.0
    assert result["cvar95"] >= result["expected_cost"]
    assert 0.0 <= result["draft_gini"] <= 1.0
    assert result["total_draft_events"] < sum(s.n_drafts for s in sims)
    if result["eligibility_mean"] is not None:
        assert 0.0 <= result["eligibility_mean"] <= 1.0

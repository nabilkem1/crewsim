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

def test_compute_kpis_cost_by_category_sums_to_expected_cost():
    """WN-002: the decomposition must be a real partition of the same total
    already shown as expected_cost -- not a second, independently-summed
    figure that could silently drift from it."""
    cfg = config.load()
    warmup_end, _ = des.measurement_window_bounds(cfg)
    rows = [
        {"sim_time": warmup_end + 1.0, "event_uid": 1, "root_event_uid": 1, "crew_id": "C1",
             "category": "DRAFT_TIER1", "amount": 500.0},
        {"sim_time": warmup_end + 2.0, "event_uid": 2, "root_event_uid": 2, "crew_id": "C2",
             "category": "DRAFT_TIER1", "amount": 500.0},
        {"sim_time": warmup_end + 3.0, "event_uid": 3, "root_event_uid": 3, "crew_id": "C3",
             "category": "RESERVE_UTILIZATION", "amount": 250.0},
        {"sim_time": warmup_end + 4.0, "event_uid": 4, "root_event_uid": 4, "crew_id": None,
             "category": "CANCELLATION", "amount": 25000.0},
    ]
    sim_a = _fake_sim(cfg, rows)
    # A second scenario with a DIFFERENT category present, to prove averaging
    # divides by n_scenarios (2), not by however many scenarios booked that
    # category.
    sim_b = _fake_sim(cfg, rows=[
        {"sim_time": warmup_end + 1.0, "event_uid": 1, "root_event_uid": 1, "crew_id": None,
             "category": "RESERVE_STAFFING", "amount": 1000.0},
    ])
    result = compute_kpis(cfg, [sim_a, sim_b])

    assert result["cost_by_category"]["DRAFT_TIER1"] == 500.0  # (1000 + 0) / 2 scenarios
    assert result["cost_by_category"]["RESERVE_UTILIZATION"] == 125.0  # (250 + 0) / 2
    assert result["cost_by_category"]["CANCELLATION"] == 12500.0  # (25000 + 0) / 2
    assert result["cost_by_category"]["RESERVE_STAFFING"] == 500.0  # (0 + 1000) / 2
    assert sum(result["cost_by_category"].values()) == result["expected_cost"]
    # No category that never actually booked a row anywhere -- e.g. TERMINAL_PENALTY.
    assert "TERMINAL_PENALTY" not in result["cost_by_category"]


def test_compute_kpis_delay_ambient_is_the_one_deliberate_exception_to_that_sum():
    """DELAY_AMBIENT is the single category this codebase deliberately keeps
    OUT of expected_cost/cvar95 (des.EXCLUDED_FROM_OPTIMISED_COST) while still
    showing it in cost_by_category -- so for a run that books it, the
    previous test's invariant (sum(cost_by_category) == expected_cost) does
    NOT hold, on purpose. Asserted explicitly so nobody re-derives that
    invariant as a general rule and "fixes" this exclusion by accident."""
    cfg = config.load()
    warmup_end, _ = des.measurement_window_bounds(cfg)
    rows = [
        {"sim_time": warmup_end + 1.0, "event_uid": 0, "root_event_uid": 0, "crew_id": "C1",
             "category": "DRAFT_TIER1", "amount": 500.0},
        {"sim_time": warmup_end + 2.0, "event_uid": 0, "root_event_uid": 0, "crew_id": None,
             "category": "DELAY_AMBIENT", "amount": 5000.0},
    ]
    sim = _fake_sim(cfg, rows)
    result = compute_kpis(cfg, [sim])

    assert result["cost_by_category"]["DELAY_AMBIENT"] == 5000.0
    assert result["expected_cost"] == 500.0
    assert sum(result["cost_by_category"].values()) != result["expected_cost"]


def test_compute_kpis_utilization_rate_from_real_reserve_staffing_rows():
    """WN-003: utilization_rate's denominator is the real count of
    RESERVE_STAFFING rows booked (one per reserve per covered day), not a
    hand-parsed reading of a policy YAML."""
    cfg = config.load()
    warmup_end, _ = des.measurement_window_bounds(cfg)
    rows = [
        {"sim_time": warmup_end + 1.0, "event_uid": 1, "root_event_uid": 1, "crew_id": "C1",
             "category": "RESERVE_UTILIZATION", "amount": 250.0},
    ]
    # 4 RESERVE_STAFFING rows (4 reserve-days bought), 1 actual dispatch.
    for i, crew in enumerate(["R1", "R1", "R2", "R2"], start=10):
        rows.append({"sim_time": warmup_end + i, "event_uid": i, "root_event_uid": i,
                      "crew_id": crew, "category": "RESERVE_STAFFING", "amount": 250.0})
    sim = _fake_sim(cfg, rows)
    result = compute_kpis(cfg, [sim])

    assert result["reserve_staffing_days_mean"] == 4.0
    assert result["reserve_dispatches_mean"] == 1.0
    assert result["utilization_rate"] == 0.25


def test_reserve_usage_is_split_by_call_type_and_flags_paid_but_unused():
    """IMP-117: SC/LC reserve-days paid and assignments used are reported
    separately, and a call type that is paid for but never used is flagged."""
    cfg = config.load()
    warmup_end, _ = des.measurement_window_bounds(cfg)
    rows = [
        {"sim_time": warmup_end + 1.0, "event_uid": 0, "root_event_uid": 0, "crew_id": "S1",
         "category": "RESERVE_STAFFING", "amount": 250.0},
        {"sim_time": warmup_end + 1.0, "event_uid": 0, "root_event_uid": 0, "crew_id": "L1",
         "category": "RESERVE_STAFFING", "amount": 180.0},
        {"sim_time": warmup_end + 2.0, "event_uid": 7, "root_event_uid": 7, "crew_id": "S1",
         "category": "RESERVE_UTILIZATION", "amount": 100.0},
    ]
    sim = _fake_sim(cfg, rows)
    types_by_key = {
        ("S1", warmup_end + 1.0, 0): "SC",
        ("L1", warmup_end + 1.0, 0): "LC",
        ("S1", warmup_end + 2.0, 7): "SC",
    }
    sim.reserve_call_type_of = lambda r: types_by_key.get((r.crew_id, r.sim_time, r.event_uid))

    result = compute_kpis(cfg, [sim])
    usage = result["reserve_by_call_type"]
    assert usage["SC"] == {"staffing_days_mean": 1.0, "staffing_dollars_mean": 250.0, "assignments_mean": 1.0}
    assert usage["LC"] == {"staffing_days_mean": 1.0, "staffing_dollars_mean": 180.0, "assignments_mean": 0.0}
    assert result["unused_paid_call_types"] == ["LC"]


def test_real_simulation_records_a_call_type_for_every_reserve_row():
    """IMP-117: the engine's side table covers every RESERVE_STAFFING and
    RESERVE_UTILIZATION row it books, so the split above is never partial."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    sim = des.run_scenario(cfg, costs, policy, scenario_id=0, n_scenarios=1)
    reserve_rows = [r for r in sim.ledger.rows
                    if r.category in ("RESERVE_STAFFING", "RESERVE_UTILIZATION")]
    assert reserve_rows
    assert all(sim.reserve_call_type_of(r) in ("SC", "LC") for r in reserve_rows)


def test_compute_kpis_utilization_rate_none_when_no_reserves_staffed():
    cfg = config.load()
    sim = _fake_sim(cfg, rows=[])
    result = compute_kpis(cfg, [sim])
    assert result["reserve_staffing_days_mean"] == 0.0
    assert result["utilization_rate"] is None


def test_compute_kpis_service_level_uses_the_real_configured_threshold():
    """The real loaded config (not a mock) carries service_level (WN-004);
    this proves compute_kpis reads it rather than a hardcoded assumption."""
    cfg = config.load()
    assert cfg.service_level is not None  # would fail loudly if configs/base.yaml regressed
    warmup_end, _ = des.measurement_window_bounds(cfg)

    def _cancellations(n: int, offset: int):
        return [
            {"sim_time": warmup_end + offset + i, "event_uid": offset + i, "root_event_uid": offset + i,
             "crew_id": None, "category": "CANCELLATION", "amount": 25000.0}
            for i in range(n)
        ]

    # u_max=3: a scenario with 4 uncovered legs (cancellations) exceeds it,
    # one with 1 does not.
    sim_over = _fake_sim(cfg, rows=_cancellations(4, 0))
    sim_under = _fake_sim(cfg, rows=_cancellations(1, 100))
    result = compute_kpis(cfg, [sim_over, sim_under])

    assert result["service_level"]["u_max"] == cfg.service_level.u_max
    assert result["service_level"]["epsilon"] == cfg.service_level.epsilon
    assert result["service_level"]["p_uncovered_exceeds_u_max"] == 0.5  # 1 of 2 scenarios
    assert result["service_level"]["service_level_met"] is False  # 0.5 > epsilon (0.05)


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

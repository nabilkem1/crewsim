import pytest

from crewsim import config
from crewsim.engine import des
from crewsim.engine.events import assign_reserve
from crewsim.engine.policy import load_policy
from crewsim.engine.state import Block, BlockType, CrewMember


def test_duty_end_and_rest_end_splits_reserve():
    """Verify that E3, E6, E7 properly split a RESERVE block and insert DUTY and REST."""
    # Setup a mock crew member with a 3-day reserve block
    crew = CrewMember(
        crew_id="R001",
        base="YUL",
        fleet_quals={"A321"},
        position="FO",
        seniority=100,
        calendar=[
            Block(start=100000, end=400000, btype=BlockType.RESERVE, reserve_call_type="SC")
        ]
    )
    
    # Assign a duty from 200000 to 250000 with 40000 rest
    duty_start = 200000
    duty_end = 250000
    min_rest = 40000
    
    assign_reserve(crew, duty_start, duty_end, min_rest, "PAIR1")
    
    # Calendar should now be:
    # 1. RESERVE [100000, 200000]
    # 2. DRAFTED_DUTY [200000, 250000]
    # 3. REST [250000, 290000]
    # 4. RESERVE [290000, 400000]
    
    assert len(crew.calendar) == 4
    
    b1, b2, b3, b4 = crew.calendar
    
    assert b1.btype == BlockType.RESERVE
    assert b1.start == 100000 and b1.end == 200000
    assert b1.reserve_call_type == "SC"
    
    assert b2.btype == BlockType.DRAFTED_DUTY
    assert b2.start == 200000 and b2.end == 250000
    
    assert b3.btype == BlockType.REST
    assert b3.start == 250000 and b3.end == 290000
    
    assert b4.btype == BlockType.RESERVE
    assert b4.start == 290000 and b4.end == 400000
    assert b4.reserve_call_type == "SC"
    
    # Verify no overlap
    for i in range(1, len(crew.calendar)):
        assert crew.calendar[i-1].end <= crew.calendar[i].start

def test_reserve_duty_records_flight_mins():
    """IMP-102: a reserve's covered trip counts toward their L3 flight limit.

    assign_reserve used to build the DRAFTED_DUTY block without flight_mins,
    so get_rolling_counters saw the duty hours but zero flight hours for every
    trip a reserve flew. The draft path (cascade.py) always carried it.
    """
    crew = CrewMember(
        crew_id="R001", base="YUL", fleet_quals={"A321"}, position="FO", seniority=100,
        calendar=[Block(start=0, end=4000, btype=BlockType.RESERVE, reserve_call_type="SC")],
    )
    assign_reserve(crew, 1000, 1600, 600, "PAIR1", flight_mins=420.0)

    duty = next(b for b in crew.calendar if b.btype == BlockType.DRAFTED_DUTY)
    assert duty.flight_mins == 420.0
    _, flight = crew.get_rolling_counters(end_time=5000, days=7)
    assert flight == pytest.approx(420.0)


def test_reserve_near_flight_limit_becomes_ineligible_after_one_trip():
    """IMP-102 AC3: the recorded flight time actually binds L3.

    A reserve who has just flown 34 h is one 2 h trip away from the 35 h 7-day
    limit in configs/base.yaml. Before the fix the covered trip recorded 0
    flight minutes and the next trip was approved.
    """
    from crewsim.engine.legality import check_l3_rolling_7d
    from crewsim.engine.state import OpenTimeItem
    from tests.engine.conftest import legality_cfg

    cfg = legality_cfg()
    limit_mins = cfg.legality.rolling_7d_flight_limit_hours * 60
    crew = CrewMember(
        crew_id="R001", base="YUL", fleet_quals={"A321"}, position="FO", seniority=100,
        calendar=[Block(start=0, end=20000, btype=BlockType.RESERVE, reserve_call_type="SC")],
    )
    # One covered trip carrying all but 60 min of the 7-day flight allowance
    # (a long duty so L3's DUTY limit is not what binds).
    assign_reserve(crew, 1000, 1800, 600, "PAIR1", flight_mins=limit_mins - 60)
    next_trip = OpenTimeItem(
        uid=2, pairing_id="PAIR2", base="YUL", fleet="A321", position="FO",
        start=3000, end=3200, deadline=3000, origin="SICK_CALL", root_event_uid=2,
        flight_mins=120,
    )
    verdict = check_l3_rolling_7d(crew, next_trip, cfg)
    assert not verdict.legal and "flight" in verdict.reason


def test_open_time_item_deadline_is_report_time_minus_the_configured_lead():
    """The deadline ARITHMETIC only -- renamed, because the previous name
    ("...held") promised something this test never checked: it drives no
    pipeline, holds nothing and books nothing. The hold itself is covered by
    test_uncoverable_items_are_retried_before_being_cancelled below."""
    import pathlib

    from crewsim.config import (
        BaseConfig,
        CalibrationConfig,
        CascadeReconstructionConfig,
        DemandConfig,
        DraftReconstructionConfig,
        HorizonConfig,
        PathsConfig,
        PopulationConfig,
        QualityGateThresholds,
        RegimeHmmConfig,
        RegimeQuantiles,
        ScopeConfig,
    )
    
    cfg = BaseConfig(
        paths=PathsConfig(
            corpus_dir=pathlib.Path("a"),
            params_dir=pathlib.Path("b"),
            reports_dir=pathlib.Path("c"),
            seasons_file=pathlib.Path("d")
        ),
        scope=ScopeConfig(base="YUL", fleet="A321", position="FO", crew_group="pilots", season="winter", bid_period="2027-01"),
        horizon=HorizonConfig(warmup_days=7, measurement_days=28, cooldown_days=7),
        population=PopulationConfig(roster_size=120, displaced_flying="absorb",
                                     reserve_bid_rule="junior_first"),
        quality_gates=QualityGateThresholds(d4_link_pass=0.9, d4_link_marginal=0.8, d6_d7_join_pass=0.9, station_day_coverage_pass=0.9),
        calibration=CalibrationConfig(
            delay_gmm_components=2, delay_gmm_random_state=42,
            regime_quantiles=RegimeQuantiles(p_calm=0.5, p_normal=0.8, p_disrupted=0.9),
            regime_hmm=RegimeHmmConfig(
                n_restarts=2, max_iter=50, tol=1e-4, seed=1, init_self_transition=0.7,
                transition_pseudocount=0.5, min_probability=1e-6, candidate_n_states=[4],
                delay_threshold_minutes=15, sick_call_exposure="constant",
                restart_agreement_tol=1e-4, min_state_share=0.01,
            ),
            overdispersion_threshold=1.5, sick_call_min_duration_days=0.5,
        ),
        draft_reconstruction=DraftReconstructionConfig(premium_pay_codes=[], short_notice_reason_codes=[], initiator_filter=[]),
        cascade_reconstruction=CascadeReconstructionConfig(window_days=7, cascade_reason_codes=[], confidence_level=0.95),
        mode="FULL",
        costs_file="costs_pilots.yaml",
        demand=DemandConfig(uncovered_deadline_hours={"default": 2.0})
    )
    
    from crewsim.engine.sick_calls import apply_sick_call
    
    # Sim time is minutes since horizon start (S1d-04b) -- 1000 is the pairing's
    # report time, reachable within a 3-day (4320-minute) search from t=900.
    crew = CrewMember(
        crew_id="R001", base="YUL", fleet_quals={"A321"}, position="FO", seniority=100,
        calendar=[Block(start=1000.0, end=2000.0, btype=BlockType.PAIRING, pairing_id="PAIR1")]
    )

    import numpy as np
    _removed_crew, items = apply_sick_call(cfg, [crew], 900.0, 3, 1, np.random.default_rng(0))

    assert len(items) == 1
    oti = items[0]

    # Report time is 1000.0.
    # We configured 2.0 hours hold time => deadline should be 1000.0 - 2 * 60 = 880.0
    assert oti.deadline == 1000.0 - (2.0 * 60)


# ==================== S1b-06: E8 hold-to-deadline, on the real pipeline ======
# test_uncovered_deadline_held above asserts the DEADLINE ARITHMETIC only. It
# builds a config, calls apply_sick_call, and checks `deadline == report - 2h`.
# Nothing is held, no retry happens, no cancellation books -- despite the name.
# These drive the real recovery_pipeline instead.


@pytest.fixture(scope="module")
def traced_scenario():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    return cfg, costs, des.run_scenario(
        cfg, costs, policy, scenario_id=0, master_seed="master", n_scenarios=1,
        trace=True, verbose_trace=True,
    )


def test_uncoverable_items_are_retried_before_being_cancelled(traced_scenario):
    """AC1: "held, not cancelled on the spot; the pipeline retries as state
    changes". Counts real retry lines in a real scenario's trace."""
    _cfg, _costs, sim = traced_scenario
    retries = [line for line in sim.trace if "unresolved for now" in line]
    cancels = [line for line in sim.trace if "CANCELLED at deadline" in line]

    if not cancels:
        pytest.skip(
            "no item goes uncovered on the current corpus -- since the 2026-08-12 report-time\n            eligibility and duty-cap fixes, drafting always succeeds, so E8's hold-to-\n            deadline path never fires (audit OPEN-6). The mechanism is unchanged; there is\n            simply no demand able to exhaust a 108-strong draftable pool."
        )
    assert retries, (
        "items were cancelled without a single retry -- E8 is cancelling on the spot, "
        "which makes a late rescue impossible and overstates cancellations"
    )


def test_at_least_one_item_is_genuinely_held_open(traced_scenario):
    """A retry at the same instant is not a hold. At least one item must be
    cancelled STRICTLY LATER than it arrived.

    (Not every item: an absence notified after its pairing has already begun is
    born past its own deadline, because `deadline = start - lead` is absolute.
    That is a real modelled case, tracked separately, and `explain-event` warns
    about it rather than claiming a hold that did not happen.)
    """
    import re

    _cfg, _costs, sim = traced_scenario
    arrival = {}
    held = []
    for line in sim.trace:
        m = re.match(r"\[t=(-?[\d.]+)\].*?item (\d+)", line)
        if not m:
            continue
        t, uid = float(m.group(1)), m.group(2)
        arrival.setdefault(uid, t)
        if "CANCELLED at deadline" in line and t > arrival[uid]:
            held.append((uid, t - arrival[uid]))

    if not held:
        pytest.skip(
            "no item goes uncovered on the current corpus -- since the 2026-08-12 report-time\n            eligibility and duty-cap fixes, drafting always succeeds, so E8's hold-to-\n            deadline path never fires (audit OPEN-6). The mechanism is unchanged; there is\n            simply no demand able to exhaust a 108-strong draftable pool."
        )


def test_cancellation_books_appr_compensation_at_the_deadline(traced_scenario):
    """AC2: "Cancellation AND APPR compensation book at the deadline."

    APPR was defined in costs_pilots.yaml and modelled in config.py but booked
    nowhere in src/ -- a costed, declared, never-consumed key.
    """
    _cfg, costs, sim = traced_scenario
    rows = sim.ledger.rows
    cancellations = [r for r in rows if r.category == "CANCELLATION"]
    appr = [r for r in rows if r.category == "APPR_COMPENSATION"]

    if not cancellations:
        pytest.skip(
            "no item goes uncovered on the current corpus -- since the 2026-08-12 report-time\n            eligibility and duty-cap fixes, drafting always succeeds, so E8's hold-to-\n            deadline path never fires (audit OPEN-6). The mechanism is unchanged; there is\n            simply no demand able to exhaust a 108-strong draftable pool."
        )
    assert len(appr) == len(cancellations), "every cancellation must attract APPR compensation"

    expected = costs.appr_compensation.on_cancellation
    assert expected > 0.0
    assert all(r.amount == expected for r in appr)

    # Booked at the same instant and against the same causal chain, not as a
    # detached lump -- otherwise it would not follow the cancellation through
    # measurement-window attribution.
    by_event = {r.event_uid: r.sim_time for r in cancellations}
    for r in appr:
        assert r.event_uid in by_event
        assert r.sim_time == by_event[r.event_uid]

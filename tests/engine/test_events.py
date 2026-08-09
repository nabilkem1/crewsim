from crewsim.engine.events import assign_reserve
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

def test_uncovered_deadline_held():
    """Verify that an uncovered item is held until its deadline instead of being cancelled immediately."""
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
        population=PopulationConfig(roster_size=120),
        quality_gates=QualityGateThresholds(d4_link_pass=0.9, d4_link_marginal=0.8, d6_d7_join_pass=0.9, d9_completeness_pass=0.9),
        calibration=CalibrationConfig(delay_gmm_components=2, delay_gmm_random_state=42, regime_quantiles=RegimeQuantiles(p_calm=0.5, p_normal=0.8, p_disrupted=0.9), overdispersion_threshold=1.5, sick_call_min_duration_days=0.5),
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

    _removed_crew, items = apply_sick_call(cfg, [crew], 900.0, 3, 1)

    assert len(items) == 1
    oti = items[0]

    # Report time is 1000.0.
    # We configured 2.0 hours hold time => deadline should be 1000.0 - 2 * 60 = 880.0
    assert oti.deadline == 1000.0 - (2.0 * 60)

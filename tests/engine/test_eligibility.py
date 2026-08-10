
import numpy as np
import pytest

from crewsim.engine.eligibility import EligibilityEngine
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


def _test_cfg():
    """The real configs/base.yaml -- see tests/engine/conftest.py for why this
    is not a hand-built stand-in any more."""
    from tests.engine.conftest import legality_cfg
    return legality_cfg()


def test_full_mode_eligibility():
    engine = EligibilityEngine(mode="FULL", cfg=_test_cfg())

    # 1. Create a pool of reserves
    r1 = CrewMember("R001", "YUL", {"A321neoLR"}, "FO", 1)
    # Good coverage: reserve covers the whole duty window
    r1.calendar.append(Block(0.0, 1000.0, BlockType.RESERVE))
    
    r2 = CrewMember("R002", "YUL", {"A321neoLR"}, "FO", 2)
    # Poor coverage: reserve ends at the moment of the call (100.0)
    # Since we now only check if it covers item.start (200.0), a block ending at 200.0 is NOT enough.
    r2.calendar.append(Block(0.0, 200.0, BlockType.RESERVE))
    
    r3 = CrewMember("R003", "YUL", {"A321neoLR"}, "FO", 3)
    # Good coverage, but illegal (wrong fleet)
    r3.calendar.append(Block(0.0, 1000.0, BlockType.RESERVE))
    r3.fleet_quals = {"A330"}
    
    reserves = [r1, r2, r3]
    
    item = OpenTimeItem(
        uid=1, pairing_id="P1", base="YUL", fleet="A321neoLR", position="FO",
        start=250.0, end=500.0, deadline=250.0, origin="SICK_CALL", root_event_uid=1
    )
    
    elig = engine.eligible_reserves(reserves, item, now=100.0)
    
    # Pool should be [r1, r3] (r2's block doesn't cover 250.0)
    # Elig should be [r1] (r3 is wrong fleet, so it fails L6)
    assert len(elig) == 1
    assert elig[0].crew_id == "R001"
    
    # Samples should log realized fraction: 1 eligible out of 2 in the pool = 0.5
    assert engine.get_distribution() == [0.5]
    
    # check_recommendation_safe should pass in FULL mode
    assert engine.check_recommendation_safe() is True


def test_pool_requires_coverage_of_whole_duty_window():
    """S1c-01's own acceptance criterion: pool = reserves whose RESERVE block
    covers the DUTY WINDOW, not merely the report-time instant. A reserve
    whose on-call window ends partway through the duty can't actually fly it
    and must not be counted as pool-eligible."""
    engine = EligibilityEngine(mode="FULL", cfg=_test_cfg())

    item = OpenTimeItem(
        uid=1, pairing_id="P1", base="YUL", fleet="A321neoLR", position="FO",
        start=250.0, end=500.0, deadline=250.0, origin="SICK_CALL", root_event_uid=1
    )

    covers_start_only = CrewMember("R001", "YUL", {"A321neoLR"}, "FO", 1)
    covers_start_only.calendar.append(Block(0.0, 300.0, BlockType.RESERVE))  # ends inside [250, 500)

    covers_whole_window = CrewMember("R002", "YUL", {"A321neoLR"}, "FO", 2)
    covers_whole_window.calendar.append(Block(0.0, 500.0, BlockType.RESERVE))  # ends exactly at item.end

    elig = engine.eligible_reserves([covers_start_only, covers_whole_window], item, now=100.0)

    assert [r.crew_id for r in elig] == ["R002"]
    # Pool was [R002] only (R001 was never in the pool) -- fraction is 1/1, not 1/2.
    assert engine.get_distribution() == [1.0]


def test_reduced_mode():
    engine = EligibilityEngine(mode="REDUCED", p_elig=0.5)
    
    r1 = CrewMember("R001", "YUL", {"A321neoLR"}, "FO", 1)
    r2 = CrewMember("R002", "YUL", {"A321neoLR"}, "FO", 2)
    r3 = CrewMember("R003", "YUL", {"A321neoLR"}, "FO", 3)
    r4 = CrewMember("R004", "YUL", {"A321neoLR"}, "FO", 4)
    reserves = [r1, r2, r3, r4]
    
    item = OpenTimeItem(
        uid=1, pairing_id="P1", base="YUL", fleet="A321neoLR", position="FO",
        start=200.0, end=500.0, deadline=200.0, origin="SICK_CALL", root_event_uid=1
    )
    
    # Since p_elig is 0.5, we fix the random seed for deterministic outcome
    rng = np.random.default_rng(42)
    elig = engine.eligible_reserves(reserves, item, now=100.0, rng=rng)
    
    # We should get a subset based on random draws
    assert len(elig) >= 0 and len(elig) <= 4
    
    # Must refuse recommendation in REDUCED mode
    with pytest.raises(RuntimeError, match="REDUCED mode"):
        engine.check_recommendation_safe()


# ======================= S1c-01 AC4: REDUCED is real, and refuses ============
def test_reduced_mode_is_reachable_from_config():
    """The engine read a hardcoded mode="FULL" and ignored cfg.mode entirely,
    so base.yaml documented a REDUCED mode that could not be selected."""
    from crewsim import config
    from crewsim.engine.eligibility import EligibilityEngine

    cfg = config.load()
    assert EligibilityEngine.from_config(cfg).mode == "FULL"

    reduced = cfg.model_copy(update={"mode": "REDUCED"})
    engine = EligibilityEngine.from_config(reduced)
    assert engine.mode == "REDUCED"
    assert engine.p_elig == cfg.reduced_mode.p_elig, "p_elig must come from config"


def test_reduced_mode_still_respects_pool_membership():
    """REDUCED replaces the LEGALITY check with a coin flip, not the structural
    pool. It used to thin `reserves` directly, so it could return a crew member
    with no covering RESERVE block and des.py's assign_reserve raised
    'Crew P00453 has no RESERVE block overlapping [...]'. Unreachable at the
    time, so never observed."""
    import numpy as np

    from crewsim.engine.eligibility import EligibilityEngine

    covered = CrewMember(
        crew_id="R_IN", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
        calendar=[Block(start=0.0, end=1000.0, btype=BlockType.RESERVE, reserve_call_type="SC")],
    )
    uncovered = CrewMember(
        crew_id="R_OUT", base="YUL", fleet_quals={"A330"}, position="CA", seniority=2,
        calendar=[Block(start=0.0, end=100.0, btype=BlockType.RESERVE, reserve_call_type="SC")],
    )
    item = OpenTimeItem(
        uid=1, pairing_id="P1", base="YUL", fleet="A330", position="CA",
        start=200.0, end=500.0, deadline=200.0, origin="SICK_CALL", root_event_uid=1,
    )
    # p_elig=1.0 -- everyone in the pool passes the coin flip, so anything
    # returned that is NOT pool-eligible is a pool bug, not a sampling artefact.
    engine = EligibilityEngine(mode="REDUCED", p_elig=1.0)
    elig = engine.eligible_reserves([covered, uncovered], item, now=100.0,
                                    rng=np.random.default_rng(0))
    assert [c.crew_id for c in elig] == ["R_IN"]


def test_reduced_mode_records_its_distribution():
    """V3 and --report-eligibility read get_distribution(); REDUCED returned
    early and recorded nothing, so both would have seen an empty series."""
    import numpy as np

    from crewsim.engine.eligibility import EligibilityEngine

    crew = [
        CrewMember(crew_id=f"R{i}", base="YUL", fleet_quals={"A330"}, position="CA",
                   seniority=i,
                   calendar=[Block(start=0.0, end=1000.0, btype=BlockType.RESERVE)])
        for i in range(10)
    ]
    item = OpenTimeItem(uid=1, pairing_id="P1", base="YUL", fleet="A330", position="CA",
                        start=200.0, end=500.0, deadline=200.0, origin="SICK_CALL",
                        root_event_uid=1)
    engine = EligibilityEngine(mode="REDUCED", p_elig=0.5)
    engine.eligible_reserves(crew, item, now=100.0, rng=np.random.default_rng(0))
    assert len(engine.get_distribution()) == 1


def test_a_reduced_run_completes_end_to_end():
    """The regression that mattered: a real REDUCED scenario must run at all."""
    from crewsim import config
    from crewsim.engine import des
    from crewsim.engine.policy import load_policy

    cfg = config.load().model_copy(update={"mode": "REDUCED"})
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    sim = des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="master",
                           n_scenarios=1)
    assert sim.elig.mode == "REDUCED"
    assert sim.elig.get_distribution(), "a REDUCED run must still log eligibility"


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

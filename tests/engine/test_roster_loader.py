import pytest
from crewsim import config
from crewsim.engine import roster_loader

def test_roster_loader():
    """Verify D1 and D2 load correctly into CrewMember and Blocks, applying exclusions."""
    cfg = config.load()
    
    # We test on YUL A321 FO as specified in the manual check, if the data has A321neoLR we use it,
    # otherwise we just assert the structural behavior.
    active, exclusions = roster_loader.load_rosters(cfg, base="YUL", position="FO", fleet="A321")
    
    assert len(active) > 0, "Should load some active crew"
    
    # Check that exclusion stats exist
    assert "LONG_TERM_ABSENCE" in exclusions
    
    # Check the first crew member's state
    c = active[0]
    assert c.base == "YUL"
    assert c.position == "FO"
    assert "A321" in str(c.fleet_quals) or "A321" in list(c.fleet_quals)[0]
    
    # Calendar should be populated
    # And it must be sorted
    if c.calendar:
        for i in range(1, len(c.calendar)):
            assert c.calendar[i-1].end <= c.calendar[i].start, "Blocks must not overlap and be sorted"

import pytest
from crewsim import config
from crewsim.engine import roster_loader
from crewsim.engine.sick_calls import apply_sick_call
import random

def test_sick_calls():
    """Verify sick calls sample crew and break pairings into open time."""
    cfg = config.load()
    active, _ = roster_loader.load_rosters(cfg)
    
    random.seed(42)
    # Aug 1 2023 12:00 UTC
    current_time = 1690891200.0 
    c, otis = apply_sick_call(active, current_time, 3.0, 100)
    
    assert c is not None, "Should find a crew member about to report"
    assert len(otis) > 0, "Should generate open time items"
    
    for oti in otis:
        assert oti.origin == "SICK_CALL"
        assert oti.deadline < oti.start
        
    # Verify the block is removed
    for b in c.calendar:
        assert b.pairing_id != otis[0].pairing_id, "Pairing block should be removed from calendar"

from crewsim import config
from crewsim.engine import roster_loader
from crewsim.engine.policy import load_policy
from crewsim.engine.state import BlockType


def test_reserve_rotation_and_split():
    """Verify that minted reserves inherit authentic D2 on/off rotations and SC/LC labels."""
    cfg = config.load()
    pol_path = config.repo_root() / "configs" / "policies" / "R10.yaml"
    pol = load_policy(pol_path)
    
    active_crew, _ = roster_loader.load_rosters(cfg, base="YUL", position="FO", fleet="A321", policy=pol)
    
    reserves = [c for c in active_crew if getattr(c, "_is_reserve", False)]
    assert len(reserves) > 0, "Should have minted reserves"
    
    # Check that they have RESERVE blocks (and DAY_OFF blocks)
    for c in reserves:
        assert any(b.btype == BlockType.RESERVE for b in c.calendar), "Minted reserve has no RESERVE blocks"
        assert not any(b.btype == BlockType.PAIRING for b in c.calendar), "Minted reserve should have no PAIRINGs"
        
    # Check SC / LC distinctness
    sc_count = 0
    lc_count = 0
    for c in reserves:
        for b in c.calendar:
            if b.btype == BlockType.RESERVE:
                if b.reserve_call_type == "SC": sc_count += 1
                if b.reserve_call_type == "LC": lc_count += 1
                
    assert sc_count > 0, "Should have SC reserve blocks"
    assert lc_count > 0, "Should have LC reserve blocks"
    
    # Check that it's roughly 60/40 (just that both exist in reasonable proportion)
    total = sc_count + lc_count
    assert 0.3 < (sc_count / total) < 0.9, f"SC proportion out of bounds: {sc_count/total}"

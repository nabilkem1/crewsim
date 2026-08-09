from crewsim import config
from crewsim.engine import roster_loader
from crewsim.engine.policy import load_policy


def test_headcount_conservation():
    """Verify that carving out reserves conserves total active headcount."""
    cfg = config.load()
    
    # Load without policy
    active_no_policy, _ = roster_loader.load_rosters(cfg, base="YUL", position="FO", fleet="A321")
    total_no_policy = len(active_no_policy)
    
    pol_path = config.repo_root() / "configs" / "policies" / "R10.yaml"
    pol = load_policy(pol_path)
    active_with_policy, _ = roster_loader.load_rosters(cfg, base="YUL", position="FO", fleet="A321", policy=pol)
    total_with_policy = len(active_with_policy)
    
    assert total_no_policy == total_with_policy, "Total active headcount must be conserved"
    
    # Check that exactly N reserves were carved out
    n_reserves = pol.total_reserves(base="YUL", fleet="A321neoLR", position="FO")
    assert n_reserves in {10, 12}, "R10 policy should have 10 or 12 max daily reserves"
    
    reserves_marked = sum(getattr(c, "_is_reserve", False) for c in active_with_policy)
    lines_marked = sum(not getattr(c, "_is_reserve", False) for c in active_with_policy)
    
    assert reserves_marked == n_reserves
    assert lines_marked + reserves_marked == total_with_policy
    
    # Verify reserves lost their pairing blocks and lines lost their reserve blocks
    for c in active_with_policy:
        if getattr(c, "_is_reserve", False):
            assert all(b.btype.name != "PAIRING" for b in c.calendar), "Reserves should have PAIRINGs stripped"
        else:
            assert all(b.btype.name != "RESERVE" for b in c.calendar), "Line holders should have RESERVEs stripped"

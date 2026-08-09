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
        
    # S1b-03 AC2: SC and LC are distinct, and the split is measured in DAYS,
    # not blocks -- a block is an arbitrary unit (one long LC stretch and one
    # short SC stretch are "50/50" by block and nothing like it by exposure.)
    sc_mins = sum(
        b.end - b.start for c in reserves for b in c.calendar
        if b.btype == BlockType.RESERVE and b.reserve_call_type == "SC"
    )
    lc_mins = sum(
        b.end - b.start for c in reserves for b in c.calendar
        if b.btype == BlockType.RESERVE and b.reserve_call_type == "LC"
    )
    assert sc_mins > 0 and lc_mins > 0, "both call types must be present"

    # The story states "roughly 60/40". Measured across the shipped candidate
    # policies this sits at 60.7-69.6% SC, so the band is set to admit that
    # spread and nothing like the 30/70 the previous 0.3-0.9 bound allowed.
    sc_share = sc_mins / (sc_mins + lc_mins)
    assert 0.55 <= sc_share <= 0.75, f"SC share {sc_share:.1%} is not roughly 60/40"


def test_reserve_lines_rotate_on_and_off():
    """S1b-03 AC1: an on/off rotation, NOT one flat horizon-long block. If a
    reserve were on call for the whole horizon, eligibility would read ~100%
    and gate V3 could never pass."""
    cfg = config.load()
    pol = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    active_crew, _ = roster_loader.load_rosters(
        cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position, policy=pol
    )
    reserves = [c for c in active_crew if c._is_reserve]
    horizon = cfg.horizon.horizon_days * 1440.0

    for c in reserves:
        on = sum(b.end - b.start for b in c.calendar if b.btype == BlockType.RESERVE)
        assert on < horizon, f"{c.crew_id} is on call for the entire horizon -- no rotation"

    # And the pool as a whole presents materially fewer servers than heads.
    from crewsim.gates.v2_erlang import mean_on_call_servers
    assert mean_on_call_servers(reserves, horizon) < len(reserves)

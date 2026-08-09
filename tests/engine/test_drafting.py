from crewsim.engine.drafting import determine_tier, select_draft_candidate
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


def _test_cfg():
    """The real configs/base.yaml -- see tests/engine/conftest.py for why this
    is not a hand-built stand-in any more."""
    from tests.engine.conftest import legality_cfg
    return legality_cfg()

def _test_crew(id_num: int, sen: int, blocks=None):
    return CrewMember(
        crew_id=f"C{id_num:04d}", base="YUL", fleet_quals={"A321neoLR"}, position="FO",
        seniority=sen, calendar=blocks or []
    )

def _test_duty(start=100.0, end=200.0):
    return OpenTimeItem(
        uid=1, pairing_id="P1", base="YUL", fleet="A321neoLR", position="FO",
        start=start, end=end, deadline=start-10, origin="SICK_CALL", root_event_uid=1
    )

def test_determine_tier():
    duty = _test_duty(start=100.0, end=200.0)
    
    # Tier 1: No duty
    c1 = _test_crew(1, 10)
    assert determine_tier(c1, duty, _test_cfg()) == 1
    
    # Tier 2: PAIRING
    c2 = _test_crew(2, 20, [Block(start=150.0, end=250.0, btype=BlockType.PAIRING)])
    assert determine_tier(c2, duty, _test_cfg()) == 2
    
    # Tier 3: TRAINING
    c3 = _test_crew(3, 30, [Block(start=50.0, end=150.0, btype=BlockType.TRAINING)])
    assert determine_tier(c3, duty, _test_cfg()) == 3
    
    # Tier 4: VACATION
    c4 = _test_crew(4, 40, [Block(start=0.0, end=300.0, btype=BlockType.VACATION)])
    assert determine_tier(c4, duty, _test_cfg()) == 4

def test_select_senior_first():
    duty = _test_duty()
    
    c_tier1_sen10 = _test_crew(1, 10)
    c_tier1_sen5 = _test_crew(2, 5)   # More senior (lower number)
    c_tier2_sen1 = _test_crew(3, 1, [Block(start=150.0, end=250.0, btype=BlockType.PAIRING)]) # Most senior, but Tier 2
    
    roster = [c_tier1_sen10, c_tier2_sen1, c_tier1_sen5]

    # Should pick Tier 1 over Tier 2, and sen5 over sen10
    chosen = select_draft_candidate(roster, duty, cfg=_test_cfg())
    assert chosen is not None
    assert chosen.crew_id == "C0002"
    assert chosen.seniority == 5

def test_select_junior_first_counterfactual():
    duty = _test_duty()
    
    c_tier1_sen10 = _test_crew(1, 10)
    c_tier1_sen5 = _test_crew(2, 5)
    c_tier2_sen1 = _test_crew(3, 1, [Block(start=150.0, end=250.0, btype=BlockType.PAIRING)])
    
    roster = [c_tier1_sen10, c_tier2_sen1, c_tier1_sen5]

    # Should still pick Tier 1, but sen10 (highest number = most junior)
    chosen = select_draft_candidate(roster, duty, junior_first=True, cfg=_test_cfg())
    assert chosen is not None
    assert chosen.crew_id == "C0001"
    assert chosen.seniority == 10

def test_orderings_produce_different_draft_sequences():
    """S1a-08 AC4 (defect D6): senior-first and junior-first must not be the
    same selector. In v2 they were -- the sort ran twice and inverted itself.

    Asserts on the CREW SEQUENCE from a real scenario's ledger, because that is
    what actually differs. Measured on this corpus: the two orderings draft
    genuinely different people (P00343/P00350, senior, vs P00451/P00449,
    junior) but cost exactly the same, to the dollar, across every scenario --
    draft cost is priced by TIER (base_premium + tier), every draft here lands
    in tier 1, and seniority does not enter the tariff. So the AC's literal
    wording, "different cost vectors", is not satisfiable on this data and a
    test asserting it would fail against a correctly working selector.

    The superseded version compared strings like "C0002_tier1" built from a
    hand-made three-crew roster, with the comment "we don't have the cost
    engine yet" -- true when written, not since S1d-04c.
    """
    from crewsim import config
    from crewsim.engine import des
    from crewsim.engine.policy import load_policy

    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    def drafted_crew(draft_mode: str) -> list[str]:
        sim = des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="d6-regression",
                               n_scenarios=2, draft_mode=draft_mode)
        return [r.crew_id for r in sim.ledger.rows if r.category.startswith("DRAFT")]

    senior = drafted_crew("mandated")
    junior = drafted_crew("junior_first")

    assert senior, "a real scenario must produce at least one draft to compare"
    assert senior != junior, (
        "D6 regression: senior-first and junior-first drafted the identical sequence "
        "of crew -- the mandated ordering is not actually being applied"
    )
    # Direction, not just difference: mandated must reach for lower seniority
    # NUMBERS (more senior) than junior_first does.
    senior_nums = [int(c.lstrip("P")) for c in senior]
    junior_nums = [int(c.lstrip("P")) for c in junior]
    assert sum(senior_nums) / len(senior_nums) < sum(junior_nums) / len(junior_nums), (
        "mandated drafted more JUNIOR crew on average than junior_first -- the sort "
        "is inverted, which is exactly defect D6"
    )

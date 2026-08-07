from crewsim.engine.state import CrewMember, Block, BlockType, OpenTimeItem
from crewsim.engine.drafting import determine_tier, select_draft_candidate

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
    assert determine_tier(c1, duty) == 1
    
    # Tier 2: PAIRING
    c2 = _test_crew(2, 20, [Block(start=150.0, end=250.0, btype=BlockType.PAIRING)])
    assert determine_tier(c2, duty) == 2
    
    # Tier 3: TRAINING
    c3 = _test_crew(3, 30, [Block(start=50.0, end=150.0, btype=BlockType.TRAINING)])
    assert determine_tier(c3, duty) == 3
    
    # Tier 4: VACATION
    c4 = _test_crew(4, 40, [Block(start=0.0, end=300.0, btype=BlockType.VACATION)])
    assert determine_tier(c4, duty) == 4

def test_select_senior_first():
    duty = _test_duty()
    
    c_tier1_sen10 = _test_crew(1, 10)
    c_tier1_sen5 = _test_crew(2, 5)   # More senior (lower number)
    c_tier2_sen1 = _test_crew(3, 1, [Block(start=150.0, end=250.0, btype=BlockType.PAIRING)]) # Most senior, but Tier 2
    
    roster = [c_tier1_sen10, c_tier2_sen1, c_tier1_sen5]
    
    # Should pick Tier 1 over Tier 2, and sen5 over sen10
    chosen = select_draft_candidate(roster, duty)
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
    chosen = select_draft_candidate(roster, duty, junior_first=True)
    assert chosen is not None
    assert chosen.crew_id == "C0001"
    assert chosen.seniority == 10

def test_orderings_produce_different_cost_vectors():
    # Regression test for D6: senior_first and junior_first must produce different sequences
    duty1 = _test_duty(100.0, 200.0)
    duty2 = _test_duty(300.0, 400.0)
    
    roster = [
        _test_crew(1, 10),
        _test_crew(2, 5),
        _test_crew(3, 1)
    ]
    
    def simulate(junior_first: bool):
        # We don't have the cost engine yet, so the "cost vector" proxy is the sequence
        # of (chosen_crew_id, tier) which would generate the costs.
        vector = []
        # Event 1
        c1 = select_draft_candidate(roster, duty1, junior_first)
        assert c1 is not None
        vector.append(f"{c1.crew_id}_tier{determine_tier(c1, duty1)}")
        
        # Simulate state mutation (assign duty1 to chosen crew)
        c1.calendar.append(Block(start=100.0, end=200.0, btype=BlockType.DRAFTED_DUTY))
        c1.calendar.sort()
        
        # Event 2
        c2 = select_draft_candidate(roster, duty2, junior_first)
        assert c2 is not None
        vector.append(f"{c2.crew_id}_tier{determine_tier(c2, duty2)}")
        
        # Undo state mutation for next run
        c1.calendar.pop()
        
        return vector

    vector_senior = simulate(junior_first=False)
    vector_junior = simulate(junior_first=True)
    
    assert vector_senior != vector_junior, "D6 regression: Cost vectors (draft sequences) must not be identical"


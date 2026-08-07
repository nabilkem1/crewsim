from crewsim.engine.ledger import CostLedger

def test_ledger_booking():
    ledger = CostLedger()
    
    # Simulating a sick call on Tuesday that leads to a cascade and cancellation on Thursday
    
    # 1. Root event (Tuesday sick call -> uncovered item)
    # 2. Draft tier-1 to cover it
    ledger.book(
        scenario_id=0, policy_id="P1", sim_time=100.0,
        event_uid=10, root_event_uid=1, crew_id="C0001",
        category="DRAFT_TIER1", amount=500.0
    )
    
    # 3. Draft causes a cascade (future pairing broken -> new uncovered item)
    # The new event (uid=11) tracks back to the root (uid=1)
    
    # 4. The cascaded item cancels on Thursday
    ledger.book(
        scenario_id=0, policy_id="P1", sim_time=150.0,
        event_uid=11, root_event_uid=1, crew_id=None,
        category="CANCELLATION", amount=25000.0
    )
    
    assert len(ledger.rows) == 2
    
    # Verify aggregation is purely derived from rows
    totals = ledger.sum_by_category()
    assert totals["DRAFT_TIER1"] == 500.0
    assert totals["CANCELLATION"] == 25000.0
    assert ledger.total_cost() == 25500.0
    
    # Verify we can trace root_event_uid=1 entirely
    traced = ledger.filter_by_root(1)
    assert len(traced) == 2
    assert sum(r.amount for r in traced) == 25500.0

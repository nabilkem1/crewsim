from crewsim.engine.ledger import CostLedger
from crewsim.engine.costs import book_reserve_staffing

def test_reserve_staffing_linear_scaling():
    ledger = CostLedger()
    
    # 6 reserves, $250/day, 28 days total horizon
    book_reserve_staffing(
        ledger=ledger,
        scenario_id=0,
        policy_id="R6",
        num_reserves=6,
        rate_per_day=250.0,
        horizon_days=28
    )
    
    # Total rows should be 6 * 28 = 168
    assert len(ledger.rows) == 168
    
    # Unfiltered total: 168 * 250 = 42,000
    assert ledger.total_cost() == 42000.0
    
    # Warm-up filter: skip first 7 days
    # sim_time for day 7 is 7 * 24 * 60 = 10080
    warmup_end = 7 * 24 * 60.0
    
    # Measured window total (21 days * 6 reserves * 250 = 31500)
    measured_total = ledger.total_cost(min_time=warmup_end)
    assert measured_total == 31500.0

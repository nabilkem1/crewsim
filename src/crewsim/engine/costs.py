from crewsim.engine.ledger import CostLedger

def book_reserve_staffing(
    ledger: CostLedger,
    scenario_id: int,
    policy_id: str,
    num_reserves: int,
    rate_per_day: float,
    horizon_days: int
) -> None:
    """
    Book RESERVE_STAFFING once per reserve per day.
    This fixes D1 by ensuring costs are distributed correctly over time and
    can be properly prorated by the warm-up filter.
    """
    for day in range(horizon_days):
        # Sim time in minutes: day * 24 * 60
        sim_time = float(day * 24 * 60)
        for i in range(num_reserves):
            ledger.book(
                scenario_id=scenario_id,
                policy_id=policy_id,
                sim_time=sim_time,
                event_uid=0,           # Staffing is structural
                root_event_uid=0,
                crew_id=f"R{i+1:03d}",
                category="RESERVE_STAFFING",
                amount=rate_per_day
            )

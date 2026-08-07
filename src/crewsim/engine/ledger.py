from dataclasses import dataclass

@dataclass(frozen=True)
class LedgerRow:
    scenario_id: int
    policy_id: str
    sim_time: float
    event_uid: int
    root_event_uid: int
    crew_id: str | None
    category: str
    amount: float

class CostLedger:
    def __init__(self) -> None:
        self.rows: list[LedgerRow] = []

    def book(
        self,
        scenario_id: int,
        policy_id: str,
        sim_time: float,
        event_uid: int,
        root_event_uid: int,
        crew_id: str | None,
        category: str,
        amount: float
    ) -> None:
        """
        Record a cost event. Every aggregate is derived purely from these rows.
        """
        self.rows.append(LedgerRow(
            scenario_id=scenario_id,
            policy_id=policy_id,
            sim_time=sim_time,
            event_uid=event_uid,
            root_event_uid=root_event_uid,
            crew_id=crew_id,
            category=category,
            amount=amount
        ))

    def sum_by_category(self, min_time: float = 0.0, max_time: float | None = None) -> dict[str, float]:
        """Derive aggregate totals from the raw rows, optionally filtered by time (e.g. warm-up)."""
        totals: dict[str, float] = {}
        for row in self.rows:
            if row.sim_time >= min_time and (max_time is None or row.sim_time < max_time):
                totals[row.category] = totals.get(row.category, 0.0) + row.amount
        return totals

    def filter_by_root(self, root_uid: int) -> list[LedgerRow]:
        """Trace all costs originating from a single root event."""
        return [r for r in self.rows if r.root_event_uid == root_uid]

    def total_cost(self, min_time: float = 0.0, max_time: float | None = None) -> float:
        return sum(
            row.amount for row in self.rows 
            if row.sim_time >= min_time and (max_time is None or row.sim_time < max_time)
        )

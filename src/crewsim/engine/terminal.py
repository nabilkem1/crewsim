
from crewsim.config import CostsConfig
from crewsim.engine.state import OpenTimeItem


def evaluate_terminal_penalties(residual_items: list[OpenTimeItem], costs: CostsConfig) -> list[tuple[str, float, int]]:
    """
    Evaluates terminal penalties for any unresolved OpenTimeItems remaining at the simulation horizon.
    Returns a list of (category, amount, root_event_uid) for ledger booking.
    """
    entries = []
    penalty_amount = costs.disruption.cancellation * costs.disruption.terminal_penalty_multiple
    
    for item in residual_items:
        entries.append(
            ("TERMINAL_PENALTY", penalty_amount, item.root_event_uid)
        )
        
    return entries

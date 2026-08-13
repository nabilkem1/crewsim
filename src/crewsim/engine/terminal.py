
from crewsim.config import CostsConfig
from crewsim.engine.state import OpenTimeItem


def evaluate_terminal_penalties(
    residual_items: list[OpenTimeItem], costs: CostsConfig
) -> list[tuple[str, float, int, int]]:
    """
    Evaluates terminal penalties for any unresolved OpenTimeItems remaining at the simulation horizon.
    Returns a list of (category, amount, event_uid, root_event_uid) for ledger booking.

    event_uid is the residual item's own uid (it used to be booked as 0):
    the AUD-03 causal marker books one OPEN_ITEM row per item uid, and
    carrying the same uid here is what lets a reader -- and the Welch
    queue-length diagnostic -- pair a terminal penalty with the exact item
    it punishes.
    """
    entries = []
    penalty_amount = costs.disruption.cancellation * costs.disruption.terminal_penalty_multiple

    for item in residual_items:
        entries.append(
            ("TERMINAL_PENALTY", penalty_amount, item.uid, item.root_event_uid)
        )

    return entries

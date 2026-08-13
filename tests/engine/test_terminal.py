import types

from crewsim.engine.state import OpenTimeItem
from crewsim.engine.terminal import evaluate_terminal_penalties


def test_evaluate_terminal_penalties():
    # Setup mock costs
    costs = types.SimpleNamespace()
    costs.disruption = types.SimpleNamespace()
    costs.disruption.cancellation = 25000.0
    costs.disruption.terminal_penalty_multiple = 1.5
    
    items = [
        OpenTimeItem(
            uid=101,
            pairing_id="P_TERM1",
            base="YUL",
            fleet="A330",
            position="CA",
            start=1000.0,
            end=1100.0,
            deadline=900.0,
            origin="SICK_CALL",
            root_event_uid=5,
            flight_mins=0.0
        ),
        OpenTimeItem(
            uid=102,
            pairing_id="P_TERM2",
            base="YUL",
            fleet="A330",
            position="CA",
            start=1100.0,
            end=1200.0,
            deadline=1000.0,
            origin="CASCADE",
            root_event_uid=7,
            flight_mins=0.0
        )
    ]
    
    entries = evaluate_terminal_penalties(items, costs)

    assert len(entries) == 2

    assert entries[0][0] == "TERMINAL_PENALTY"
    assert entries[0][1] == 37500.0 # 25000 * 1.5
    assert entries[0][2] == 101 # the item's own uid (AUD-03: pairs with its OPEN_ITEM marker)
    assert entries[0][3] == 5 # root_event_uid preserved

    assert entries[1][0] == "TERMINAL_PENALTY"
    assert entries[1][1] == 37500.0
    assert entries[1][2] == 102
    assert entries[1][3] == 7


import pytest

from crewsim.engine.cascade import apply_delta, compute_draft_delta
from crewsim.engine.drafting import determine_tier
from crewsim.engine.legality import find_l0_violations
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


def test_future_pairing_cascade():
    # Setup mock config
    # Real base.yaml: compute_draft_delta reads legality.min_rest_hours_* via
    # the shared min_rest_minutes helper, not just cascade.visibility_lag_hours.
    from tests.engine.conftest import legality_cfg
    cfg = legality_cfg()
    
    # Create a crew member with a future pairing
    # Pairing from t=1000 to t=1100
    crew = CrewMember("C1", "YUL", {"A330"}, "CA", 1, [
        Block(start=1000.0, end=1100.0, btype=BlockType.PAIRING, pairing_id="P_FUTURE")
    ])
    
    # Draft item that overlaps with the pairing
    # Draft from t=900 to t=1050
    item = OpenTimeItem(
        uid=1,
        pairing_id="P_DRAFT",
        base="YUL",
        fleet="A330",
        position="CA",
        start=900.0,
        end=1050.0,
        deadline=800.0,
        origin="SICK_CALL",
        root_event_uid=1,
        flight_mins=0.0
    )
    
    delta, cascades = compute_draft_delta(crew, item, cfg, now=900.0)
    
    # Assert delta logic
    assert len(delta.added_blocks) == 2 # DRAFTED_DUTY and REST
    assert delta.added_blocks[0].btype == BlockType.DRAFTED_DUTY
    assert delta.added_blocks[1].btype == BlockType.REST
    
    # Assert pairing was removed
    assert len(delta.removed_blocks) == 1
    assert delta.removed_blocks[0].pairing_id == "P_FUTURE"
    
    # Assert cascade item was generated
    assert len(cascades) == 1
    casc = cascades[0]
    assert casc.pairing_id == "P_FUTURE"
    assert casc.origin == "CASCADE"
    assert casc.root_event_uid == 1 # inherited root uid
    assert casc.start == 1000.0
    
    # Apply delta and verify state
    apply_delta(crew, delta)
    
    block_types = [b.btype for b in crew.calendar]
    assert BlockType.DRAFTED_DUTY in block_types
    assert BlockType.REST in block_types
    assert BlockType.PAIRING not in block_types # The future pairing is gone

def test_future_pairing_mandatory_rest_cascade():
    # Real base.yaml: compute_draft_delta reads legality.min_rest_hours_* via
    # the shared min_rest_minutes helper, not just cascade.visibility_lag_hours.
    from tests.engine.conftest import legality_cfg
    cfg = legality_cfg()
    
    # Future pairing starts at 1050
    crew = CrewMember("C1", "YUL", {"A330"}, "CA", 1, [
        Block(start=1050.0, end=1200.0, btype=BlockType.PAIRING, pairing_id="P_FUTURE")
    ])
    
    # Draft item from 800 to 900
    # Mandatory rest (home base = 11h = 660m). Rest ends at 900 + 660 = 1560
    # Since 1050 is < 1560, the future pairing is completely broken by the rest!
    item = OpenTimeItem(
        uid=1,
        pairing_id="P_DRAFT",
        base="YUL",
        fleet="A330",
        position="CA",
        start=800.0,
        end=900.0,
        deadline=700.0,
        origin="SICK_CALL",
        root_event_uid=1,
        flight_mins=0.0
    )
    
    delta, cascades = compute_draft_delta(crew, item, cfg, now=800.0)
    
    # Assert pairing was removed
    assert len(delta.removed_blocks) == 1
    assert delta.removed_blocks[0].pairing_id == "P_FUTURE"
    
    # Assert cascade item was generated
    assert len(cascades) == 1
    casc = cascades[0]
    assert casc.pairing_id == "P_FUTURE"

def test_future_reserve_cascade():
    from tests.engine.conftest import legality_cfg
    cfg = legality_cfg()


    # Future reserve starts at 1050
    crew = CrewMember("C1", "YUL", {"A330"}, "CA", 1, [
        Block(start=1050.0, end=1400.0, btype=BlockType.RESERVE)
    ])
    
    # Draft item from 800 to 900
    # Mandatory rest ends at 1560
    item = OpenTimeItem(
        uid=1,
        pairing_id="P_DRAFT",
        base="YUL",
        fleet="A330",
        position="CA",
        start=800.0,
        end=900.0,
        deadline=700.0,
        origin="SICK_CALL",
        root_event_uid=1,
        flight_mins=0.0
    )
    
    delta, cascades = compute_draft_delta(crew, item, cfg, now=800.0)
    
    # Assert reserve block was removed
    assert len(delta.removed_blocks) == 1
    assert delta.removed_blocks[0].btype == BlockType.RESERVE
    
    # Assert NO cascade item was generated (it's a capacity loss, not an open item)
    assert len(cascades) == 0


@pytest.mark.parametrize(
    ("btype", "expected_tier"),
    [(BlockType.TRAINING, 3), (BlockType.SIMULATOR, 5)],
)
def test_training_block_removed_by_draft(btype, expected_tier):
    """IMP-103: drafting a crew member out of training or a simulator session
    removes that session from their calendar.

    It used to stay, so the realized calendar held DRAFTED_DUTY overlapping a
    TRAINING/SIMULATOR block -- two DUTY_BLOCKS at once, reported by
    find_l0_violations and double-counted by the rolling counters -- while the
    reschedule fee for exactly that session was still booked.
    """
    from tests.engine.conftest import legality_cfg
    cfg = legality_cfg()

    session = Block(start=850.0, end=1300.0, btype=btype)
    crew = CrewMember("C1", "YUL", {"A330"}, "CA", 1, [session])
    item = OpenTimeItem(
        uid=1, pairing_id="P_DRAFT", base="YUL", fleet="A330", position="CA",
        start=800.0, end=900.0, deadline=700.0, origin="SICK_CALL", root_event_uid=1,
    )

    assert determine_tier(crew, item, cfg) == expected_tier
    delta, cascades = compute_draft_delta(crew, item, cfg, now=800.0)

    assert session in delta.removed_blocks
    assert cascades == []  # a rescheduled session is not an uncovered flight
    apply_delta(crew, delta)
    assert btype not in {b.btype for b in crew.calendar}
    assert find_l0_violations(crew) == []

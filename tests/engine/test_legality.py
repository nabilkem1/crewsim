from hypothesis import given, strategies as st
from crewsim.engine.state import CrewMember, Block, BlockType
from crewsim.engine.legality import check_l0_single_assignment

# Strategy to generate valid, non-overlapping sorted blocks for a calendar
@st.composite
def calendars(draw):
    num_blocks = draw(st.integers(min_value=0, max_value=20))
    blocks = []
    current_time = 0.0
    for _ in range(num_blocks):
        # Gap before next block
        current_time += draw(st.floats(min_value=0.0, max_value=1000.0, allow_infinity=False, allow_nan=False))
        # Block duration
        duration = draw(st.floats(min_value=1.0, max_value=2000.0, allow_infinity=False, allow_nan=False))
        btype = draw(st.sampled_from(list(BlockType)))
        blocks.append(Block(start=current_time, end=current_time + duration, btype=btype))
        current_time += duration
    return blocks

@given(
    cal=calendars(),
    start=st.floats(min_value=0.0, max_value=30000.0, allow_infinity=False, allow_nan=False),
    duration=st.floats(min_value=1.0, max_value=2000.0, allow_infinity=False, allow_nan=False),
)
def test_l0_invariant(cal, start, duration):
    crew = CrewMember(
        crew_id="test_crew",
        base="YUL",
        fleet_quals={"A330"},
        position="CA",
        seniority=1,
        calendar=cal
    )
    
    end = start + duration
    res = check_l0_single_assignment(crew, start, end)
    
    # Manually check if there is an overlapping occupying block
    occupying_types = {BlockType.DRAFTED_DUTY, BlockType.REST, BlockType.DEADHEAD}
    has_occupying_overlap = any(
        b.start < end and b.end > start and b.btype in occupying_types
        for b in cal
    )
    
    if has_occupying_overlap:
        assert not res.legal
        assert res.fail_rule == "ILLEGAL_L0"
    else:
        assert res.legal
        assert res.fail_rule is None

def test_l0_pairing_not_occupying():
    # specifically tests that PAIRING is not occupying
    crew = CrewMember(
        crew_id="test", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
        calendar=[Block(start=100.0, end=200.0, btype=BlockType.PAIRING)]
    )
    res = check_l0_single_assignment(crew, start=150.0, end=250.0)
    assert res.legal

from crewsim.engine.state import OpenTimeItem
from crewsim.engine.legality import is_legal_assignment

def _test_crew(calendar=None):
    return CrewMember(
        crew_id="test", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
        calendar=calendar or []
    )

def _test_duty(start=100.0, end=200.0, base="YUL", fleet="A330", position="CA"):
    return OpenTimeItem(
        uid=1, pairing_id="P1", base=base, fleet=fleet, position=position,
        start=start, end=end, deadline=start-10, origin="SICK_CALL", root_event_uid=1
    )

def test_l1_max_duty():
    crew = _test_crew()
    # 13 hours = 780 minutes
    duty_legal = _test_duty(start=0.0, end=780.0)
    assert is_legal_assignment(crew, duty_legal).legal

    duty_illegal = _test_duty(start=0.0, end=781.0)
    res = is_legal_assignment(crew, duty_illegal)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L1"
    assert "13h exceeded" in res.reason

def test_l2_min_rest_home():
    # Home base needs 11 hours (660 mins) rest
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.PAIRING)])
    duty_legal = _test_duty(start=100.0 + 660.0, end=1000.0, base="YUL")
    assert is_legal_assignment(crew, duty_legal).legal

    duty_illegal = _test_duty(start=100.0 + 659.0, end=1000.0, base="YUL")
    res = is_legal_assignment(crew, duty_illegal)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L2"
    assert "Insufficient rest" in res.reason

def test_l2_min_rest_away():
    # Away base needs 10 hours (600 mins) rest
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.PAIRING)])
    # base CDG is away from YUL
    duty_legal = _test_duty(start=100.0 + 600.0, end=1000.0, base="CDG")
    # Need to deadhead to get there to avoid L7, so we'll mock that by passing is_deadhead=True
    assert is_legal_assignment(crew, duty_legal, is_deadhead=True).legal

    duty_illegal = _test_duty(start=100.0 + 599.0, end=1000.0, base="CDG")
    res = is_legal_assignment(crew, duty_illegal, is_deadhead=True)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L2"

def test_l2_vacation_not_duty():
    # Vacation is not a duty, so rest rules don't apply to the gap after vacation ends
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.VACATION)])
    duty_legal = _test_duty(start=101.0, end=200.0)
    assert is_legal_assignment(crew, duty_legal).legal

def test_l6_qualifications():
    crew = _test_crew()
    # Fleet mismatch
    duty_wrong_fleet = _test_duty(fleet="A321neoLR")
    res1 = is_legal_assignment(crew, duty_wrong_fleet)
    assert not res1.legal
    assert res1.fail_rule == "ILLEGAL_L6"
    assert "Wrong type rating" in res1.reason

    # Position mismatch
    duty_wrong_pos = _test_duty(position="FO")
    res2 = is_legal_assignment(crew, duty_wrong_pos)
    assert not res2.legal
    assert res2.fail_rule == "ILLEGAL_L6"
    assert "Wrong position" in res2.reason

def test_l7_base():
    crew = _test_crew()
    # Base mismatch
    duty_wrong_base = _test_duty(base="YYZ")
    res = is_legal_assignment(crew, duty_wrong_base)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L7"
    assert "Base mismatch" in res.reason

    # But legal if deadheading
    assert is_legal_assignment(crew, duty_wrong_base, is_deadhead=True).legal

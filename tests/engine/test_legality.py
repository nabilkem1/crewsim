from hypothesis import given
from hypothesis import strategies as st

from crewsim.engine.legality import (
    OCCUPYING_BLOCKS,
    check_l0_single_assignment,
    find_l0_violations,
    is_legal_assignment,
)
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


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
    
    # Manually check if there is an overlapping occupying block. Uses the
    # canonical OCCUPYING_BLOCKS set: this test's subject is the overlap
    # MECHANISM, and a locally restated set silently drifts when a new
    # occupying type is added (it did -- AUD-02's ABSENCE).
    has_occupying_overlap = any(
        b.start < end and b.end > start and b.btype in OCCUPYING_BLOCKS
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



def _test_crew(calendar=None):
    return CrewMember(
        crew_id="test", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
        calendar=calendar or []
    )

def _test_duty(start=100.0, end=200.0, base="YUL", fleet="A330", position="CA", flight_mins=0.0):
    return OpenTimeItem(
        uid=1, pairing_id="P1", base=base, fleet=fleet, position=position,
        start=start, end=end, deadline=start-10, origin="SICK_CALL", root_event_uid=1, flight_mins=flight_mins
    )

def _test_cfg():
    """The real configs/base.yaml -- see tests/engine/conftest.py for why this
    is not a hand-built stand-in any more."""
    from tests.engine.conftest import legality_cfg
    return legality_cfg()

def test_l1_max_duty():
    crew = _test_crew()
    cfg = _test_cfg()
    # 13 hours = 780 minutes
    duty_legal = _test_duty(start=0.0, end=780.0)
    assert is_legal_assignment(crew, duty_legal, cfg=cfg).legal

    duty_illegal = _test_duty(start=0.0, end=781.0)
    res = is_legal_assignment(crew, duty_illegal, cfg=cfg)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L1"
    assert "13h exceeded" in res.reason

def test_l2_min_rest_home():
    # Home base needs 11 hours (660 mins) rest
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.PAIRING)])
    cfg = _test_cfg()
    
    duty_legal = _test_duty(start=100.0 + 660.0, end=1000.0)
    assert is_legal_assignment(crew, duty_legal, cfg=cfg).legal
    
    duty_illegal = _test_duty(start=100.0 + 659.0, end=1000.0)
    res = is_legal_assignment(crew, duty_illegal, cfg=cfg)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L2"
    assert "Insufficient rest" in res.reason

def test_l2_min_rest_away():
    # Away base needs 10 hours (600 mins) rest
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.PAIRING)])
    cfg = _test_cfg()
    # base CDG is away from YUL
    duty_legal = _test_duty(start=100.0 + 600.0, end=1000.0, base="CDG")
    # Need to deadhead to get there to avoid L7, so we'll mock that by passing is_deadhead=True
    assert is_legal_assignment(crew, duty_legal, is_deadhead=True, cfg=cfg).legal
    
    duty_illegal = _test_duty(start=100.0 + 599.0, end=1000.0, base="CDG")
    res = is_legal_assignment(crew, duty_illegal, is_deadhead=True, cfg=cfg)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L2"

def test_l2_vacation_not_duty():
    # Vacation is not a duty, so rest rules don't apply to the gap after vacation ends
    crew = _test_crew([Block(start=0.0, end=100.0, btype=BlockType.VACATION)])
    cfg = _test_cfg()
    duty_legal = _test_duty(start=101.0, end=200.0)
    assert is_legal_assignment(crew, duty_legal, cfg=cfg).legal

def test_l6_qualifications():
    crew = _test_crew()
    cfg = _test_cfg()
    # Fleet mismatch
    duty_wrong_fleet = _test_duty(fleet="A321neoLR")
    res1 = is_legal_assignment(crew, duty_wrong_fleet, cfg=cfg)
    assert not res1.legal
    assert res1.fail_rule == "ILLEGAL_L6"
    assert "Wrong type rating" in res1.reason
    
    # Position mismatch
    duty_wrong_pos = _test_duty(position="FO")
    res2 = is_legal_assignment(crew, duty_wrong_pos, cfg=cfg)
    assert not res2.legal
    assert res2.fail_rule == "ILLEGAL_L6"
    assert "Wrong position" in res2.reason

def test_l7_base():
    crew = _test_crew()
    cfg = _test_cfg()
    # Base mismatch
    duty_wrong_base = _test_duty(base="YYZ")
    res = is_legal_assignment(crew, duty_wrong_base, cfg=cfg)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L7"
    assert "Base mismatch" in res.reason

    # But legal if deadheading
    assert is_legal_assignment(crew, duty_wrong_base, is_deadhead=True, cfg=cfg).legal

def test_l8_notice_time():
    import types

    from crewsim.engine.legality import check_l8_notice_time
    
    # Mock cfg
    mock_cfg = types.SimpleNamespace()
    mock_cfg.legality = types.SimpleNamespace()
    mock_cfg.legality.short_call_notice_hours = 2.0
    mock_cfg.legality.long_call_notice_hours = 12.0
    
    # SC requires 2 hours (120 mins) notice
    crew_sc = _test_crew([Block(start=0.0, end=1000.0, btype=BlockType.RESERVE, reserve_call_type="SC")])
    duty = _test_duty(start=300.0, end=500.0)
    
    # 2.5 hours notice (150 mins) -> Legal
    res_sc_legal = check_l8_notice_time(crew_sc, duty, now=150.0, cfg=mock_cfg)
    assert res_sc_legal.legal
    
    # 1.5 hours notice (90 mins) -> Illegal
    res_sc_illegal = check_l8_notice_time(crew_sc, duty, now=210.0, cfg=mock_cfg)
    assert not res_sc_illegal.legal
    assert res_sc_illegal.fail_rule == "ILLEGAL_L8"
    assert "Insufficient notice" in res_sc_illegal.reason
    assert "for SC" in res_sc_illegal.reason
    
    # LC requires 12 hours (720 mins) notice
    crew_lc = _test_crew([Block(start=0.0, end=1500.0, btype=BlockType.RESERVE, reserve_call_type="LC")])
    duty_lc = _test_duty(start=1000.0, end=1200.0)
    
    # 13 hours notice (780 mins) -> Legal
    res_lc_legal = check_l8_notice_time(crew_lc, duty_lc, now=220.0, cfg=mock_cfg)
    assert res_lc_legal.legal
    
    # 10 hours notice (600 mins) -> Illegal
    res_lc_illegal = check_l8_notice_time(crew_lc, duty_lc, now=400.0, cfg=mock_cfg)
    assert not res_lc_illegal.legal
    assert res_lc_illegal.fail_rule == "ILLEGAL_L8"
    assert "for LC" in res_lc_illegal.reason

def test_l8_classification_uses_call_time_not_report_time():
    """S1c-02: the docstring says L8 is 'applied against the call time, not
    the report time' -- that must also govern which reserve block decides
    SC vs LC, not just the notice-duration arithmetic. A crew called while
    on an SC block, whose on-call regime later flips to LC before the duty's
    report time, must be judged as SC (found as a real bug: the original
    implementation looked up the block at item.start, misclassifying this
    case as LC and failing it against LC's stricter 12h requirement)."""
    import types

    from crewsim.engine.legality import check_l8_notice_time

    mock_cfg = types.SimpleNamespace()
    mock_cfg.legality = types.SimpleNamespace()
    mock_cfg.legality.short_call_notice_hours = 2.0
    mock_cfg.legality.long_call_notice_hours = 12.0

    # On an SC block when called (now=100); the block flips to LC at 200,
    # before the duty's report at 300.
    crew = _test_crew([
        Block(start=0.0, end=200.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
        Block(start=200.0, end=1000.0, btype=BlockType.RESERVE, reserve_call_type="LC"),
    ])
    duty = _test_duty(start=300.0, end=500.0)

    # 3.33h notice: enough for SC's 2h, nowhere near LC's 12h.
    res = check_l8_notice_time(crew, duty, now=100.0, cfg=mock_cfg)
    assert res.legal

def test_in_progress_pairing_blocks_a_draft():
    """IMP-104: a crew member cannot be drafted off a pairing already under way.

    PAIRING is not an OCCUPYING block (line holders are drafted off FUTURE
    pairings by design), so before this check a crew member flying a trip at
    the call was a legal candidate for an item overlapping it, and the draft
    reopened a trip that was in the air.
    """
    cfg = _test_cfg()
    flying = _test_crew([
        Block(start=50.0, end=900.0, btype=BlockType.PAIRING, pairing_id="IN_AIR"),
    ])
    item = _test_duty(start=300.0, end=500.0)

    res = is_legal_assignment(flying, item, now=100.0, cfg=cfg)
    assert not res.legal and res.fail_rule == "ILLEGAL_L0"
    assert "already under way" in res.reason

    # The same pairing, not yet started at the call, may be drafted off.
    assert is_legal_assignment(flying, item, now=40.0, cfg=cfg).legal


def test_line_notice():
    """IMP-104: line-holder draft notice comes from config, boundary inclusive."""
    import types

    from crewsim.engine.legality import check_l8_notice_time

    cfg = types.SimpleNamespace(legality=types.SimpleNamespace(
        short_call_notice_hours=2.0, long_call_notice_hours=12.0,
        line_holder_draft_notice_hours=3.0,
    ))
    line_holder = _test_crew([Block(start=0.0, end=2000.0, btype=BlockType.DAY_OFF)])
    item = _test_duty(start=400.0, end=600.0)

    assert check_l8_notice_time(line_holder, item, now=220.0, cfg=cfg).legal       # exactly 3 h
    late = check_l8_notice_time(line_holder, item, now=221.0, cfg=cfg)
    assert not late.legal and late.fail_rule == "ILLEGAL_L8"

    # The shipped default (0.0) adds no floor, but a call after the report is
    # never legal.
    cfg.legality.line_holder_draft_notice_hours = 0.0
    assert check_l8_notice_time(line_holder, item, now=400.0, cfg=cfg).legal
    assert not check_l8_notice_time(line_holder, item, now=401.0, cfg=cfg).legal


def _l8_cfg():
    import types

    return types.SimpleNamespace(legality=types.SimpleNamespace(
        short_call_notice_hours=2.0, long_call_notice_hours=12.0,
        line_holder_draft_notice_hours=0.0,
    ))


def test_l8_between_shifts_reserve_gets_reserve_notice():
    """IMP-116: a reserve called BETWEEN shifts, for a duty reporting inside
    their next shift, is in the eligibility pool because that next block covers
    the report. L8 must hold them to that block's SC/LC notice, not to the
    line-holder notice (0 h) they used to fall through to."""
    from crewsim.engine.eligibility import is_on_call_at
    from crewsim.engine.legality import check_l8_notice_time

    # Off shift at the call (now=500); on an SC shift from 600 that covers the
    # report at 610. 1h50 notice: legal for a line holder, illegal for SC (2 h).
    reserve = _test_crew([
        Block(start=0.0, end=400.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
        Block(start=600.0, end=1320.0, btype=BlockType.RESERVE, reserve_call_type="SC"),
    ])
    item = _test_duty(start=610.0, end=800.0)
    assert is_on_call_at(reserve, item.start)  # the pool admits them

    res = check_l8_notice_time(reserve, item, now=500.0, cfg=_l8_cfg())
    assert not res.legal and res.fail_rule == "ILLEGAL_L8"
    assert "for SC" in res.reason

    # Enough SC notice -> legal.
    assert check_l8_notice_time(reserve, item, now=480.0, cfg=_l8_cfg()).legal


def test_l8_between_shifts_long_call_reserve_gets_long_call_notice():
    """IMP-116, LC variant: the next shift's LC notice applies, not 0 h."""
    from crewsim.engine.legality import check_l8_notice_time

    reserve = _test_crew([
        Block(start=1440.0, end=2160.0, btype=BlockType.RESERVE, reserve_call_type="LC"),
    ])
    item = _test_duty(start=1500.0, end=1700.0)

    short = check_l8_notice_time(reserve, item, now=1000.0, cfg=_l8_cfg())   # 8.3 h
    assert not short.legal and "for LC" in short.reason
    assert check_l8_notice_time(reserve, item, now=780.0, cfg=_l8_cfg()).legal  # 12 h exactly


def test_l8_line_holder_still_gets_line_holder_notice():
    """IMP-116 must not change line holders: with no RESERVE block at the call
    or at the report, the line-holder notice applies."""
    from crewsim.engine.legality import check_l8_notice_time, reserve_call_type_for

    line_holder = _test_crew([Block(start=0.0, end=200.0, btype=BlockType.PAIRING, pairing_id="P1")])
    item = _test_duty(start=610.0, end=800.0)
    assert reserve_call_type_for(line_holder, item, now=500.0) is None
    assert check_l8_notice_time(line_holder, item, now=500.0, cfg=_l8_cfg()).legal


def test_l3_rolling_7d():
    import types

    from crewsim.engine.legality import check_l3_rolling_7d
    from crewsim.engine.state import Block, BlockType
    mock_cfg = types.SimpleNamespace()
    mock_cfg.legality = types.SimpleNamespace()
    mock_cfg.legality.rolling_7d_duty_limit_hours = 60.0
    mock_cfg.legality.rolling_7d_flight_limit_hours = 35.0
    
    # Base case: empty calendar
    crew = _test_crew([])
    duty = _test_duty(start=1000.0, end=1000.0 + 600.0, flight_mins=300.0) # 10 hours duty, 5 hours flight
    
    res = check_l3_rolling_7d(crew, duty, mock_cfg)
    assert res.legal
    
    # 7 days is 7 * 24 * 60 = 10080 mins
    # Let's give them 55 hours duty (3300 mins) in the last 7 days
    b1 = Block(start=1000.0 - 5000.0, end=1000.0 - 5000.0 + 3300.0, btype=BlockType.PAIRING, flight_mins=0.0)
    crew2 = _test_crew([b1])
    
    # Adding a 6 hour duty (360 mins) will push it to 61 hours duty -> Illegal!
    duty2 = _test_duty(start=1000.0, end=1000.0 + 360.0, flight_mins=0.0)
    res2 = check_l3_rolling_7d(crew2, duty2, mock_cfg)
    assert not res2.legal
    assert res2.fail_rule == "ILLEGAL_L3"
    assert "duty" in res2.reason
    
    # Let's test flight limits: 34 hours flight in last 7 days
    b2 = Block(start=1000.0 - 2000.0, end=1000.0 - 2000.0 + 2040.0, btype=BlockType.PAIRING, flight_mins=2040.0)
    crew3 = _test_crew([b2])
    
    # Adding 2 hours flight -> Illegal!
    duty3 = _test_duty(start=1000.0, end=1000.0 + 300.0, flight_mins=120.0)
    res3 = check_l3_rolling_7d(crew3, duty3, mock_cfg)
    assert not res3.legal
    assert res3.fail_rule == "ILLEGAL_L3"
    assert "flight" in res3.reason

def test_l4_rolling_28d():
    import types

    from crewsim.engine.legality import check_l4_rolling_28d
    from crewsim.engine.state import Block, BlockType
    mock_cfg = types.SimpleNamespace()
    mock_cfg.legality = types.SimpleNamespace()
    mock_cfg.legality.rolling_28d_duty_limit_hours = 190.0
    
    # 28 days is 28 * 24 * 60 = 40320 mins
    # Let's give them 185 hours duty (11100 mins) in the last 28 days
    b1 = Block(start=100000.0 - 20000.0, end=100000.0 - 20000.0 + 11100.0, btype=BlockType.PAIRING, flight_mins=0.0)
    crew = _test_crew([b1])
    
    # Adding a 6 hour duty (360 mins) pushes to 191 hours -> Illegal!
    duty = _test_duty(start=100000.0, end=100000.0 + 360.0)
    res = check_l4_rolling_28d(crew, duty, mock_cfg)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L4"
    assert "190.0h" in res.reason
    
    # Adding a 4 hour duty (240 mins) pushes to 189 hours -> Legal!
    duty2 = _test_duty(start=100000.0, end=100000.0 + 240.0)
    res2 = check_l4_rolling_28d(crew, duty2, mock_cfg)
    assert res2.legal

def test_l5_duty_free_day():
    from crewsim.engine.legality import check_l5_duty_free_day
    
    # 6 days of duty (144h) = 8640 mins.
    # Let's say duty 1 is from 0 to 8000. 
    b1 = Block(start=0.0, end=8000.0, btype=BlockType.PAIRING)
    crew = _test_crew([b1])
    
    # Adding a duty that starts at 8000 and goes to 8640 (total 144h)
    duty_legal = _test_duty(start=8000.0, end=8640.0)
    assert check_l5_duty_free_day(crew, duty_legal).legal
    
    # Adding a duty that pushes beyond 8640 -> Illegal!
    duty_illegal = _test_duty(start=8000.0, end=8641.0)
    res = check_l5_duty_free_day(crew, duty_illegal)
    assert not res.legal
    assert res.fail_rule == "ILLEGAL_L5"
    assert "144h" in res.reason
    
    # If there's a 24 hour gap (1440 mins)
    b2 = Block(start=0.0, end=7000.0, btype=BlockType.PAIRING)
    # Gap from 7000 to 8440 is 1440 mins (24h)
    crew2 = _test_crew([b2])
    duty_after_gap = _test_duty(start=8440.0, end=8440.0 + 8000.0)
    assert check_l5_duty_free_day(crew2, duty_after_gap).legal

def test_l5_ignores_unrelated_preexisting_streak():
    """S1c-04: found while implementing the emergent (whole-calendar) L5
    check -- check_l5_duty_free_day's +/-7d padding window can contain an
    over-length streak that has NOTHING to do with the candidate duty (a
    crew's own unrelated past multi-day trip). The old implementation
    rejected any candidate merely for being co-located in that window with
    such a streak, even when well-separated (>24h gap) from it -- real
    corpus reserves have exactly this shape. Only a streak the candidate
    duty actually overlaps should bind."""
    from crewsim.engine.legality import check_l5_duty_free_day

    # A pre-existing 150h streak, itself over the 144h limit -- but the
    # candidate duty is 4+ days away from it (>24h gap), so it doesn't
    # extend or belong to that streak.
    crew = _test_crew([Block(start=0.0, end=9000.0, btype=BlockType.PAIRING)])
    unrelated_candidate = _test_duty(start=15000.0, end=15500.0)
    res = check_l5_duty_free_day(crew, unrelated_candidate)
    assert res.legal, "candidate wrongly rejected for a streak it doesn't overlap"

    # Sanity: a candidate that DOES extend an over-length streak must still
    # be rejected -- the fix must not become a blanket pass-through.
    extending_candidate = _test_duty(start=8000.0, end=8700.0)
    res2 = check_l5_duty_free_day(crew, extending_candidate)
    assert not res2.legal
    assert res2.fail_rule == "ILLEGAL_L5"

@given(
    cal=calendars(),
    start=st.floats(min_value=0.0, max_value=30000.0, allow_infinity=False, allow_nan=False),
    duration=st.floats(min_value=1.0, max_value=2000.0, allow_infinity=False, allow_nan=False),
)
def test_l5_invariant(cal, start, duration):
    from crewsim.engine.legality import check_l5_duty_free_day
    crew = CrewMember(
        crew_id="test_crew",
        base="YUL",
        fleet_quals={"A330"},
        position="CA",
        seniority=1,
        calendar=cal
    )
    duty = _test_duty(start=start, end=start+duration)
    # The invariant is that check_l5_duty_free_day should never crash
    res = check_l5_duty_free_day(crew, duty)
    assert isinstance(res.legal, bool)

def test_find_l5_calendar_violations():
    """S1c-04: the emergent, whole-calendar form of L5 used by
    `crewsim run --assert-invariants` to verify the rule actually held
    across a real simulation, not just that check_l5_duty_free_day passes
    its own per-assignment unit test."""
    from crewsim.engine.legality import find_l5_calendar_violations

    # A clean calendar: two 6-day-or-shorter duty stretches separated by a
    # real 24h+ gap -- no violation.
    clean = _test_crew([
        Block(start=0.0, end=8000.0, btype=BlockType.PAIRING),
        Block(start=8000.0 + 1440.0, end=8000.0 + 1440.0 + 5000.0, btype=BlockType.RESERVE),
    ])
    assert find_l5_calendar_violations(clean) == []

    # A calendar with a genuine >144h continuous streak (no gap >= 24h
    # anywhere in it) -- a real violation, not injected via a synthetic item.
    violating = _test_crew([
        Block(start=0.0, end=8000.0, btype=BlockType.PAIRING),
        Block(start=8000.0, end=8700.0, btype=BlockType.RESERVE),
    ])
    violations = find_l5_calendar_violations(violating)
    assert len(violations) == 1
    assert violations[0].fail_rule == "ILLEGAL_L5"
    assert "144h" in violations[0].reason

    # Non-duty block types (DAY_OFF, REST, VACATION) must not count toward
    # the streak even if they fill every gap -- only DUTY_BLOCKS types can
    # extend a work streak.
    with_rest_blocks = _test_crew([
        Block(start=0.0, end=8000.0, btype=BlockType.PAIRING),
        Block(start=8000.0, end=8700.0, btype=BlockType.REST),
    ])
    assert find_l5_calendar_violations(with_rest_blocks) == []

def test_find_l5_streak_spans_one_entry_per_streak():
    """S1c-04: a single continuous streak spanning MANY separate blocks
    (each <24h apart from the next) must produce exactly ONE span, not one
    per block still inside the already-over-144h streak. Found as a real
    bug against real corpus data: a 9-block streak for one crew produced 9
    near-duplicate spans (same start, progressively larger end) before
    this fix, which corrupted both the reported violation count and the
    delta comparison in `run --assert-invariants` (every intermediate
    checkpoint compared as a distinct, wrongly-"new" span)."""
    from crewsim.engine.legality import find_l5_streak_spans

    # 9 separate PAIRING blocks, each starting well within 24h of the last
    # one's end, forming one continuous >144h (8640 min) streak:
    # 9*400 + 8*700 = 9200 min total span, well past the 144h threshold.
    blocks = []
    t = 0.0
    for _ in range(9):
        blocks.append(Block(start=t, end=t + 400.0, btype=BlockType.PAIRING))
        t += 400.0 + 700.0  # ~11.7h gap between duties -- well under the 24h reset threshold
    crew = _test_crew(blocks)

    spans = find_l5_streak_spans(crew)
    assert len(spans) == 1
    assert spans[0] == (blocks[0].start, blocks[-1].end)

def test_find_l5_regressions():
    """S1c-04: the delta comparison `run --assert-invariants` uses to
    decide whether drafting/reserve-assignment introduced or worsened an
    L5 violation, as opposed to a pre-existing one already present in the
    static roster baseline."""
    from crewsim.engine.legality import find_l5_regressions

    baseline = [(0.0, 9000.0)]

    # Same violation, unchanged -- not a regression.
    assert find_l5_regressions(baseline, [(0.0, 9000.0)]) == []

    # Shrunk (e.g. a sick call removed a block from the middle) -- an
    # improvement, still contained within the baseline span, not a
    # regression. This is the real case found against corpus data: exact
    # tuple comparison wrongly flagged every such shrink as "new".
    assert find_l5_regressions(baseline, [(0.0, 8500.0)]) == []

    # Genuinely extended beyond the baseline span -- a real regression.
    assert find_l5_regressions(baseline, [(0.0, 9500.0)]) == [(0.0, 9500.0)]

    # A brand new streak with no overlapping baseline entry at all -- a
    # real regression.
    assert find_l5_regressions(baseline, [(20000.0, 30000.0)]) == [(20000.0, 30000.0)]

    # No baseline violations at all, but a post-sim one appears -- the
    # cleanest possible regression case.
    assert find_l5_regressions([], [(0.0, 9000.0)]) == [(0.0, 9000.0)]



# ============================ L0 realized-calendar invariant (S1a-06 / D3) ===


def test_find_l0_violations_catches_two_overlapping_duties():
    """The invariant `run --assert-invariants` reports must be able to fail --
    v2 shipped 1,030 of these, so a check that cannot see one is worthless."""
    crew = _test_crew([
        Block(start=100.0, end=300.0, btype=BlockType.PAIRING),
        Block(start=200.0, end=400.0, btype=BlockType.DRAFTED_DUTY),
    ])
    crew.calendar.sort(key=lambda b: b.start)
    violations = find_l0_violations(crew)
    assert len(violations) == 1
    assert {b.btype for b in violations[0]} == {BlockType.PAIRING, BlockType.DRAFTED_DUTY}


def test_find_l0_violations_ignores_a_draft_over_a_day_off():
    """Drafting a crew member who is OFF is drafting.py's tier 1 -- the
    mandated behaviour, not a double assignment. Flagging it would make the
    invariant fire on every normal draft (measured: 797 false positives across
    3 real scenarios before this was scoped to duty blocks)."""
    crew = _test_crew([
        Block(start=0.0, end=2880.0, btype=BlockType.DAY_OFF),
        Block(start=1000.0, end=1400.0, btype=BlockType.DRAFTED_DUTY),
        Block(start=1400.0, end=2060.0, btype=BlockType.REST),
    ])
    crew.calendar.sort(key=lambda b: b.start)
    assert find_l0_violations(crew) == []


def test_find_l0_violations_ignores_touching_but_non_overlapping_duties():
    """Back-to-back duties share an instant at the boundary; that is adjacency,
    not overlap, and half-open intervals are what the rest of the engine uses."""
    crew = _test_crew([
        Block(start=100.0, end=200.0, btype=BlockType.PAIRING),
        Block(start=200.0, end=300.0, btype=BlockType.DRAFTED_DUTY),
    ])
    crew.calendar.sort(key=lambda b: b.start)
    assert find_l0_violations(crew) == []


def test_find_l0_violations_finds_every_pair_not_just_the_first():
    """Three mutually overlapping duties are three distinct violations -- a
    count that saturates at one would understate a real regression."""
    crew = _test_crew([
        Block(start=100.0, end=500.0, btype=BlockType.PAIRING),
        Block(start=200.0, end=600.0, btype=BlockType.DRAFTED_DUTY),
        Block(start=300.0, end=700.0, btype=BlockType.DEADHEAD),
    ])
    crew.calendar.sort(key=lambda b: b.start)
    assert len(find_l0_violations(crew)) == 3

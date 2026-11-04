import numpy as np

from crewsim import config
from crewsim.engine import roster_loader
from crewsim.engine.sick_calls import apply_named_absence, apply_sick_call
from crewsim.engine.state import Block, BlockType, CrewMember


def test_sick_calls():
    """Verify sick calls sample crew and break pairings into open time."""
    cfg = config.load()
    active, _ = roster_loader.load_rosters(cfg)
    window_start, window_end = roster_loader.select_template_window(cfg)

    # Pin current_time to just before the earliest PAIRING actually loaded,
    # rather than a hardcoded 0.0 -- S1d-04b code review flagged that a bare
    # 0.0 makes this test's pass/fail depend on which window
    # select_template_window happens to resolve (configs/base.yaml's
    # scope.season / windows.holdout can change for unrelated reasons). This
    # way the test stays correct regardless of which window gets picked, as
    # long as the loaded roster has at least one PAIRING -- which
    # test_reserve_lines.py / test_headcount.py already establish it does.
    earliest_pairing_start = min(
        b.start for c in active for b in c.calendar if b.btype == BlockType.PAIRING
    )
    current_time = earliest_pairing_start - 1.0

    # AUD-26: crew selection draws from an injected Generator now, not the
    # reseeded process-global stdlib random.
    c, otis = apply_sick_call(cfg, active, current_time, 3.0, 100, np.random.default_rng(42))

    assert c is not None, (
        f"Should find a crew member about to report "
        f"(template window {window_start} to {window_end}, current_time={current_time})"
    )
    assert len(otis) > 0, "Should generate open time items"

    for oti in otis:
        assert oti.origin == "SICK_CALL"
        # configs/base.yaml's uncovered_deadline_hours is currently 0.0 (a
        # placeholder), so deadline == start today; <= holds either way.
        assert oti.deadline <= oti.start

    # Verify the block is removed
    for b in c.calendar:
        assert b.pairing_id != otis[0].pairing_id, "Pairing block should be removed from calendar"


def test_in_progress_pairing_is_not_reopened():
    """IMP-105: a sick call breaks only pairings that start at or after the call.

    A pairing already under way at the call used to be reopened as an item
    whose deadline (start - lead) was already in the past, so it was born late
    and cancelled. Now the crew member completes the duty in progress, and the
    absence removes them from everything that starts later.
    """
    cfg = config.load()
    crew = CrewMember(
        crew_id="S1", seniority=1, base="YUL", position="FO", fleet_quals={"A321neoLR"},
        calendar=[
            Block(start=900.0, end=1300.0, btype=BlockType.PAIRING,
                  pairing_id="IN_PROGRESS", flight_mins=200.0),
            Block(start=3000.0, end=3400.0, btype=BlockType.PAIRING,
                  pairing_id="LATER", flight_mins=200.0),
        ],
    )
    now = 1000.0
    sick, items = apply_sick_call(cfg, [crew], now, 3.0, 1, np.random.default_rng(0))

    assert sick is crew
    assert [i.pairing_id for i in items] == ["LATER"]
    assert all(i.start >= now for i in items)
    assert any(b.pairing_id == "IN_PROGRESS" for b in crew.calendar), (
        "the duty already under way stays on the calendar (completed)"
    )


def test_crew_with_only_an_in_progress_pairing_is_not_selected():
    """IMP-105: a crew member whose only pairing in the window has already
    started has nothing a sick call could reopen, so they are not a candidate."""
    cfg = config.load()
    crew = CrewMember(
        crew_id="S1", seniority=1, base="YUL", position="FO", fleet_quals={"A321neoLR"},
        calendar=[Block(start=900.0, end=1300.0, btype=BlockType.PAIRING, pairing_id="IN_PROGRESS")],
    )
    sick, items = apply_sick_call(cfg, [crew], 1000.0, 3.0, 1, np.random.default_rng(0))
    assert sick is None and items == []


def test_apply_named_absence_selects_the_named_crew_not_a_random_one():
    cfg = config.load()
    target = CrewMember(crew_id="T1", seniority=1, base="YUL", position="FO", fleet_quals={"A321neoLR"},
                         calendar=[Block(start=100.0, end=500.0, btype=BlockType.PAIRING,
                                         pairing_id="PAIR1", flight_mins=200.0)])
    other = CrewMember(crew_id="T2", seniority=2, base="YUL", position="FO", fleet_quals={"A321neoLR"},
                        calendar=[Block(start=100.0, end=500.0, btype=BlockType.PAIRING,
                                        pairing_id="PAIR2", flight_mins=200.0)])

    crew, items = apply_named_absence(cfg, [target, other], "T1", 0.0, 1000.0, 1)
    assert crew is not None and crew.crew_id == "T1"
    assert [i.pairing_id for i in items] == ["PAIR1"]


def test_apply_named_absence_ignores_pairings_that_started_before_the_window():
    """Regression test (S1e-06/V5 replay): a windowed roster (roster_loader
    load_rosters's window param) can still return a PAIRING block that
    started BEFORE the window if it extends into it -- a duty already
    mid-flight when the replay begins. Breaking it produces an OpenTimeItem
    whose deadline (b.start - dl_hours*60) is already in the past at sim
    time 0, so it cancels instantly with no recovery attempt ever made.
    apply_named_absence must exclude any block with b.start < 0."""
    cfg = config.load()
    crew = CrewMember(crew_id="T1", seniority=1, base="YUL", position="FO", fleet_quals={"A321neoLR"},
                       calendar=[
                           Block(start=-505.0, end=25.0, btype=BlockType.PAIRING,
                                 pairing_id="ALREADY_IN_PROGRESS", flight_mins=200.0),
                           Block(start=200.0, end=500.0, btype=BlockType.PAIRING,
                                 pairing_id="STARTS_IN_WINDOW", flight_mins=200.0),
                       ])

    _, items = apply_named_absence(cfg, [crew], "T1", 0.0, 1000.0, 1)
    assert [i.pairing_id for i in items] == ["STARTS_IN_WINDOW"], (
        "a pairing that started before the replay window must not be broken -- "
        "its item would be born already past its own deadline"
    )

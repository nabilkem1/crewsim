import random

from crewsim import config

from .state import Block, BlockType, CrewMember, OpenTimeItem


def _break_pairings(
    cfg: config.BaseConfig, c: CrewMember, overlapping_blocks: list[Block], uid_counter: int
) -> list[OpenTimeItem]:
    """Shared by apply_sick_call (random crew) and apply_named_absence
    (S1e-06: a specific real crew_id) -- both need the identical
    deadline-calc + OpenTimeItem-construction + calendar-removal logic once
    the affected crew member and their overlapping PAIRING blocks are known;
    only HOW that crew/blocks pair is chosen differs between the two."""
    open_time = []
    for b in overlapping_blocks:
        if b.btype != BlockType.PAIRING:
            continue
        dl_hours = 0.0
        if cfg.demand is not None:
            if isinstance(cfg.demand.uncovered_deadline_hours, dict):
                dl_hours = cfg.demand.uncovered_deadline_hours.get("default", 0.0)
            else:
                dl_hours = float(cfg.demand.uncovered_deadline_hours)

        deadline = b.start - (dl_hours * 60.0)
        oti = OpenTimeItem(
            uid=uid_counter,
            pairing_id=b.pairing_id or "UNKNOWN",
            base=c.base,
            fleet=next(iter(c.fleet_quals)) if c.fleet_quals else "UNKNOWN",
            position=c.position,
            start=b.start,
            end=b.end,
            deadline=deadline,
            origin="SICK_CALL",
            root_event_uid=uid_counter,
            # S1b-04 (P2): carried through, matching cascade.py's own item
            # construction. Without it L3's rolling-flight-hour check saw 0
            # added flight time for every sick-call-origin item and so
            # under-rejected candidates who were near the 35h limit. This does
            # change legality outcomes on existing CRN scenarios -- it is a
            # correctness fix, not a refactor, and the numbers move.
            flight_mins=b.flight_mins,
        )
        uid_counter += 1
        open_time.append(oti)

        if b in c.calendar:
            c.calendar.remove(b)

    return open_time


def apply_sick_call(cfg: config.BaseConfig, active_crew: list[CrewMember], current_time: float, duration_days: float, uid_counter: int) -> tuple[CrewMember | None, list[OpenTimeItem]]:
    """
    Applies a sick call to a random crew member who is on or about to report for duty (PAIRING).
    Returns the removed CrewMember and a list of OpenTimeItems generated from their broken pairings.
    """
    # 1. Sample from crew who are on or about to report for duty.
    # "About to report" means starting a PAIRING within the next 24 hours, for instance.
    eligible = []

    # We look for someone with a PAIRING block overlapping [current_time, current_time + duration_days * 1440]
    # or just starting within 24 hours. Sim time is minutes since horizon start (S1d-04b), not seconds.
    search_end = current_time + (duration_days * 1440.0)
    for c in active_crew:
        blocks = c.blocks_in(current_time, search_end)
        has_pairing = any(b.btype == BlockType.PAIRING for b in blocks)
        if has_pairing:
            eligible.append((c, blocks))

    if not eligible:
        return None, []

    c, overlapping_blocks = random.choice(eligible)

    # 2. The absent crew member is removed for the sampled duration; multi-day absences break several pairings
    # 3. Their pairing(s) become open-time items with the correct deadline
    open_time = _break_pairings(cfg, c, overlapping_blocks, uid_counter)
    return c, open_time


def apply_named_absence(
    cfg: config.BaseConfig, active_crew: list[CrewMember], crew_id: str, start_min: float, end_min: float,
    uid_counter: int,
) -> tuple[CrewMember | None, list[OpenTimeItem]]:
    """S1e-06 (V5 replay): same pairing-breaking logic as apply_sick_call,
    but for a NAMED real crew member over a real [start_min, end_min)
    absence window (D4's real absence_start/absence_end), instead of a
    random crew member over a duration-based search from an arrival
    instant. Kept as a sibling function rather than unifying the two: the
    selection semantics genuinely differ, and apply_sick_call's random path
    (used by every existing CRN scenario) must not risk any behavioural
    change.
    """
    crew_by_id = {c.crew_id: c for c in active_crew}
    c = crew_by_id.get(crew_id)
    if c is None:
        return None, []

    # b.start >= 0 (not just an overlap with [start_min, end_min)): a
    # calendar loaded for a windowed replay (roster_loader.load_rosters's
    # window param) still returns blocks that started before the window if
    # they extend into it -- a duty already mid-flight when the replay
    # begins. Its deadline (b.start - dl_hours*60) would then already be in
    # the past at sim time 0, so the item is born past its own deadline and
    # cancels instantly with NO recovery attempt ever made -- a decision
    # with nothing to show, which fails S1e-06's own AC. Excluding it is
    # correct, not a workaround: the normal CRN engine (apply_sick_call)
    # never produces this case either, since every item it creates has
    # item.start within the SAME horizon its "now" is measured against.
    overlapping_blocks = [
        b for b in c.blocks_in(start_min, end_min) if b.btype == BlockType.PAIRING and b.start >= 0
    ]
    open_time = _break_pairings(cfg, c, overlapping_blocks, uid_counter)
    return c, open_time

import numpy as np

from crewsim import config

from .state import Block, BlockType, CrewMember, OpenTimeItem


def uncovered_deadline_minutes(cfg: config.BaseConfig) -> float:
    """The configured lead time (minutes before report) at which an uncovered
    item cancels -- `demand.uncovered_deadline_hours`, `default` key when the
    config carries a per-haul dict.

    THE single definition (AUD-20): it used to be re-derived inline in
    _break_pairings, des.displaced_flying_source, and hardcoded as a bare
    `60.0` in cascade.compute_draft_delta -- so cascade items cancelled on a
    different clock than every other item and sweeping the configured
    deadline did not move them.
    """
    if cfg.demand is None:
        return 0.0
    raw = cfg.demand.uncovered_deadline_hours
    dl_hours = raw.get("default", 0.0) if isinstance(raw, dict) else float(raw)
    return dl_hours * 60.0


def _break_pairings(
    cfg: config.BaseConfig, c: CrewMember, overlapping_blocks: list[Block], uid_counter: int
) -> list[OpenTimeItem]:
    """Shared by apply_sick_call (random crew) and apply_named_absence
    (S1e-06: a specific real crew_id) -- both need the identical
    deadline-calc + OpenTimeItem-construction + calendar-removal logic once
    the affected crew member and their overlapping PAIRING blocks are known;
    only HOW that crew/blocks pair is chosen differs between the two."""
    open_time = []
    lead = uncovered_deadline_minutes(cfg)
    for b in overlapping_blocks:
        if b.btype != BlockType.PAIRING:
            continue
        oti = OpenTimeItem(
            uid=uid_counter,
            pairing_id=b.pairing_id or "UNKNOWN",
            base=c.base,
            fleet=c.primary_fleet,
            position=c.position,
            start=b.start,
            end=b.end,
            deadline=b.start - lead,
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


def _mark_unavailable(c: CrewMember, start: float, end: float) -> None:
    """AUD-02 / spec §5.0.4 E1's second clause: the absent crew member is
    physically unavailable for the whole absence, not merely relieved of the
    pairings it broke. The ABSENCE block is in legality.OCCUPYING_BLOCKS, so
    L0 rejects any assignment overlapping it -- without this the sick crew
    member remained a legal tier-1 draft candidate and could be selected to
    cover the very pairing their own absence created."""
    if end <= start:
        return
    c.calendar.append(Block(start=start, end=end, btype=BlockType.ABSENCE))
    c.calendar.sort(key=lambda b: b.start)


def apply_sick_call(
    cfg: config.BaseConfig,
    active_crew: list[CrewMember],
    current_time: float,
    duration_days: float,
    uid_counter: int,
    rng: np.random.Generator,
) -> tuple[CrewMember | None, list[OpenTimeItem]]:
    """
    Applies a sick call to a random crew member who is on or about to report for duty (PAIRING).
    Returns the removed CrewMember and a list of OpenTimeItems generated from their broken pairings.

    `rng` is the caller's per-arrival CRN generator (AUD-26): crew selection
    used to run through the process-global stdlib `random`, reseeded per
    arrival -- deterministic, but exactly the hidden global state §4.3 bans,
    and one stray `random` consumer away from silently breaking CRN.
    """
    # 1. Sample from crew who have a PAIRING that has not yet started and
    # reports within the absence window [current_time, current_time +
    # duration). Sim time is minutes since horizon start (S1d-04b).
    #
    # IMP-105: only FUTURE pairings (start >= current_time) are broken. A
    # pairing already under way at the call is not reopened -- it used to be,
    # and its deadline (start - lead) was then already in the past, so it was
    # born late and cancelled after at most a token attempt, inflating
    # cancellations. The rule now: a crew member who falls sick mid-pairing
    # completes the duty already in progress (it stays on their calendar), and
    # the absence removes them from everything that starts after the call.
    eligible = []
    search_end = current_time + (duration_days * 1440.0)
    for c in active_crew:
        future_pairings = [
            b for b in c.blocks_in(current_time, search_end)
            if b.btype == BlockType.PAIRING and b.start >= current_time
        ]
        if future_pairings:
            eligible.append((c, future_pairings))

    if not eligible:
        return None, []

    c, overlapping_blocks = eligible[int(rng.integers(len(eligible)))]

    # 2. The absent crew member is removed for the sampled duration; multi-day absences break several pairings
    # 3. Their pairing(s) become open-time items with the correct deadline
    open_time = _break_pairings(cfg, c, overlapping_blocks, uid_counter)
    # 4. And they are unavailable for anything else until the absence ends (E1).
    _mark_unavailable(c, current_time, search_end)
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
    # never produces this case either -- since IMP-105 it breaks only
    # pairings with start >= the call time.
    overlapping_blocks = [
        b for b in c.blocks_in(start_min, end_min) if b.btype == BlockType.PAIRING and b.start >= 0
    ]
    open_time = _break_pairings(cfg, c, overlapping_blocks, uid_counter)
    # E1's unavailability clause, clamped to the replay window's own clock:
    # an absence that began before minute 0 still blocks the crew from 0.
    _mark_unavailable(c, max(start_min, 0.0), end_min)
    return c, open_time

from dataclasses import dataclass
from typing import Any

from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


@dataclass(frozen=True)
class LegalityResult:
    legal: bool
    fail_rule: str | None = None
    reason: str | None = None

OCCUPYING_BLOCKS = {
    BlockType.DRAFTED_DUTY,
    BlockType.REST,
    BlockType.DEADHEAD,
}

DUTY_BLOCKS = {
    BlockType.PAIRING,
    BlockType.RESERVE,
    BlockType.DRAFTED_DUTY,
    BlockType.DEADHEAD,
    BlockType.SIMULATOR,
    BlockType.TRAINING,
}

def check_l0_single_assignment(crew: CrewMember, start: float, end: float) -> LegalityResult:
    """
    Rule L0: Single assignment.
    A crew member holds at most one duty at any instant.
    The checked span `[start, end]` should include the duty plus the rest it obliges.
    PAIRING, VACATION, SIMULATOR, etc. are not in the occupying set (can be drafted off them).
    """
    overlapping = crew.blocks_in(start, end)
    for block in overlapping:
        if block.btype in OCCUPYING_BLOCKS:
            return LegalityResult(legal=False, fail_rule="ILLEGAL_L0", reason="Double assignment (L0)")
    
    return LegalityResult(legal=True, fail_rule=None)

MINUTES_PER_HOUR = 60.0


def _require_legality_cfg(cfg: Any, rule: str) -> Any:
    if not cfg or not getattr(cfg, "legality", None):
        raise ValueError(f"{rule} check requires legality configuration in cfg")
    return cfg.legality


def min_rest_minutes(cfg: Any, crew_base: str, duty_base: str) -> float:
    """The rest a duty at `duty_base` obliges for a crew member based at `crew_base`.

    THE single definition of L2's rest requirement. It used to be written out
    four separate times -- legality.py (twice), drafting.py, cascade.py and
    des.py each re-deriving `11 * 60 if same base else 10 * 60` -- so the four
    could drift apart silently and a CBA change meant editing all of them. They
    all call this now, and the hours themselves come from
    configs/base.yaml -> legality (S1a-02/S1a-07).
    """
    legality = _require_legality_cfg(cfg, "L2")
    hours = (legality.min_rest_hours_home if crew_base == duty_base
             else legality.min_rest_hours_away)
    return float(hours) * MINUTES_PER_HOUR


def check_l1_max_duty(item: OpenTimeItem, cfg: Any = None) -> LegalityResult:
    """
    L1: Max duty period, legality.max_duty_hours (13 h today).
    Conservative bias: a flat bound ignores CARs FDP tables, which can allow up
    to 14h depending on start time and sectors. This stricter bound ensures
    surrogate-legal is truly legal.
    """
    limit_hours = _require_legality_cfg(cfg, "L1").max_duty_hours
    duration_mins = item.end - item.start
    if duration_mins > limit_hours * MINUTES_PER_HOUR:
        return LegalityResult(
            legal=False, fail_rule="ILLEGAL_L1",
            reason=f"Max duty period {limit_hours:.0f}h exceeded "
                   f"({duration_mins / MINUTES_PER_HOUR:.1f}h)",
        )
    return LegalityResult(legal=True)

def check_l2_min_rest(crew: CrewMember, item: OpenTimeItem, cfg: Any = None) -> LegalityResult:
    """
    L2: Min rest before duty, legality.min_rest_hours_home/_away (11 h / 10 h today).
    Conservative bias: Always demands the full figure, ignoring split-duty or
    reduced rest provisions that might permit shorter rests in disruption.
    """
    req_mins = min_rest_minutes(cfg, crew.base, item.base)

    latest_duty_end = 0.0
    for b in crew.calendar:
        if b.start >= item.start:
            break
        if b.btype in DUTY_BLOCKS and b.end <= item.start:
            latest_duty_end = max(latest_duty_end, b.end)

    if latest_duty_end > 0:
        rest_mins = item.start - latest_duty_end
        if rest_mins < req_mins:
            return LegalityResult(
                legal=False, fail_rule="ILLEGAL_L2",
                reason=f"Insufficient rest ({rest_mins / MINUTES_PER_HOUR:.1f}h < "
                       f"{req_mins / MINUTES_PER_HOUR:.1f}h)",
            )

    return LegalityResult(legal=True)

def check_l6_qualifications(crew: CrewMember, item: OpenTimeItem) -> LegalityResult:
    """
    L6: Qualification: type rating and position must match.
    Conservative bias: Hard-binding binary check. No allowance for mixed-fleet
    flying (MFF) or flying in a lower position, even if technically legal.
    """
    if item.fleet not in crew.fleet_quals:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L6", reason=f"Wrong type rating (needs {item.fleet})")
    if crew.position != item.position:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L6", reason=f"Wrong position (needs {item.position})")
    return LegalityResult(legal=True)

def check_l7_base(crew: CrewMember, item: OpenTimeItem, is_deadhead: bool = False) -> LegalityResult:
    """
    L7: Crew must start duty at own base unless deadheaded.
    Conservative bias: Does not support complex multi-base positioning sequences;
    demands strict base match for pure assignments.
    """
    if not is_deadhead and crew.base != item.base:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L7", reason=f"Base mismatch ({crew.base} != {item.base})")
    return LegalityResult(legal=True)

def check_l8_notice_time(crew: CrewMember, item: OpenTimeItem, now: float | None = None, cfg: Any = None) -> LegalityResult:
    """
    L8: Reserve notification time.
    Short-call and long-call minimum notice limits pulled from config.
    Applied against the call time (`now`), not the report time.
    """
    if now is None:
        return LegalityResult(legal=True)
        
    notice_mins = item.start - now

    # Find the active reserve block at the CALL time (`now`), not the report
    # time -- a reserve's SC/LC classification is which on-call regime they
    # were under when actually notified, and that block can differ from the
    # one covering item.start if a call happens near a shift boundary.
    reserve_type = "SC" # Default if not found
    for b in crew.blocks_in(now, now):
        if b.btype == BlockType.RESERVE and b.start <= now and b.end > now:
            reserve_type = b.reserve_call_type or "SC"
            break
            
    if not cfg or not cfg.legality:
        raise ValueError("L8 check requires legality configuration in cfg")
        
    sc_hours = cfg.legality.short_call_notice_hours
    lc_hours = cfg.legality.long_call_notice_hours
    
    req_mins = sc_hours * 60 if reserve_type == "SC" else lc_hours * 60
    
    if notice_mins < req_mins:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L8", reason=f"Insufficient notice ({notice_mins/60:.1f}h < {req_mins/60:.1f}h for {reserve_type})")
        
    return LegalityResult(legal=True)

def check_l3_rolling_7d(crew: CrewMember, item: OpenTimeItem, cfg: Any = None) -> LegalityResult:
    """
    L3: 60 h duty / 35 h flight in a rolling 7 days.
    """
    if not cfg or not cfg.legality:
        raise ValueError("L3 check requires legality configuration in cfg")
        
    duty_limit = cfg.legality.rolling_7d_duty_limit_hours * 60
    flight_limit = cfg.legality.rolling_7d_flight_limit_hours * 60
    
    duty_7d, flight_7d = crew.get_rolling_counters(item.start, 7)
    
    # We must also add the current item being assigned
    added_duty = item.end - item.start
    added_flight = item.flight_mins
    
    if (duty_7d + added_duty) > duty_limit:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L3", reason=f"Rolling 7d duty exceeded ({(duty_7d + added_duty)/60:.1f}h > {duty_limit/60:.1f}h)")
        
    if (flight_7d + added_flight) > flight_limit:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L3", reason=f"Rolling 7d flight exceeded ({(flight_7d + added_flight)/60:.1f}h > {flight_limit/60:.1f}h)")
        
    return LegalityResult(legal=True)

def check_l4_rolling_28d(crew: CrewMember, item: OpenTimeItem, cfg: Any = None) -> LegalityResult:
    """
    L4: 190 h duty in a rolling 28 days.
    """
    if not cfg or not cfg.legality:
        raise ValueError("L4 check requires legality configuration in cfg")
        
    duty_limit = cfg.legality.rolling_28d_duty_limit_hours * 60
    
    duty_28d, _ = crew.get_rolling_counters(item.start, 28)
    added_duty = item.end - item.start
    
    if (duty_28d + added_duty) > duty_limit:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L4", reason=f"Rolling 28d duty exceeded ({(duty_28d + added_duty)/60:.1f}h > {duty_limit/60:.1f}h)")
        
    return LegalityResult(legal=True)

def check_l5_duty_free_day(crew: CrewMember, item: OpenTimeItem) -> LegalityResult:
    """
    L5: One duty-free day (24 hours) per rolling 7 days.
    Equivalent to: No continuous period of duty (or duties separated by < 24h)
    can span more than 6 days (144 hours = 8640 minutes).
    """
    window_start = item.start - (7 * 24 * 60.0)
    window_end = item.end + (7 * 24 * 60.0)
    
    duty_btypes = {
        BlockType.PAIRING, BlockType.RESERVE, BlockType.DRAFTED_DUTY, 
        BlockType.DEADHEAD, BlockType.SIMULATOR, BlockType.TRAINING
    }
    
    duties = []
    for b in crew.blocks_in(window_start, window_end):
        if b.btype in duty_btypes:
            duties.append((b.start, b.end))
            
    duties.append((item.start, item.end))
    duties.sort(key=lambda x: x[0])
    
    if not duties:
        return LegalityResult(legal=True)
        
    merged: list[tuple[float, float]] = []
    for d in duties:
        if not merged:
            merged.append(d)
        else:
            last = merged[-1]
            if d[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], d[1]))
            else:
                merged.append(d)
                
    streak_start = merged[0][0]
    for i in range(len(merged)):
        _curr_start, curr_end = merged[i]

        if (curr_end - streak_start) > 6 * 24 * 60.0:  # noqa: SIM102 - the nested check carries the comment below; collapsing orphans it
            # Only a violation if `item` is actually part of THIS streak --
            # the +/-7d padding window can contain an unrelated pre-existing
            # over-length streak (real corpus data: a crew's own past
            # multi-day trip) that has nothing to do with the candidate
            # duty being evaluated. Rejecting item for a streak it doesn't
            # even overlap was a real bug (found while implementing S1c-04):
            # verified against real reserves, it over-rejected candidates
            # near unrelated historical streaks.
            if item.start < curr_end and item.end > streak_start:
                return LegalityResult(
                    legal=False,
                    fail_rule="ILLEGAL_L5",
                    reason=f"Work streak exceeded 144h without 24h rest ({streak_start} to {curr_end})"
                )

        if i + 1 < len(merged):
            next_start, _next_end = merged[i+1]
            gap = next_start - curr_end
            if gap >= 24 * 60.0:
                streak_start = next_start

    return LegalityResult(legal=True)

def find_l0_violations(crew: CrewMember) -> list[tuple[Block, Block]]:
    """Every pair of overlapping DUTY blocks in a crew's REALIZED calendar --
    i.e. every place this crew is rostered to work two things at once
    (S1a-06 / defect D3, which produced 1,030 of these in v2).

    The realized-calendar analogue of check_l0_single_assignment, which asks the
    same question about one candidate assignment before it is made. This audits
    the calendar drafting and reserve assignment actually produced, which is
    what `run --assert-invariants` needs: that command promises "0 overlapping
    duty blocks across N scenarios" and until this existed had no way to count
    them (it checked V3 eligibility and L5 streaks, neither of which is L0).

    Scoped to DUTY_BLOCKS on BOTH sides, deliberately:

      * DAY_OFF overlapping a DRAFTED_DUTY is not a violation, it is the
        mandated behaviour -- drafting a crew member who is off is exactly
        drafting.py's tier 1, and the engine consumes the day rather than
        splitting the block.
      * REST is not a duty. It is an obligation that BLOCKS further duty (which
        is why it is in OCCUPYING_BLOCKS for the pre-assignment check), but a
        rest period overlapping the day off it is spent on is normal.

    So the invariant here is the physically impossible thing: two DUTIES at the
    same instant. Returns the offending pairs, not a count, so a failure names
    the blocks.
    """
    ordered = sorted(crew.calendar, key=lambda b: b.start)
    duties = [b for b in ordered if b.btype in DUTY_BLOCKS]
    violations: list[tuple[Block, Block]] = []
    for i, a in enumerate(duties):
        for b in duties[i + 1:]:
            if b.start >= a.end:
                break  # sorted by start: nothing later can overlap `a` either
            violations.append((a, b))
    return violations


def find_l5_streak_spans(crew: CrewMember) -> list[tuple[float, float]]:
    """The (streak_start, streak_end) span of every >144h duty streak in a
    crew's ENTIRE realized calendar (not one candidate assignment against a
    sliding window, as check_l5_duty_free_day does per-assignment). Same
    merge-and-streak algorithm as check_l5_duty_free_day, applied directly
    to the whole calendar.

    Returns spans, not just a count: `run --assert-invariants` (S1c-04)
    compares a crew's post-simulation spans against their pre-simulation
    baseline spans to detect NEW or WORSENED (extended) violations -- two
    calendars can have the same violation COUNT while one has a genuinely
    different violating streak than the other (one healed, a different one
    appeared), which a count comparison alone would miss.
    """
    duties = [(b.start, b.end) for b in crew.calendar if b.btype in DUTY_BLOCKS]
    duties.sort(key=lambda x: x[0])

    if not duties:
        return []

    merged: list[tuple[float, float]] = []
    for d in duties:
        if not merged:
            merged.append(d)
        else:
            last = merged[-1]
            if d[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], d[1]))
            else:
                merged.append(d)

    # One entry per maximal streak (a run of merged blocks connected by
    # <24h gaps), emitted once the streak actually ends -- not once per
    # merged block still inside an already-over-144h streak. Checking
    # "over 144h" on every intermediate block (as check_l5_duty_free_day
    # does, which is safe there since it short-circuit-returns on the
    # first hit) would emit the SAME ongoing streak many times here, one
    # per block, since curr_end keeps growing while streak_start stays
    # fixed until a real 24h+ gap is reached.
    spans = []
    streak_start = merged[0][0]
    for i in range(len(merged)):
        _curr_start, curr_end = merged[i]
        is_last = i == len(merged) - 1
        gap_to_next = merged[i + 1][0] - curr_end if not is_last else None
        streak_ends_here = is_last or (gap_to_next is not None and gap_to_next >= 24 * 60.0)

        if streak_ends_here:
            if (curr_end - streak_start) > 6 * 24 * 60.0:
                spans.append((streak_start, curr_end))
            if not is_last:
                streak_start = merged[i + 1][0]

    return spans

def find_l5_calendar_violations(crew: CrewMember) -> list[LegalityResult]:
    """LegalityResult wrapper around find_l5_streak_spans, for reporting
    (used directly wherever a human-readable reason is wanted, e.g. a
    raw-count summary; the delta comparison below uses find_l5_streak_spans
    directly since it needs span identity, not just a printable reason)."""
    return [
        LegalityResult(
            legal=False,
            fail_rule="ILLEGAL_L5",
            reason=f"{crew.crew_id}: work streak exceeded 144h without 24h rest ({s} to {e})",
        )
        for s, e in find_l5_streak_spans(crew)
    ]

def find_l5_regressions(
    baseline_spans: list[tuple[float, float]], post_spans: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """Post-simulation L5 streaks NOT contained within any baseline streak
    -- i.e. genuinely NEW or WORSENED (extended) violations, used by
    `crewsim run --assert-invariants` (S1c-04) to check whether
    drafting/reserve-assignment introduces or extends an L5 violation
    relative to the crew's pre-simulation static-roster calendar.

    Containment, not exact-span equality: a post-sim streak that starts no
    earlier and ends no later than some baseline streak is the SAME
    violation (or an improvement -- e.g. a sick call removing a block from
    the middle of a baseline streak shrinks its span), not a new one. Exact
    tuple comparison would wrongly flag every such shrink as "new".
    """
    return [
        (s, e) for s, e in post_spans
        if not any(bs <= s and e <= be for bs, be in baseline_spans)
    ]

def is_legal_assignment(crew: CrewMember, duty: OpenTimeItem, is_deadhead: bool = False, now: float | None = None, cfg: Any = None) -> LegalityResult:
    """
    Check physical feasibility (L0) and rest/qualification surrogate rules (L1-L8).
    Currently implemented: L0, L1, L2, L3, L4, L5, L6, L7, L8.
    """
    end_with_rest = duty.end + min_rest_minutes(cfg, crew.base, duty.base)

    r0 = check_l0_single_assignment(crew, duty.start, end_with_rest)
    if not r0.legal: return r0

    r1 = check_l1_max_duty(duty, cfg)
    if not r1.legal: return r1

    r2 = check_l2_min_rest(crew, duty, cfg)
    if not r2.legal: return r2
    
    r3 = check_l3_rolling_7d(crew, duty, cfg)
    if not r3.legal: return r3
    
    r4 = check_l4_rolling_28d(crew, duty, cfg)
    if not r4.legal: return r4
    
    r5 = check_l5_duty_free_day(crew, duty)
    if not r5.legal: return r5
    
    r6 = check_l6_qualifications(crew, duty)
    if not r6.legal: return r6
    
    r7 = check_l7_base(crew, duty, is_deadhead)
    if not r7.legal: return r7
    
    r8 = check_l8_notice_time(crew, duty, now, cfg)
    if not r8.legal: return r8
    
    return LegalityResult(legal=True)

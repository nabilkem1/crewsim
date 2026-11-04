from dataclasses import dataclass
from typing import Any

from crewsim.engine.state import DUTY_BLOCKS as _STATE_DUTY_BLOCKS
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
    # AUD-02 / spec §5.0.4 E1: a sick crew member is "marked unavailable for
    # the absence duration". The ABSENCE block sick_calls inserts makes that
    # unavailability physical -- without it the sick crew member read as a
    # free tier-1 draft candidate for their whole absence.
    BlockType.ABSENCE,
}

# Re-exported: state.py owns the definition (see the note there).
DUTY_BLOCKS = _STATE_DUTY_BLOCKS


def _counts_reserve_as_duty(cfg: Any) -> bool:
    """AUD-24: whether on-call-but-not-flying hours ACCRUE toward the rolling
    limits (L3, L4) and the L5 work streak.

    A [CONFIRM: Labour Relations] question, swept rather than assumed --
    `configs/base.yaml -> legality.reserve_counts_as_duty`. Defaults True (the
    conservative reading, and the long-standing behaviour) when no config is
    supplied, so the many unit tests that call these rules with a bare cfg
    keep their existing meaning.

    Note this governs ACCRUAL only. It never affects L0: two overlapping
    duties are physically impossible whatever the accrual rule says, so
    `find_l0_violations` keeps the full DUTY_BLOCKS set.
    """
    legality = getattr(cfg, "legality", None) if cfg is not None else None
    if legality is None:
        return True
    return bool(getattr(legality, "reserve_counts_as_duty", True))


def accrual_duty_blocks(cfg: Any = None) -> frozenset[BlockType]:
    """DUTY_BLOCKS, minus RESERVE when on-call time does not accrue."""
    if _counts_reserve_as_duty(cfg):
        return DUTY_BLOCKS
    return DUTY_BLOCKS - {BlockType.RESERVE}

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


def check_l0_pairing_in_progress(
    crew: CrewMember, start: float, end: float, now: float | None
) -> LegalityResult:
    """IMP-104, the half of L0 that needs the call time.

    PAIRING is deliberately not an OCCUPYING block: a line holder can be
    drafted off a FUTURE pairing, which then re-enters as open time
    (cascade.compute_draft_delta). But a pairing that has already started at
    the call -- `b.start <= now < b.end` -- is being flown. Drafting off it
    would reopen a trip that is in the air, and the resulting cascade item
    would be born past its own deadline. So the assignment window
    `[start, end)` (duty plus the rest it obliges) must not overlap a pairing
    already under way. Skipped when `now` is unknown, like L8.
    """
    if now is None:
        return LegalityResult(legal=True)
    for b in crew.blocks_in(start, end):
        if b.btype == BlockType.PAIRING and b.start <= now < b.end:
            return LegalityResult(
                legal=False, fail_rule="ILLEGAL_L0",
                reason=f"Pairing {b.pairing_id} already under way at the call (L0)",
            )
    return LegalityResult(legal=True)


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

def on_call_block(crew: CrewMember, when: float) -> Block | None:
    """The RESERVE block covering `when`, or None.

    THE definition of "on call at an instant" -- the eligibility pool, the
    remaining-window dispatch rule, the V3 historical reconstruction, the
    trace's alternatives log and L8 all use it, so they cannot drift apart.
    Lives here rather than in eligibility.py because eligibility imports this
    module; eligibility re-exports it under the same name.
    """
    for b in crew.calendar:
        if b.btype == BlockType.RESERVE and b.start <= when < b.end:
            return b
    return None


def reserve_call_type_for(crew: CrewMember, item: OpenTimeItem, now: float) -> str | None:
    """Which reserve notice rule ("SC" / "LC") L8 applies, or None for a line holder.

    IMP-116. The call-time block wins: a reserve's SC/LC classification is the
    on-call regime they were under when actually notified, and near a shift
    boundary that block can differ from the one covering the report. When no
    block covers the call -- a reserve called between shifts for a duty in
    their next shift -- the block covering the REPORT time decides, because
    that block is exactly what admitted them to the eligibility pool
    (`is_on_call_at(r, item.start)`). Before IMP-116 that case returned None,
    so a reserve picked AS a reserve was held to the line-holder notice
    (`line_holder_draft_notice_hours`, 0 h today) instead of SC/LC notice.

    Only a crew member with no RESERVE block at either instant -- a line
    holder, or a reserve outside both windows -- gets None.
    """
    block = on_call_block(crew, now) or on_call_block(crew, item.start)
    if block is None:
        return None
    return block.reserve_call_type or "SC"


def check_l8_notice_time(crew: CrewMember, item: OpenTimeItem, now: float | None = None, cfg: Any = None) -> LegalityResult:
    """
    L8: Reserve notification time.
    Short-call and long-call minimum notice limits pulled from config.
    Applied against the call time (`now`), not the report time.

    AUD-10: L8 applies ONLY to a crew member who is actually on reserve at
    the call time. §5.4 defines it as a reserve call-out rule ("minimum
    notification-to-report 2 h short-call / 12 h long-call"); no notice rule
    is specified for drafting a line holder. The previous implementation
    defaulted every non-reserve to "SC", silently inventing a 2 h draft
    notice floor that made last-minute drafts structurally impossible.
    """
    if now is None:
        return LegalityResult(legal=True)

    notice_mins = item.start - now
    reserve_type = reserve_call_type_for(crew, item, now)

    if not cfg or not cfg.legality:
        raise ValueError("L8 check requires legality configuration in cfg")

    if reserve_type is None:
        # Not on reserve when called: the reserve short/long-call rule does
        # not apply. IMP-104: the line-holder drafting notice comes from
        # configs/base.yaml -> legality.line_holder_draft_notice_hours (a
        # [CONFIRM: Crew Planning] value, 0.0 today -- AUD-10 removed the 2 h
        # floor that had been invented here). Even at 0.0 the call must not
        # come after the report: a duty that has already started cannot be
        # drafted for.
        req_mins = float(cfg.legality.line_holder_draft_notice_hours) * 60
        if notice_mins < req_mins:
            return LegalityResult(
                legal=False, fail_rule="ILLEGAL_L8",
                reason=f"Insufficient draft notice ({notice_mins/60:.1f}h < {req_mins/60:.1f}h for a line holder)",
            )
        return LegalityResult(legal=True)

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

    duty_7d, flight_7d = crew.get_rolling_counters(
        item.start, 7, count_reserve_as_duty=_counts_reserve_as_duty(cfg)
    )
    
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

    duty_28d, _ = crew.get_rolling_counters(
        item.start, 28, count_reserve_as_duty=_counts_reserve_as_duty(cfg)
    )
    added_duty = item.end - item.start
    
    if (duty_28d + added_duty) > duty_limit:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L4", reason=f"Rolling 28d duty exceeded ({(duty_28d + added_duty)/60:.1f}h > {duty_limit/60:.1f}h)")
        
    return LegalityResult(legal=True)

def check_l5_duty_free_day(
    crew: CrewMember, item: OpenTimeItem, cfg: Any = None
) -> LegalityResult:
    """
    L5: One duty-free day (24 hours) per rolling 7 days.
    Equivalent to: No continuous period of duty (or duties separated by < 24h)
    can span more than 6 days (144 hours = 8640 minutes).

    Whether on-call time counts toward the streak follows the same AUD-24
    flag as L3/L4 -- a run of standby days is only a "work streak" if
    standby is work.
    """
    window_start = item.start - (7 * 24 * 60.0)
    window_end = item.end + (7 * 24 * 60.0)

    duty_btypes = accrual_duty_blocks(cfg)
    duties = [(b.start, b.end) for b in crew.blocks_in(window_start, window_end) if b.btype in duty_btypes]
    duties.append((item.start, item.end))

    for streak_start, streak_end in _over_limit_streaks(duties):
        # Only a violation if `item` is actually part of THIS streak -- the
        # +/-7d padding window can contain an unrelated pre-existing
        # over-length streak (real corpus data: a crew's own past multi-day
        # trip) that has nothing to do with the candidate duty being
        # evaluated. Rejecting item for a streak it doesn't even overlap was a
        # real bug (found while implementing S1c-04): verified against real
        # reserves, it over-rejected candidates near unrelated historical
        # streaks.
        if item.start < streak_end and item.end > streak_start:
            return LegalityResult(
                legal=False,
                fail_rule="ILLEGAL_L5",
                reason=f"Work streak exceeded 144h without 24h rest ({streak_start} to {streak_end})"
            )
    return LegalityResult(legal=True)


_L5_MAX_STREAK_MINUTES = 6 * 24 * 60.0   # 144 h of work ...
_L5_MIN_BREAK_MINUTES = 24 * 60.0        # ... before a 24 h duty-free break


def _over_limit_streaks(duties: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Every maximal work streak longer than 144 h, as (start, end).

    IMP-612: the one L5 merge-and-streak algorithm, shared by the
    per-assignment check (check_l5_duty_free_day) and the whole-calendar
    audit (find_l5_streak_spans), which used to carry a copy each.

    Overlapping duties are merged first; consecutive merged blocks separated
    by less than 24 h belong to the same streak. One entry per maximal
    streak, emitted once the streak ends -- never once per block still inside
    an already-over-limit streak.
    """
    if not duties:
        return []
    merged: list[tuple[float, float]] = []
    for start, end in sorted(duties, key=lambda d: d[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    spans: list[tuple[float, float]] = []
    streak_start = merged[0][0]
    for i, (_start, curr_end) in enumerate(merged):
        is_last = i == len(merged) - 1
        if is_last or merged[i + 1][0] - curr_end >= _L5_MIN_BREAK_MINUTES:
            if curr_end - streak_start > _L5_MAX_STREAK_MINUTES:
                spans.append((streak_start, curr_end))
            if not is_last:
                streak_start = merged[i + 1][0]
    return spans

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


def find_duty_during_rest_violations(crew: CrewMember) -> list[tuple[Block, Block]]:
    """Every (duty, rest) pair where a DUTY block overlaps a REST block in a
    crew's realized calendar -- crew working during mandatory rest.

    AUD-11: `find_l0_violations` deliberately excludes REST from its scan
    (rest overlapping the day off it is spent on is normal), but that also
    made it blind to the opposite case -- a duty inserted INTO a rest period,
    which is exactly the violation class the pre-AUD-01 `blocks_in` bug let
    through. This is the missing half of the V8 invariant: REST blocks
    further duty (it is in OCCUPYING_BLOCKS for the pre-assignment check),
    so a realized calendar where a duty sits inside one is as physically
    wrong as two overlapping duties.
    """
    duties = sorted((b for b in crew.calendar if b.btype in DUTY_BLOCKS), key=lambda b: b.start)
    rests = sorted((b for b in crew.calendar if b.btype == BlockType.REST), key=lambda b: b.start)
    violations: list[tuple[Block, Block]] = []
    for duty in duties:
        for rest in rests:
            if rest.start >= duty.end:
                break
            if duty.start < rest.end and duty.end > rest.start:
                violations.append((duty, rest))
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
    return _over_limit_streaks([(b.start, b.end) for b in crew.calendar if b.btype in DUTY_BLOCKS])

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

    r0b = check_l0_pairing_in_progress(crew, duty.start, end_with_rest, now)
    if not r0b.legal: return r0b

    r1 = check_l1_max_duty(duty, cfg)
    if not r1.legal: return r1

    r2 = check_l2_min_rest(crew, duty, cfg)
    if not r2.legal: return r2
    
    r3 = check_l3_rolling_7d(crew, duty, cfg)
    if not r3.legal: return r3
    
    r4 = check_l4_rolling_28d(crew, duty, cfg)
    if not r4.legal: return r4
    
    r5 = check_l5_duty_free_day(crew, duty, cfg)
    if not r5.legal: return r5
    
    r6 = check_l6_qualifications(crew, duty)
    if not r6.legal: return r6
    
    r7 = check_l7_base(crew, duty, is_deadhead)
    if not r7.legal: return r7
    
    r8 = check_l8_notice_time(crew, duty, now, cfg)
    if not r8.legal: return r8
    
    return LegalityResult(legal=True)

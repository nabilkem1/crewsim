from dataclasses import dataclass
from crewsim.engine.state import CrewMember, BlockType, OpenTimeItem

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

def check_l1_max_duty(item: OpenTimeItem) -> LegalityResult:
    """
    L1: Max duty period 13 h.
    Conservative bias: Flat 13h bound ignores CARs FDP tables which can allow up to 14h
    depending on start time and sectors. This stricter bound ensures surrogate-legal
    is truly legal.
    """
    duration_mins = item.end - item.start
    if duration_mins > 13 * 60:
        return LegalityResult(legal=False, fail_rule="ILLEGAL_L1", reason=f"Max duty period 13h exceeded ({duration_mins/60:.1f}h)")
    return LegalityResult(legal=True)

def check_l2_min_rest(crew: CrewMember, item: OpenTimeItem) -> LegalityResult:
    """
    L2: Min rest before duty: 11 h at home base, 10 h away.
    Conservative bias: Always demands full 11h/10h, ignoring split-duty or
    reduced rest provisions that might permit shorter rests in disruption.
    """
    latest_duty_end = 0.0
    for b in crew.calendar:
        if b.start >= item.start:
            break
        if b.btype in DUTY_BLOCKS and b.end <= item.start:
            if b.end > latest_duty_end:
                latest_duty_end = b.end
                
    if latest_duty_end > 0:
        rest_mins = item.start - latest_duty_end
        req_mins = 11 * 60 if item.base == crew.base else 10 * 60
        if rest_mins < req_mins:
            return LegalityResult(legal=False, fail_rule="ILLEGAL_L2", reason=f"Insufficient rest ({rest_mins/60:.1f}h < {req_mins/60:.1f}h)")
            
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

def is_legal_assignment(crew: CrewMember, duty: OpenTimeItem, is_deadhead: bool = False) -> LegalityResult:
    """
    Check physical feasibility (L0) and rest/qualification surrogate rules (L1-L8).
    Currently implemented: L0, L1, L2, L6, L7.
    """
    obliged_rest = 11 * 60 if duty.base == crew.base else 10 * 60
    end_with_rest = duty.end + obliged_rest
    
    r0 = check_l0_single_assignment(crew, duty.start, end_with_rest)
    if not r0.legal: return r0
        
    r1 = check_l1_max_duty(duty)
    if not r1.legal: return r1
    
    r2 = check_l2_min_rest(crew, duty)
    if not r2.legal: return r2
    
    r6 = check_l6_qualifications(crew, duty)
    if not r6.legal: return r6
    
    r7 = check_l7_base(crew, duty, is_deadhead)
    if not r7.legal: return r7
    
    return LegalityResult(legal=True)

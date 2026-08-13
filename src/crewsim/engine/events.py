from .state import Block, BlockType, CrewMember


def assign_reserve(
    crew: CrewMember,
    duty_start: float,
    duty_end: float,
    min_rest: float,
    pairing_id: str,
    deadhead_start: float | None = None,
) -> None:
    """
    E3: Reserve Assigned.
    Splits the overlapping RESERVE block around [duty_start, duty_end + min_rest].
    Inserts DRAFTED_DUTY and REST blocks.
    (This fulfills E3 splitting and prepares the calendar for E6/E7).

    S1c-07: `deadhead_start` positions a CROSS-BASE reserve first. The crew is
    occupied from `deadhead_start`, not from `duty_start` -- a DEADHEAD block
    fills the gap, because positioning "costs a seat and consumes duty time"
    (00_Intro glossary). Extending the occupancy here rather than in a second
    cross-base-only assignment function is deliberate: one implementation means
    the local and cross-base paths cannot drift, and the DEADHEAD block is a
    real calendar block that L1/L2/L3 and the L0 invariant all see, not a free
    teleport into position.
    """
    occupy_start = duty_start if deadhead_start is None else deadhead_start
    if occupy_start > duty_start:
        raise ValueError(
            f"deadhead_start {deadhead_start} is after duty_start {duty_start}: "
            f"positioning must finish before the duty it positions for"
        )

    # The reserve must be ON CALL when the occupancy STARTS -- at report time,
    # or at the deadhead report for a cross-base dispatch. Not for the whole
    # duty: since OPEN-4 a duty may legitimately run past the end of the shift
    # that authorised it (a reserve called during standby flies the trip out),
    # so requiring full coverage here would reject exactly the assignments the
    # eligibility rule now permits.
    rest_end = duty_end + min_rest
    res_block = next(
        (b for b in crew.calendar
         if b.btype == BlockType.RESERVE and b.start <= occupy_start < b.end),
        None,
    )
    if res_block is None:
        raise ValueError(
            f"Crew {crew.crew_id} holds no RESERVE block covering {occupy_start}"
        )

    # Every RESERVE block the occupancy runs through is consumed, not just the
    # one it starts in -- a duty plus its rest can span the end of tonight's
    # shift and into tomorrow's, and leaving those standing would show the
    # crew member on call while they are flying or resting.
    consumed = [
        b for b in crew.calendar
        if b.btype == BlockType.RESERVE and b.start < rest_end and b.end > occupy_start
    ]
    for b in consumed:
        crew.calendar.remove(b)

    # 1. Block before the occupancy starts (if any)
    if res_block.start < occupy_start:
        crew.calendar.append(Block(start=res_block.start, end=occupy_start, btype=BlockType.RESERVE, reserve_call_type=res_block.reserve_call_type))

    # 1b. The positioning trip itself, for a cross-base reserve
    if deadhead_start is not None and deadhead_start < duty_start:
        crew.calendar.append(
            Block(start=deadhead_start, end=duty_start, btype=BlockType.DEADHEAD, pairing_id=pairing_id)
        )

    # 2. The duty block
    duty = Block(start=duty_start, end=duty_end, btype=BlockType.DRAFTED_DUTY, pairing_id=pairing_id)
    crew.calendar.append(duty)
    
    # 3. The rest block (we insert it here, or at E6. The spec is slightly contradictory, 
    # but functionally the calendar needs the REST block to prevent overlapping assignments).
    rest = Block(start=duty_end, end=duty_end + min_rest, btype=BlockType.REST)
    crew.calendar.append(rest)
    
    # 4. The restored reserve window(s) after rest (E7).
    # Restored from EVERY consumed block, not just the one the duty started in:
    # if the duty and its rest end partway through a later shift, the remainder
    # of that shift is still on-call time the crew member owes.
    for b in consumed:
        if b.end > rest_end:
            crew.calendar.append(
                Block(start=max(b.start, rest_end), end=b.end,
                      btype=BlockType.RESERVE, reserve_call_type=b.reserve_call_type)
            )

    crew.calendar.sort(key=lambda b: b.start)

def end_duty(crew: CrewMember, duty_block: Block) -> None:
    """
    E6: DUTY_END
    In a full DES, this would fire at duty_block.end.
    For calendar state, it might just update accumulators.
    """

def end_rest(crew: CrewMember, rest_block: Block) -> None:
    """
    E7: REST_END
    Fires at rest_block.end. Crew becomes assignable again.
    (Since we pre-inserted the restored RESERVE block in assign_reserve, the calendar is already correct).
    """

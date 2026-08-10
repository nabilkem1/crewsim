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

    # The RESERVE block has to COVER the whole occupancy, not merely overlap it.
    # Overlap was enough before S1c-07 and never bit, because the eligibility
    # pool independently requires full coverage of the duty -- but it left the
    # door open to positioning a crew member during hours they were not yet on
    # call, which is exactly the shape the cross-base path introduces.
    blocks = crew.blocks_in(occupy_start, duty_end)
    res_blocks = [
        b for b in blocks
        if b.btype == BlockType.RESERVE and b.start <= occupy_start and b.end >= duty_end
    ]

    if not res_blocks:
        raise ValueError(f"Crew {crew.crew_id} has no RESERVE block overlapping [{occupy_start}, {duty_end}]")

    res_block = res_blocks[0]
    crew.calendar.remove(res_block)

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
    
    # 4. The restored reserve block after rest (E7 restored window)
    # The spec says E7 restores it, but in a calendar model it's often easier to just schedule the blocks now.
    if duty_end + min_rest < res_block.end:
        crew.calendar.append(Block(start=duty_end + min_rest, end=res_block.end, btype=BlockType.RESERVE, reserve_call_type=res_block.reserve_call_type))
        
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

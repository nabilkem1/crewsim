from typing import List, Optional
from .state import CrewMember, Block, BlockType

def assign_reserve(crew: CrewMember, duty_start: float, duty_end: float, min_rest: float, pairing_id: str) -> None:
    """
    E3: Reserve Assigned.
    Splits the overlapping RESERVE block around [duty_start, duty_end + min_rest].
    Inserts DRAFTED_DUTY and REST blocks.
    (This fulfills E3 splitting and prepares the calendar for E6/E7).
    """
    # Find the overlapping RESERVE block
    blocks = crew.blocks_in(duty_start, duty_end)
    res_blocks = [b for b in blocks if b.btype == BlockType.RESERVE]
    
    if not res_blocks:
        raise ValueError(f"Crew {crew.crew_id} has no RESERVE block overlapping [{duty_start}, {duty_end}]")
        
    res_block = res_blocks[0]
    crew.calendar.remove(res_block)
    
    # 1. Block before duty (if any)
    if res_block.start < duty_start:
        crew.calendar.append(Block(start=res_block.start, end=duty_start, btype=BlockType.RESERVE, reserve_call_type=res_block.reserve_call_type))
        
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
    pass

def end_rest(crew: CrewMember, rest_block: Block) -> None:
    """
    E7: REST_END
    Fires at rest_block.end. Crew becomes assignable again.
    (Since we pre-inserted the restored RESERVE block in assign_reserve, the calendar is already correct).
    """
    pass

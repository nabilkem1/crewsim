"""cascade — see spec §5. Implemented in a later story; shape fixed by S0-00."""

from crewsim.config import BaseConfig
from crewsim.engine.legality import min_rest_minutes
from crewsim.engine.sick_calls import uncovered_deadline_minutes
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem, StateDelta


def compute_draft_delta(crew: CrewMember, item: OpenTimeItem, cfg: BaseConfig, now: float) -> tuple[StateDelta, list[OpenTimeItem]]:
    """
    Computes the StateDelta when drafting `crew` for `item`.
    Identifies future PAIRING blocks that are overlapped or structurally broken
    by the new duty and its mandatory rest period.
    Returns the delta and the generated OpenTimeItems from the cascaded pairings.
    """
    delta = StateDelta(crew_id=crew.crew_id)
    
    # 1. Add the new drafted duty block
    new_duty = Block(
        start=item.start,
        end=item.end,
        btype=BlockType.DRAFTED_DUTY,
        pairing_id=item.pairing_id,
        flight_mins=item.flight_mins
    )
    delta.added_blocks.append(new_duty)
    
    # Mandatory rest after duty, from configs/base.yaml -> legality via the one
    # shared definition (legality.min_rest_minutes). This module used to
    # re-derive the same 11h/10h figure itself, which meant a cascade could in
    # principle disagree with the legality check that authorised the draft.
    mandatory_rest_end = item.end + min_rest_minutes(cfg, crew.base, item.base)
    
    # Add the rest block
    new_rest = Block(
        start=item.end,
        end=mandatory_rest_end,
        btype=BlockType.REST
    )
    delta.added_blocks.append(new_rest)
    
    cascaded_items = []
    
    # 2. Find pairings and reserve blocks that overlap the duty OR the mandatory rest
    # We find blocks in [item.start, mandatory_rest_end]
    overlapping = crew.blocks_in(item.start, mandatory_rest_end)
    
    # Any PAIRING or RESERVE block that overlaps this period is broken.
    for b in overlapping:
        if b.btype == BlockType.PAIRING:
            delta.removed_blocks.append(b)
            
            # The removed pairing re-enters as an OpenTimeItem
            cascaded_items.append(
                OpenTimeItem(
                    uid=0, # engine must re-assign uid
                    # Block.pairing_id is Optional; OpenTimeItem requires one. A
                    # RESERVE/DAY_OFF block reaching here has no pairing to name,
                    # so mark it explicitly rather than letting None through.
                    pairing_id=b.pairing_id or "UNKNOWN",
                    base=crew.base,
                    fleet=next(iter(crew.fleet_quals)), # simplification
                    position=crew.position,
                    start=b.start,
                    end=b.end,
                    # AUD-20: the same config-derived cancellation lead every
                    # other item uses -- this was a hardcoded `b.start - 60.0`,
                    # so cascade items cancelled on their own private clock.
                    deadline=b.start - uncovered_deadline_minutes(cfg),
                    origin="CASCADE",
                    root_event_uid=item.root_event_uid,
                    flight_mins=b.flight_mins
                )
            )
        elif b.btype == BlockType.RESERVE:
            # A future reserve block is cancelled because they are on duty or mandatory rest.
            # This structurally shrinks the reserve pool on that day.
            # No OpenTimeItem is generated because it's a loss of capacity, not an uncovered flight.
            delta.removed_blocks.append(b)
            
    return delta, cascaded_items

def apply_delta(crew: CrewMember, delta: StateDelta) -> None:
    """
    Applies the StateDelta to the crew member's calendar.
    """
    assert crew.crew_id == delta.crew_id
    
    # Remove broken blocks
    for b in delta.removed_blocks:
        if b in crew.calendar:
            crew.calendar.remove(b)
            
    # Add new blocks
    for b in delta.added_blocks:
        crew.calendar.append(b)
        
    # Sort calendar
    crew.calendar.sort(key=lambda x: x.start)

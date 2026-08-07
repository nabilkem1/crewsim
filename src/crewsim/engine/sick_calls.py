import random
from typing import List, Tuple
from .state import CrewMember, BlockType, OpenTimeItem, Block

from crewsim import config

def apply_sick_call(cfg: config.BaseConfig, active_crew: List[CrewMember], current_time: float, duration_days: float, uid_counter: int) -> Tuple[CrewMember, List[OpenTimeItem]]:
    """
    Applies a sick call to a random crew member who is on or about to report for duty (PAIRING).
    Returns the removed CrewMember and a list of OpenTimeItems generated from their broken pairings.
    """
    # 1. Sample from crew who are on or about to report for duty.
    # "About to report" means starting a PAIRING within the next 24 hours, for instance.
    eligible = []
    
    # We look for someone with a PAIRING block overlapping [current_time, current_time + duration_days * 86400]
    # or just starting within 24 hours.
    search_end = current_time + (duration_days * 86400)
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
    
    open_time = []
    
    for b in overlapping_blocks:
        if b.btype == BlockType.PAIRING:
            # Create open time item
            dl_hours = 0.0
            if cfg.demand is not None:
                if isinstance(cfg.demand.uncovered_deadline_hours, dict):
                    # We would look up by route type if we had it; default for now
                    dl_hours = cfg.demand.uncovered_deadline_hours.get("default", 0.0)
                else:
                    dl_hours = float(cfg.demand.uncovered_deadline_hours)
                    
            deadline = b.start - (dl_hours * 3600.0)
            oti = OpenTimeItem(
                uid=uid_counter,
                pairing_id=b.pairing_id or "UNKNOWN",
                base=c.base,
                fleet=list(c.fleet_quals)[0] if c.fleet_quals else "UNKNOWN",
                position=c.position,
                start=b.start,
                end=b.end,
                deadline=deadline,
                origin="SICK_CALL",
                root_event_uid=uid_counter
            )
            uid_counter += 1
            open_time.append(oti)
            
            # Remove pairing from their calendar and replace with LONG_TERM_ABSENCE / SICK
            # For simplicity in state modeling, we can just change the btype of the block or remove it.
            # In a real model we might split blocks. We'll just remove the pairing block for now.
            if b in c.calendar:
                c.calendar.remove(b)
                
    return c, open_time

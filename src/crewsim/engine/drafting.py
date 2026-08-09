from typing import Any

from crewsim.engine.legality import is_legal_assignment, min_rest_minutes
from crewsim.engine.state import BlockType, CrewMember, OpenTimeItem


def determine_tier(crew: CrewMember, item: OpenTimeItem, cfg: Any = None) -> int:
    """
    Determine the impact tier (1-4) of drafting a crew member for the given item.
    Tier 1: No duty (DAY_OFF or empty calendar)
    Tier 2: Holds a pairing that conflicts (PAIRING)
    Tier 3: Ground training (TRAINING)
    Tier 4: Vacation or Simulator (VACATION, SIMULATOR)

    The window examined is the duty plus the rest it obliges -- the same span
    is_legal_assignment checks, via the same min_rest_minutes helper, so the
    tier and the legality verdict can never disagree about how long a draft
    actually ties a crew member up.
    """
    end_with_rest = item.end + min_rest_minutes(cfg, crew.base, item.base)
    overlapping = crew.blocks_in(item.start, end_with_rest)
    
    tier = 1
    for b in overlapping:
        if b.btype in (BlockType.VACATION, BlockType.SIMULATOR):
            return 4
        elif b.btype == BlockType.TRAINING:
            tier = max(tier, 3)
        elif b.btype == BlockType.PAIRING:
            tier = max(tier, 2)
            
    return tier

def select_draft_candidate(
    roster: list[CrewMember],
    item: OpenTimeItem,
    junior_first: bool = False,
    cfg: Any = None,
    now: float | None = None,
) -> CrewMember | None:
    """
    Select the best candidate for drafting.
    Filters by L0-L8 legality, groups by impact tier, and sorts by seniority within the tier.
    Per Air Transat policy: senior-first is standard (lowest seniority number).
    """
    legal_candidates = [c for c in roster if is_legal_assignment(c, item, now=now, cfg=cfg).legal]
    if not legal_candidates:
        return None
        
    # Group by tier
    tiers: dict[int, list[CrewMember]] = {1: [], 2: [], 3: [], 4: []}
    for c in legal_candidates:
        tier = determine_tier(c, item, cfg)
        tiers[tier].append(c)
        
    # Find the lowest non-empty tier (1 is best, 4 is worst)
    for tier in range(1, 5):
        candidates = tiers[tier]
        if candidates:
            # Sort by seniority. Lower number = more senior.
            # If junior_first is True, we reverse it (highest number first).
            candidates.sort(key=lambda c: c.seniority, reverse=junior_first)
            return candidates[0]
            
    return None

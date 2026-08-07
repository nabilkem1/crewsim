import datetime
import polars as pl
from typing import Tuple, Dict, List
from .. import config
from ..data import loaders
from .state import CrewMember, Block, BlockType

from .policy import Policy

def load_rosters(cfg: config.BaseConfig, base: str = None, fleet: str = None, position: str = None, policy: Policy = None) -> Tuple[List[CrewMember], Dict[str, int]]:
    """
    Loads crew from D1 and their blocks from D2.
    If policy is provided, carves out N reserves based on the policy and strips their D2 pairing blocks.
    Returns:
        (active_crew_list, exclusion_counts)
    """
    d1 = loaders.load_dataset(cfg, "d1_crew_master")
    d2 = loaders.load_dataset(cfg, "d2_rosters")
    
    # Filter D1 first if requested
    if base:
        d1 = d1.filter(pl.col("base") == base)
    if position:
        d1 = d1.filter(pl.col("position") == position)
    # the dataset uses "fleet" column
    if fleet:
        # Some rows might have fleet empty? 
        d1 = d1.filter(pl.col("fleet").str.contains(fleet) | (pl.col("fleet") == fleet))

    # Determine exclusions based on employment_status
    # We count reasons
    exclusion_counts = {
        "LONG_TERM_ABSENCE": 0,
        "INITIAL_TRAINING": 0,
        "FLEET_TRANSITION": 0,
        "MANAGEMENT_OR_INSTRUCTOR": 0,
        "TERMINATED": 0,
        "OTHER": 0
    }
    
    active_crew = []
    
    crew_dict = {}
    
    for row in d1.iter_rows(named=True):
        status = row["employment_status"]
        if status != "ACTIVE":
            if status in exclusion_counts:
                exclusion_counts[status] += 1
            else:
                exclusion_counts["OTHER"] += 1
            continue
            
        crew_id = row["crew_id"]
        # fleet_family or fleet? Let's use fleet for fleet_quals
        fleet = row["fleet"]
        
        c = CrewMember(
            crew_id=crew_id,
            base=row["base"],
            fleet_quals={fleet},
            position=row["position"],
            seniority=row["seniority_number"],
            calendar=[]
        )
        crew_dict[crew_id] = c
        
    # Group D2 by crew_id
    # Sort d2 by start_utc
    # In D2, block_type is a string. Start/end are strings.
    # Convert string to float (UNIX timestamp)
    
    # We must collect rows in python to parse date to float, or do it in polars
    
    # To float: 
    def to_ts(s) -> float:
        if isinstance(s, str):
            return datetime.datetime.fromisoformat(s).timestamp()
        return s.timestamp()
        
    for row in d2.sort("start_utc").iter_rows(named=True):
        c_id = row["crew_id"]
        if c_id not in crew_dict:
            continue
            
        c = crew_dict[c_id]
        
        try:
            btype = BlockType(row["block_type"])
        except ValueError:
            # Fallback or skip if unknown block type? Spec says we should handle basic ones
            continue
            
        start = to_ts(row["start_utc"])
        end = to_ts(row["end_utc"])
        pairing_id = row["pairing_id"] if row["pairing_id"] else None
        r_type = row["reserve_call_type"] if row["reserve_call_type"] else None
        
        b = Block(start=start, end=end, btype=btype, pairing_id=pairing_id, reserve_call_type=r_type)
        c.calendar.append(b)
        
    # Validate calendars (L0 - non overlapping, sorted)
    for c in crew_dict.values():
        c.calendar.sort(key=lambda b: b.start)
        for i in range(1, len(c.calendar)):
            prev = c.calendar[i-1]
            curr = c.calendar[i]
            if curr.start < prev.end:
                raise ValueError(f"L0 Violation: Overlapping blocks for {c.crew_id}: {prev} and {curr}")
                
        active_crew.append(c)
        
    if policy:
        # We need to apply reserves per target
        # Map target -> max reserves
        target_reserves = {}
        for r in policy.stage1.reserves:
            # fleet_quals is a set, we'll just match the fleet string
            key = (r.base, r.fleet, r.position)
            daily = r.short_call + r.long_call
            if daily > target_reserves.get(key, 0):
                target_reserves[key] = daily
                
        # Group crew by target
        # Note: A crew member can have multiple fleet_quals, but usually a primary one in D1. 
        # In D1, we mapped `fleet` to `fleet_quals={fleet}`. We can just use that single fleet for grouping.
        from collections import defaultdict
        groups = defaultdict(list)
        for c in active_crew:
            f = list(c.fleet_quals)[0] if c.fleet_quals else ""
            groups[(c.base, f, c.position)].append(c)
            
        reserve_crew_all = []
        line_crew_all = []
        
        for key, crew_list in groups.items():
            n_res = target_reserves.get(key, 0)
            
            # Find authentic reserve patterns in D2 for this group
            authentic_reserve_calendars = []
            for c in crew_list:
                if any(b.btype == BlockType.RESERVE for b in c.calendar):
                    # Clean the pattern: strip PAIRINGs so it's a pure reserve line
                    clean_cal = [b for b in c.calendar if b.btype != BlockType.PAIRING]
                    authentic_reserve_calendars.append(clean_cal)
                    
            # Sort by seniority BOTTOM_UP (highest number is most junior)
            crew_list.sort(key=lambda c: c.seniority, reverse=True)
            
            res = crew_list[:n_res]
            lin = crew_list[n_res:]
            
            # Assign patterns to minted reserves
            import itertools
            if authentic_reserve_calendars:
                pattern_cycle = itertools.cycle(authentic_reserve_calendars)
            else:
                pattern_cycle = itertools.cycle([[]]) # fallback if none exist
                
            for c in res:
                c._is_reserve = True
                # Give them a real reserve pattern from the pool
                c.calendar = next(pattern_cycle)
            reserve_crew_all.extend(res)
            
            for c in lin:
                c._is_reserve = False
                c.calendar = [b for b in c.calendar if b.btype != BlockType.RESERVE]
            line_crew_all.extend(lin)
            
        active_crew = reserve_crew_all + line_crew_all
        active_crew.sort(key=lambda c: c.crew_id)
        
    return active_crew, exclusion_counts

import datetime

import polars as pl

from .. import config
from ..data import loaders
from .policy import Policy
from .state import Block, BlockType, CrewMember


def select_template_window(cfg: config.BaseConfig) -> tuple[datetime.date, datetime.date]:
    """S1d-04b: pick the historical window whose roster pattern stands in for the
    bid period being modelled (scope.bid_period is future and by definition isn't
    in the historical corpus, so a literal date anchor doesn't exist).

    The most recent complete `horizon.horizon_days`-length span inside the
    `holdout` window whose calendar months all fall within `scope.season`'s
    months (configs/seasons.yaml). That window IS the full
    warmup+measurement+cooldown horizon; its own start becomes sim minute 0.
    Returns (window_start, window_end) as dates, window_end exclusive.
    """
    if cfg.windows is None:
        raise ValueError("select_template_window requires cfg.windows (holdout window) to be configured")
    holdout = cfg.windows.get("holdout")
    season_months = set(loaders.load_seasons(cfg)[cfg.scope.season])
    horizon_days = cfg.horizon.horizon_days

    latest_start = holdout.end - datetime.timedelta(days=horizon_days - 1)
    start = latest_start
    while start >= holdout.start:
        days_touched = [start + datetime.timedelta(days=d) for d in range(horizon_days)]
        if {d.month for d in days_touched} <= season_months:
            end = start + datetime.timedelta(days=horizon_days)
            return start, end
        start -= datetime.timedelta(days=1)

    raise ValueError(
        f"No {horizon_days}-day window inside holdout [{holdout.start}, {holdout.end}] "
        f"falls entirely within scope.season={cfg.scope.season!r} "
        f"months={sorted(season_months)}"
    )


def _load_pairing_duty_periods(
    cfg: config.BaseConfig,
) -> dict[str, list[tuple[datetime.datetime, datetime.datetime, float]]]:
    """S1d-04b2: per pairing_id, the real duty periods within it (D3), each a
    single report-to-release span (~4-9h in this corpus) -- not the whole
    multi-day pairing D2 rolls it up into (48-120h, which fails legality.py's
    L1 13h max-duty rule by construction for every single one of them).

    report_local is constant across a duty period's legs; release_local
    increases per leg, so the duty's actual end is the LAST leg's
    release_local (confirmed against the raw data before writing this).
    """
    legs = loaders.load_dataset(cfg, "d3_pairing_legs")
    agg = (
        legs.group_by(["pairing_id", "duty_period"])
        .agg(
            [
                pl.col("report_local").min().alias("duty_start"),
                pl.col("release_local").max().alias("duty_end"),
                pl.col("block_hours").sum().alias("flight_hours"),
            ]
        )
        .sort(["pairing_id", "duty_period"])
    )
    out: dict[str, list[tuple[datetime.datetime, datetime.datetime, float]]] = {}
    for row in agg.iter_rows(named=True):
        out.setdefault(row["pairing_id"], []).append(
            (row["duty_start"], row["duty_end"], float(row["flight_hours"]))
        )
    return out


def load_rosters(
    cfg: config.BaseConfig,
    base: str | None = None,
    fleet: str | None = None,
    position: str | None = None,
    policy: Policy | None = None,
    window: tuple[datetime.date, datetime.date] | None = None,
) -> tuple[list[CrewMember], dict[str, int]]:
    """
    Loads crew from D1 and their blocks from D2, restricted to `window`
    (default: the S1d-04b template window, see select_template_window), with
    block times converted to minutes since that window's start -- the
    convention every other engine module uses (legality.py, cascade.py,
    costs.py).
    If policy is provided, carves out N reserves based on the policy and strips their D2 pairing blocks.
    `window` lets a caller load a much wider span than a single simulation
    horizon -- e.g. S0-04's real historical eligibility reconstruction,
    which needs D2's real calendars across the whole fitting/holdout window
    (months), not one ~6-week template slice.
    Returns:
        (active_crew_list, exclusion_counts)
    """
    d1 = loaders.load_dataset(cfg, "d1_crew_master")
    d2 = loaders.load_dataset(cfg, "d2_rosters")

    window_start, window_end = window if window is not None else select_template_window(cfg)
    anchor = datetime.datetime.combine(window_start, datetime.time.min)
    window_end_dt = datetime.datetime.combine(window_end, datetime.time.min)
    
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
        "OTHER": 0,
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
        
    # Group D2 by crew_id, restricted to the template window, with times
    # converted to minutes since window_start -- never .timestamp(): D2's
    # timestamps are naive ISO strings, and .timestamp() interprets naive
    # datetimes in the local system timezone, which would make the engine's
    # numbers depend on which machine ran it.
    def parse_dt(s: str | datetime.datetime) -> datetime.datetime:
        return datetime.datetime.fromisoformat(s) if isinstance(s, str) else s

    def to_minutes(dt: datetime.datetime) -> float:
        return (dt - anchor).total_seconds() / 60.0

    duty_periods_by_pairing = _load_pairing_duty_periods(cfg)

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

        start_dt = parse_dt(row["start_utc"])
        end_dt = parse_dt(row["end_utc"])

        # Only blocks overlapping the template window belong in this run's calendar.
        if end_dt <= anchor or start_dt >= window_end_dt:
            continue

        pairing_id = row["pairing_id"] if row["pairing_id"] else None
        r_type = row["reserve_call_type"] if row["reserve_call_type"] else None

        if btype == BlockType.PAIRING and pairing_id in duty_periods_by_pairing:
            # Replace the flat multi-day span with D3's real duty periods.
            # D3 only has "_local" times; D2 has both "_utc" and "_local" for
            # this same row, so derive this row's own UTC offset from its own
            # pair rather than hardcoding a base's timezone (bases differ,
            # hardcoding invites a DST bug).
            utc_offset = start_dt - parse_dt(row["start_local"])
            for duty_start_local, duty_end_local, flight_hours in duty_periods_by_pairing[pairing_id]:
                duty_start = duty_start_local + utc_offset
                duty_end = duty_end_local + utc_offset
                if duty_end <= anchor or duty_start >= window_end_dt:
                    continue
                c.calendar.append(
                    Block(
                        start=to_minutes(duty_start), end=to_minutes(duty_end), btype=BlockType.PAIRING,
                        pairing_id=pairing_id, flight_mins=flight_hours * 60.0,
                    )
                )
            continue

        b = Block(
            start=to_minutes(start_dt), end=to_minutes(end_dt), btype=btype,
            pairing_id=pairing_id, reserve_call_type=r_type,
        )
        c.calendar.append(b)
        
    # Validate calendars (L0 - non overlapping, sorted).
    for c in crew_dict.values():
        c.calendar.sort(key=lambda b: b.start)
        for i in range(1, len(c.calendar)):
            prev = c.calendar[i - 1]
            curr = c.calendar[i]
            if curr.start < prev.end:
                raise ValueError(
                    f"L0 Violation: crew {c.crew_id} calendar has overlapping "
                    f"blocks {prev} and {curr}. See S1d-04b2 (blocked): D3-derived "
                    f"PAIRING duty-period ends routinely spill past D2's own "
                    f"pairing-end boundary into the next D2-scheduled block -- "
                    f"this is not yet reconciled."
                )

        active_crew.append(c)
        
    if policy:
        # We need to apply reserves per target
        # Map target -> max reserves
        target_reserves: dict[tuple[str, str, str], int] = {}
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
            f = next(iter(c.fleet_quals)) if c.fleet_quals else ""
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

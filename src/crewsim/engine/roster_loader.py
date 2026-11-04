import dataclasses
import datetime
from collections import Counter
from typing import Any

import polars as pl

from .. import config
from ..data import coverage, loaders
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

    # IMP-516: the roster this window stands in for must actually be recorded.
    # D2 may stop being filled in before its last row; a template window past that
    # point would be a calendar of nothing.
    # (A hand-built cfg with no data section -- a test stub of the window inputs --
    # has no corpus to ask.)
    d2_interval = (
        coverage.dataset_interval(cfg, "d2_rosters") if getattr(cfg, "data", None) is not None else None
    )

    latest_start = holdout.end - datetime.timedelta(days=horizon_days - 1)
    start = latest_start
    while start >= holdout.start:
        days_touched = [start + datetime.timedelta(days=d) for d in range(horizon_days)]
        in_season = {d.month for d in days_touched} <= season_months
        recorded = d2_interval is None or (
            d2_interval.contains(days_touched[0]) and d2_interval.contains(days_touched[-1])
        )
        if in_season and recorded:
            end = start + datetime.timedelta(days=horizon_days)
            return start, end
        start -= datetime.timedelta(days=1)

    recorded_note = (
        f" and inside the recorded span of the D2 rosters ({d2_interval.label()})"
        if d2_interval is not None else ""
    )
    raise ValueError(
        f"No {horizon_days}-day window inside holdout [{holdout.start}, {holdout.end}] "
        f"falls entirely within scope.season={cfg.scope.season!r} "
        f"months={sorted(season_months)}{recorded_note}"
    )


DutyPeriods = dict[str, list[tuple[datetime.datetime, datetime.datetime, float]]]


def _load_pairing_duty_periods(
    cfg: config.BaseConfig,
) -> tuple[DutyPeriods, set[str], set[str]]:
    """S1d-04b2: per pairing_id, the real duty periods within it (D3), each a
    single report-to-release span (~4-9h in this corpus) -- not the whole
    multi-day pairing D2 rolls it up into (48-120h, which fails legality.py's
    L1 13h max-duty rule by construction for every single one of them).

    report_local is constant across a duty period's legs; release_local
    increases per leg, so the duty's actual end is the LAST leg's
    release_local (confirmed against the raw data before writing this).

    Returns (duty periods, incomplete pairings, estimated pairings).

    IMP-520: a pairing with a duty period whose report or release time is
    missing in D3 is `incomplete` and has NO entry in the duty periods -- the
    caller falls back to D2's own span for it and counts it, instead of
    crashing on `None + timedelta`. A leg whose block_hours is 0 or missing
    gets the hours between its own departure and arrival; a pairing that had
    to do so is `estimated`.
    """
    legs = loaders.load_dataset(cfg, "d3_pairing_legs")
    supplied = pl.col("block_hours")
    derived = (pl.col("arr_local") - pl.col("dep_local")) / pl.duration(hours=1)
    # A deadhead leg (D3 `deadhead` = 1: the pilot travels as a passenger) is duty
    # but not flying: no flight hours, and its zero block time is not an estimate.
    deadhead = (
        pl.col("deadhead").fill_null(0) == 1 if "deadhead" in legs.columns else pl.lit(False)
    )
    hours = (
        pl.when(deadhead).then(0.0)
        .when(supplied > 0).then(supplied)
        .when(derived > 0).then(derived)
        .otherwise(0.0)
    )
    agg = (
        legs.group_by(["pairing_id", "duty_period"])
        .agg(
            [
                pl.col("report_local").min().alias("duty_start"),
                pl.col("release_local").max().alias("duty_end"),
                hours.sum().alias("flight_hours"),
                ((supplied.fill_null(0) <= 0) & ~deadhead).any().alias("estimated"),
            ]
        )
        .sort(["pairing_id", "duty_period"])
    )
    out: DutyPeriods = {}
    incomplete: set[str] = set()
    estimated: set[str] = set()
    for row in agg.iter_rows(named=True):
        pid = row["pairing_id"]
        if row["duty_start"] is None or row["duty_end"] is None:
            incomplete.add(pid)
            continue
        if row["estimated"]:
            estimated.add(pid)
        out.setdefault(pid, []).append(
            (row["duty_start"], row["duty_end"], float(row["flight_hours"]))
        )
    # A pairing is usable only if EVERY duty period is: half a pairing would
    # leave the pilot looking free for the days it has no times for.
    for pid in incomplete:
        out.pop(pid, None)
    return out, incomplete, estimated


def _reconcile_overlaps(
    calendar: list[Block], trimmable: frozenset[BlockType]
) -> tuple[list[Block], dict[str, int]]:
    """IMP-520: a crew calendar with no two blocks overlapping, and what it took.

    A block of a trimmable type (a day off that runs into a pairing) gives way
    to any block it overlaps (a firm block over a trimmable one wins either way round): it is cut back to the other block's edge,
    split if the other block sits inside it, or dropped if nothing is left.
    Two blocks that are both firm (PAIRING over PAIRING, a pairing over a
    reserve) cannot both be right: the later one is dropped and counted, never
    resolved silently -- the count is the data defect's size.
    """
    stats = {"trimmed": 0, "dropped": 0}
    # Fast path: a calendar with nothing overlapping is returned as it came.
    ordered = sorted(calendar, key=lambda b: b.start)
    if all(ordered[i].start >= ordered[i - 1].end for i in range(1, len(ordered))):
        return calendar, stats
    kept: list[Block] = []
    for block in sorted(calendar, key=lambda b: (b.start, b.end)):
        pending = [block]
        while pending:
            b = pending.pop(0)
            clash = next((k for k in kept if k.start < b.end and b.start < k.end), None)
            if clash is None:
                kept.append(b)
                continue
            if b.btype in trimmable:
                # b gives way: keep the parts of b outside `clash`.
                stats["trimmed"] += 1
                before = dataclasses.replace(b, end=clash.start) if b.start < clash.start else None
                after = dataclasses.replace(b, start=clash.end) if b.end > clash.end else None
                pending[0:0] = [p for p in (before, after) if p is not None]
            elif clash.btype in trimmable:
                # the block already kept gives way to b.
                stats["trimmed"] += 1
                kept.remove(clash)
                before = dataclasses.replace(clash, end=b.start) if clash.start < b.start else None
                after = dataclasses.replace(clash, start=b.end) if clash.end > b.end else None
                pending[0:0] = [b, *[p for p in (before, after) if p is not None]]
            else:
                stats["dropped"] += 1
        kept.sort(key=lambda k: (k.start, k.end))
    return kept, stats


def load_rosters(
    cfg: config.BaseConfig,
    base: str | None = None,
    fleet: str | None = None,
    position: str | None = None,
    policy: Policy | None = None,
    window: tuple[datetime.date, datetime.date] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[list[CrewMember], dict[str, int]]:
    """
    `diagnostics`, if given, is filled with what the data cost to load (IMP-520/521):
    D2 block types mapped by `data.block_type_map`, pairings read from D2's span
    because D3 lacks their duty times, pairings whose flight hours were derived
    from clock times, and overlapping blocks trimmed or dropped.

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
        # Some rows might have fleet empty? IMP-522: a fleet group is one scope.
        d1 = d1.filter(
            pl.col("fleet").str.contains(fleet)
            | pl.col("fleet").is_in(sorted(config.fleet_members(cfg, fleet)))
        )

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
        # fleet_family or fleet? Let's use fleet for fleet_quals. IMP-522: plus
        # every fleet that shares its type rating (data.fleet_groups). Named
        # `crew_fleet`, not `fleet`: that is this function's own filter argument.
        crew_fleet = row["fleet"]

        c = CrewMember(
            crew_id=crew_id,
            base=row["base"],
            fleet_quals=config.fleet_members(cfg, crew_fleet),
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

    duty_periods_by_pairing, incomplete_pairings, estimated_pairings = _load_pairing_duty_periods(cfg)
    mapped_types: Counter[str] = Counter()
    refused_types: Counter[str] = Counter()
    null_time_pairings: set[str] = set()
    estimated_used: set[str] = set()

    for row in d2.sort("start_utc").iter_rows(named=True):
        c_id = row["crew_id"]
        if c_id not in crew_dict:
            continue

        c = crew_dict[c_id]

        start_dt = parse_dt(row["start_utc"])
        end_dt = parse_dt(row["end_utc"])

        # Only blocks overlapping the template window belong in this run's calendar.
        if end_dt <= anchor or start_dt >= window_end_dt:
            continue

        # IMP-521: a block type the engine has no name for is either mapped on
        # purpose (data.block_type_map) or refused -- never skipped. Skipping
        # made a sick or office-bound pilot look free to be drafted.
        raw_type = row["block_type"]
        try:
            btype = BlockType(raw_type)
        except ValueError:
            stand_in = cfg.data.block_type_map.get(raw_type)
            if stand_in is None:
                refused_types[raw_type] += 1
                continue
            btype = BlockType(stand_in)
            mapped_types[raw_type] += 1

        pairing_id = row["pairing_id"] if row["pairing_id"] else None
        r_type = row["reserve_call_type"] if row["reserve_call_type"] else None

        if pairing_id in incomplete_pairings and btype == BlockType.PAIRING:
            # IMP-520: D3 has no duty times for this pairing, so D2's own span
            # stands in. Coarser, but the pilot is correctly busy.
            null_time_pairings.add(pairing_id)

        if (
            btype == BlockType.PAIRING
            and pairing_id in duty_periods_by_pairing
            and row["start_local"] is not None
        ):
            # Replace the flat multi-day span with D3's real duty periods.
            # D3 only has "_local" times; D2 has both "_utc" and "_local" for
            # this same row, so derive this row's own UTC offset from its own
            # pair rather than hardcoding a base's timezone (bases differ,
            # hardcoding invites a DST bug).
            if pairing_id in estimated_pairings:
                estimated_used.add(pairing_id)
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

    if refused_types:
        raise ValueError(
            f"D2 carries block type(s) the engine has no name for: {dict(refused_types)} in "
            f"{window_start}..{window_end}. Map each to an engine block type in "
            f"configs/base.yaml -> data.block_type_map (SICK: ABSENCE makes the pilot "
            f"unavailable), or ask the data owner what it means. They are refused, not "
            f"skipped: a skipped block leaves the pilot looking free."
        )

    # Validate calendars (L0 - non overlapping, sorted). IMP-520: real rosters
    # overlap (a day off that runs into a pairing, two pairings stamped over
    # the same days). data.overlap_policy decides: refuse, or reconcile and count.
    trimmable = frozenset(BlockType(t) for t in cfg.data.trimmable_block_types)
    overlap_stats = {"trimmed": 0, "dropped": 0, "crews": 0}
    for c in crew_dict.values():
        c.calendar.sort(key=lambda b: b.start)
        if cfg.data.overlap_policy == "reconcile":
            c.calendar, per_crew = _reconcile_overlaps(c.calendar, trimmable)
            overlap_stats["trimmed"] += per_crew["trimmed"]
            overlap_stats["dropped"] += per_crew["dropped"]
            overlap_stats["crews"] += 1 if (per_crew["trimmed"] or per_crew["dropped"]) else 0
        for i in range(1, len(c.calendar)):
            prev = c.calendar[i - 1]
            curr = c.calendar[i]
            if curr.start < prev.end:
                raise ValueError(
                    f"L0 Violation: crew {c.crew_id} calendar has overlapping "
                    f"blocks {prev} and {curr}. See S1d-04b2 (blocked): D3-derived "
                    f"PAIRING duty-period ends routinely spill past D2's own "
                    f"pairing-end boundary into the next D2-scheduled block -- "
                    f"this is not yet reconciled. Set data.overlap_policy: reconcile "
                    f"to trim and count them instead."
                )
        active_crew.append(c)

    if diagnostics is not None:
        diagnostics.update({
            "block_types_mapped": dict(mapped_types),
            "pairings_without_duty_times": len(null_time_pairings),
            "pairings_block_hours_estimated": len(estimated_used),
            "overlaps_trimmed": overlap_stats["trimmed"],
            "overlaps_dropped": overlap_stats["dropped"],
            "crews_with_overlaps": overlap_stats["crews"],
        })

    if policy:
        # We need to apply reserves per target
        # Map target -> max reserves, and the SC/LC split of that peak entry.
        target_reserves: dict[tuple[str, str, str], int] = {}
        # AUD-08: the Stage-1 vector is (R_SC, R_LC), not a headcount (§7.2)
        # -- remember the peak entry's split so the minted lines can be
        # relabelled to the policy's own mix rather than inheriting whatever
        # call types the donor patterns happened to carry.
        target_split: dict[tuple[str, str, str], tuple[int, int]] = {}
        for r in policy.stage1.reserves:
            # fleet_quals is a set, we'll just match the fleet string
            key = (r.base, r.fleet, r.position)
            daily = r.short_call + r.long_call
            if daily > target_reserves.get(key, 0):
                target_reserves[key] = daily
                target_split[key] = (r.short_call, r.long_call)
                
        # Group crew by target
        # Note: A crew member can have multiple fleet_quals, but usually a primary one in D1. 
        # In D1, we mapped `fleet` to `fleet_quals={fleet}`. We can just use that single fleet for grouping.
        from collections import defaultdict
        groups = defaultdict(list)
        # IMP-522: a crew member belongs to the policy's own name for their fleet
        # when they qualify for one (a group member qualifies for the group's
        # scope fleet), else to their primary fleet -- never to whichever
        # element a set happens to iterate first.
        target_fleets = {k[1] for k in target_reserves}
        for c in active_crew:
            matching = sorted(c.fleet_quals & target_fleets)
            f = matching[0] if matching else c.primary_fleet
            groups[(c.base, f, c.position)].append(c)
            
        _check_reserve_shortfall(policy.policy_id, target_reserves, groups, base, fleet, position)

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
                    
            # S1b-02 AC3 / IMP-118: who ends up on reserve, from
            # configs/base.yaml -> population.reserve_bid_rule (senior_first
            # today; see the decision note there). Lower seniority number =
            # more senior, so senior_first sorts ascending, junior_first
            # descending.
            junior_first = cfg.population.reserve_bid_rule == "junior_first"
            crew_list.sort(key=lambda c: c.seniority, reverse=junior_first)
            
            res = crew_list[:n_res]
            lin = crew_list[n_res:]
            
            # Assign patterns to minted reserves
            import itertools
            if authentic_reserve_calendars:
                pattern_cycle = itertools.cycle(authentic_reserve_calendars)
            else:
                pattern_cycle = itertools.cycle([[]]) # fallback if none exist
                
            sc_n, _lc_n = target_split.get(key, (n_res, 0))
            for i, c in enumerate(res):
                c._is_reserve = True
                # S1b-02 AC2: remember the line they gave up before overwriting
                # it. Without this the flying silently ceased to exist, so a
                # higher R carried no opportunity cost at all.
                c._displaced_pairings = [b for b in c.calendar if b.btype == BlockType.PAIRING]
                # AUD-08: the first `short_call` minted lines are SC, the rest
                # LC -- the policy's own Stage-1 split, which rule L8 and the
                # per-day staffing rates both read off the blocks. The donor
                # pattern still supplies the ROTATION (which days are on call);
                # only the call type is the policy's to set. dataclasses.replace
                # creates fresh Block objects, which also serves the old
                # list(...)-copy purpose: pattern_cycle repeats once the reserve
                # count exceeds the number of distinct authentic patterns, and
                # shared Block lists must not be mutated across crew.
                call_type = "SC" if i < sc_n else "LC"
                c.calendar = [
                    dataclasses.replace(b, reserve_call_type=call_type)
                    if b.btype == BlockType.RESERVE else b
                    for b in next(pattern_cycle)
                ]
            reserve_crew_all.extend(res)
            
            for c in lin:
                c._is_reserve = False
                c.calendar = [b for b in c.calendar if b.btype != BlockType.RESERVE]
            line_crew_all.extend(lin)
            
        active_crew = reserve_crew_all + line_crew_all
        active_crew.sort(key=lambda c: c.crew_id)

    return active_crew, exclusion_counts


class ReserveShortfallError(ValueError):
    """A policy asks for more reserves than a (base, fleet, position) group has active crew."""


def _check_reserve_shortfall(
    policy_id: str,
    target_reserves: dict[tuple[str, str, str], int],
    groups: dict[tuple[str, str, str], list[CrewMember]],
    base: str | None,
    fleet: str | None,
    position: str | None,
) -> None:
    """IMP-119: refuse to carve fewer reserves than the policy asks for.

    `crew_list[:n_res]` silently returns everyone when a group is smaller than
    the target, and since the SC/LC split takes the first `short_call`
    reserves as SC, the whole shortfall used to come out of long-call -- so a
    policy labelled R14 could run with fewer reserves and nothing said so.
    Only groups inside this call's own filter are checked: a policy entry for
    another base is not this load's to satisfy.
    """
    shortfalls = []
    for key, wanted in sorted(target_reserves.items()):
        k_base, k_fleet, k_position = key
        if (base and k_base != base) or (fleet and k_fleet != fleet) or (position and k_position != position):
            continue
        available = len(groups.get(key, []))
        if wanted > available:
            shortfalls.append(f"{'/'.join(key)}: {wanted} requested, {available} active crew available")
    if shortfalls:
        raise ReserveShortfallError(
            f"policy {policy_id!r} asks for more reserves than the roster can supply -- "
            + "; ".join(shortfalls)
            + ". Lower the policy's short_call/long_call, or widen the roster."
        )


def load_cross_base_reserves(
    cfg: config.BaseConfig,
    home_base: str,
    fleet: str | None = None,
    position: str | None = None,
    window: tuple[datetime.date, datetime.date] | None = None,
) -> list[CrewMember]:
    """S1c-07: the reserve pool at every base EXCEPT `home_base`, taken from D2
    exactly as it was.

    Deliberately not policy-driven, and that is the whole design decision here.
    A policy's `stage1.reserves` is the Stage-1 commitment for the scope being
    optimised -- it sizes YUL. What Toronto and Vancouver staffed is not this
    planner's decision variable; it is an exogenous fact about the network on
    the modelled dates. So these crew are not minted from a reserve target the
    way `load_rosters` mints the in-scope pool: they are the real crew who
    really held RESERVE blocks at those bases in this window, with their real
    calendars, PAIRING blocks and all.

    Keeping their pairings is the point. An out-of-base reserve is available
    only when D2 says they were on call and not already flying -- exactly the
    availability that decides whether §5.3's `XB` question ("is a reserve
    available there?") answers yes. Stripping the pairings, as the in-scope
    carve-out does when it mints a pure reserve line, would invent availability
    that never existed and make cross-base coverage look far more reliable than
    it is.

    Crew with no RESERVE block anywhere in the window are dropped: a line
    holder at another base is not draftable from here (drafting is base-local,
    §5.6) and has no reserve availability to offer.
    """
    all_crew, _ = load_rosters(cfg, base=None, fleet=fleet, position=position, window=window)
    out: list[CrewMember] = []
    for c in all_crew:
        if c.base == home_base:
            continue
        if not any(b.btype == BlockType.RESERVE for b in c.calendar):
            continue
        c._is_reserve = True
        c._is_cross_base = True
        out.append(c)
    out.sort(key=lambda c: c.crew_id)
    return out

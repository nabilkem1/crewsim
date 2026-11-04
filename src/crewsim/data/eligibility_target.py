import datetime

import numpy as np
import polars as pl
from scipy import stats

from .. import config
from ..engine.eligibility import is_on_call_at
from ..engine.legality import is_legal_assignment
from ..engine.roster_loader import load_rosters
from ..engine.state import BlockType, OpenTimeItem
from . import loaders


def reconstruct_eligibility(cfg, window: str) -> dict:
    """S0-04: the REAL historical eligible-fraction distribution for
    `window` ("fitting" or "holdout", per S0-09), used as V3's ground
    truth (crewsim.gates.v3_eligibility).

    For every real D4 absence in cfg.scope (base/fleet/position) and
    cfg.scope.season whose crew's real D2 calendar has a matching PAIRING
    block, this applies the exact same pool + legality definition
    EligibilityEngine.eligible_reserves uses live: pool = other crew whose
    real RESERVE block covers the whole duty window, eligible = pool
    members who pass real is_legal_assignment (L0-L8) with `now` = the
    absence's real notification_ts. One fraction per historical duty
    period an absence actually created open time for -- a distribution,
    not a point (S0-04's own acceptance criterion), built from real
    history, not a synthetic draw.

    KNOWN VALIDATION LIMIT (AUD-09): because this reconstruction applies the
    SAME L0-L8 implementation the simulation uses, a defect in the legality
    rules moves the historical band and the simulated rate together -- gate
    V3 therefore validates roster/calendar realism, not legality
    correctness, and a V3 PASS is necessary but not sufficient. An
    independent check against D5's real call-outcome log (assigned /
    released / no-show), which never passes through this code, is the
    recommended V3b companion -- recorded as future work, not silently
    assumed away.
    """
    if cfg.windows is None:
        raise ValueError("reconstruct_eligibility requires cfg.windows (fitting/holdout) to be configured")
    win = cfg.windows.get(window)
    season_months = set(loaders.load_seasons(cfg)[cfg.scope.season])

    base, fleet, position = cfg.scope.base, cfg.scope.fleet, cfg.scope.position

    # Real crew calendars across the WHOLE window -- includes real D2
    # RESERVE blocks (historical ground truth of who was actually on
    # reserve when), not a synthetic policy carve-out (policy=None).
    crew_list, _ = load_rosters(cfg, base=base, fleet=fleet, position=position, window=(win.start, win.end))
    crew_by_id = {c.crew_id: c for c in crew_list}

    anchor = datetime.datetime.combine(win.start, datetime.time.min)

    def to_minutes(dt: datetime.datetime) -> float:
        return (dt - anchor).total_seconds() / 60.0

    d4 = loaders.load_dataset(cfg, "d4_absences")
    d4 = d4.filter(
        (pl.col("base") == base)
        & pl.col("fleet").is_in(sorted(config.fleet_members(cfg, fleet)))
        & (pl.col("position") == position)
        & pl.col("affected_pairing_id").is_not_null()
        & (pl.col("absence_start") >= win.start)
        & (pl.col("absence_start") <= win.end)
    )

    fractions = []
    for row in d4.iter_rows(named=True):
        if row["absence_start"].month not in season_months:
            continue  # scope this to the same season the live simulation is scoped to

        crew = crew_by_id.get(row["crew_id"])
        if crew is None:
            continue  # not an active in-scope crew member in this window

        # No notification time in a real extract: `data.null_notification_ts` says
        # whether the event is left out or taken as reported at 00:00 on the
        # absence's first day (the same rule the V6 replay applies).
        notified = row["notification_ts"]
        if notified is None:
            if cfg.data.null_notification_ts == "exclude":
                continue
            notified = datetime.datetime.combine(row["absence_start"], datetime.time.min)
        notification_minutes = to_minutes(notified)
        pairing_id = row["affected_pairing_id"]

        for b in crew.calendar:
            if b.btype != BlockType.PAIRING or b.pairing_id != pairing_id:
                continue

            item = OpenTimeItem(
                uid=0, pairing_id=pairing_id, base=crew.base,
                fleet=crew.primary_fleet, position=crew.position,
                start=b.start, end=b.end, deadline=b.start, origin="SICK_CALL",
                root_event_uid=0, flight_mins=b.flight_mins,
            )

            # Same pool definition as EligibilityEngine.eligible_reserves --
            # via the SAME function, so the historical side and the simulated
            # side cannot drift apart on what "on call" means (OPEN-4 changed
            # it from whole-duty coverage to on call at the report time).
            pool = [
                r for r in crew_list
                if r.crew_id != crew.crew_id and is_on_call_at(r, item.start)
            ]
            if not pool:
                continue

            eligible = sum(
                1 for r in pool
                if is_legal_assignment(r, item, now=notification_minutes, cfg=cfg).legal
            )
            fractions.append(eligible / len(pool))

    fractions = np.array(fractions)
    if len(fractions) < 2:
        raise ValueError(
            f"reconstruct_eligibility found only {len(fractions)} historical eligibility "
            f"event(s) for {base}/{fleet}/{position} in {window!r} -- too few to form a "
            f"distribution (S0-04's own acceptance criterion)."
        )

    mean_frac = float(np.mean(fractions))
    se = np.std(fractions, ddof=1) / np.sqrt(len(fractions))
    ci_half = stats.t.ppf(0.975, len(fractions) - 1) * se

    return {
        "mean": mean_frac,
        "ci_lower": mean_frac - ci_half,
        "ci_upper": mean_frac + ci_half,
        "distribution": fractions,
    }

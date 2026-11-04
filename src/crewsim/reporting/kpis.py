from typing import Any

import numpy as np

from ..engine import des

# Two distinct "never covered" outcomes: CANCELLATION (an item hit its own
# deadline mid-simulation) and TERMINAL_PENALTY (an item still open at
# horizon end) -- both are uncovered legs. Shared with grid.py's
# scenario_uncovered_legs so the two never define "uncovered" differently.
UNCOVERED_CATEGORIES = ("CANCELLATION", "TERMINAL_PENALTY")


def count_uncovered(rows: list[Any]) -> int:
    return sum(1 for r in rows if r.category in UNCOVERED_CATEGORIES)


def _gini(values: list[float]) -> float:
    """Gini concentration coefficient: 0 = perfectly even, 1 = everything on
    one individual. Closed-form statistical formula, not a business input."""
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    cumulative = sum((i + 1) * v for i, v in enumerate(ordered))
    return (2 * cumulative) / (n * sum(ordered)) - (n + 1) / n


_MINUTES_PER_DAY = 1440.0

# Ledger categories that mark an item's RESOLUTION (share its event_uid with
# the OPEN_ITEM marker). APPR rides with CANCELLATION on the same uid.
_RESOLUTION_PREFIXES = ("DRAFT_TIER",)
_RESOLUTION_CATEGORIES = ("RESERVE_UTILIZATION", "CANCELLATION", "TERMINAL_PENALTY")


def _daily_open_item_counts(cfg: Any, sim: Any) -> list[int]:
    """|O(t)| sampled at each day boundary, from the ledger alone: an item is
    open from its OPEN_ITEM marker (AUD-03) until the first resolution row
    sharing its event_uid. This is the §5.0.5 Welch signal -- the daily
    open-time count -- derived with no extra engine state."""
    created: dict[int, float] = {}
    resolved: dict[int, float] = {}
    for row in sim.ledger.rows:
        if row.category == "OPEN_ITEM":
            prev = created.get(row.event_uid)
            if prev is None or row.sim_time < prev:
                created[row.event_uid] = row.sim_time
        elif row.category in _RESOLUTION_CATEGORIES or row.category.startswith(_RESOLUTION_PREFIXES):
            prev = resolved.get(row.event_uid)
            if prev is None or row.sim_time < prev:
                resolved[row.event_uid] = row.sim_time

    days = cfg.horizon.horizon_days
    counts = []
    for d in range(days):
        boundary = (d + 1) * _MINUTES_PER_DAY
        n = sum(
            1
            for uid, t0 in created.items()
            if t0 <= boundary and resolved.get(uid, float("inf")) > boundary
        )
        counts.append(n)
    return counts


def welch_warmup_diagnostic(cfg: Any, sims: list[Any]) -> dict[str, Any] | None:
    """AUD-12 / §5.0.5: "length is checked with Welch's procedure on the daily
    open-time count ... Do not simply assert 7 days."

    An automated, conservative reading of Welch: average |O(day)| across
    scenarios, take the measurement window's own mean as the settled level,
    and report the first day from which every later pre-cool-down day stays
    within gates.welch_tolerance of that level. `ok` is whether that day
    falls inside the configured warm-up. Returns None when the tolerance is
    not configured (cfg.gates absent) -- the diagnostic never invents its own
    bar.
    """
    if cfg.gates is None or not sims:
        return None
    tol = cfg.gates.welch_tolerance
    days = cfg.horizon.horizon_days
    per_day = [0.0] * days
    for sim in sims:
        for d, n in enumerate(_daily_open_item_counts(cfg, sim)):
            per_day[d] += n
    per_day = [v / len(sims) for v in per_day]

    w_end = cfg.horizon.warmup_days
    m_end = cfg.horizon.warmup_days + cfg.horizon.measurement_days
    tail = per_day[w_end:m_end]
    tail_mean = sum(tail) / len(tail) if tail else 0.0
    band = tol * max(tail_mean, 1.0)

    stabilized_day: int | None = None
    for d in range(m_end):
        if all(abs(per_day[d2] - tail_mean) <= band for d2 in range(d, m_end)):
            stabilized_day = d
            break

    # `per_day[d]` samples the queue at the END of day d (minute (d+1)*1440),
    # so the sample taken at the instant measurement OPENS -- minute
    # w_end*1440 -- is index w_end-1. A warm-up is adequate only if the queue
    # had already settled by then, i.e. stabilized_day <= w_end-1. Accepting
    # `<= w_end` would pass a run whose queue was still climbing at the
    # measurement boundary and only settled a day later, which is exactly the
    # false assurance this diagnostic exists to prevent.
    last_warmup_sample = w_end - 1
    return {
        "daily_mean_open_items": [round(v, 3) for v in per_day],
        "tail_mean": round(tail_mean, 3),
        "tolerance": tol,
        "stabilized_day": stabilized_day,
        "warmup_days": w_end,
        "ok": stabilized_day is not None and stabilized_day <= last_warmup_sample,
    }


RESERVE_CALL_TYPES = ("SC", "LC")


def reserve_usage_by_call_type(cfg: Any, sims: list[Any]) -> dict[str, dict[str, float]]:
    """IMP-117: reserve-days PAID and reserve assignments USED, per call type.

    Measurement-window rows only (same rule as every other KPI), averaged over
    all scenarios. A call type with staffing_days_mean > 0 and
    assignments_mean == 0 is being paid for and never used -- see
    `unused_paid_call_types`. The call type comes from the Simulation's side
    table (des.Simulation.reserve_call_types), not from the row's amount.
    """
    n = len(sims)
    totals = {t: {"staffing_days": 0, "assignments": 0, "staffing_dollars": 0.0} for t in RESERVE_CALL_TYPES}
    for sim in sims:
        # A sim built without the side table (a test double, or a replay that
        # predates it) contributes nothing rather than a guessed type.
        lookup = getattr(sim, "reserve_call_type_of", None)
        if lookup is None:
            continue
        for row in des.rows_in_measurement_window(cfg, sim):
            if row.category not in ("RESERVE_STAFFING", "RESERVE_UTILIZATION"):
                continue
            call_type = lookup(row)
            if call_type not in totals:
                continue
            if row.category == "RESERVE_STAFFING":
                totals[call_type]["staffing_days"] += 1
                totals[call_type]["staffing_dollars"] += row.amount
            else:
                totals[call_type]["assignments"] += 1
    return {
        t: {
            "staffing_days_mean": v["staffing_days"] / n if n else 0.0,
            "staffing_dollars_mean": v["staffing_dollars"] / n if n else 0.0,
            "assignments_mean": v["assignments"] / n if n else 0.0,
        }
        for t, v in totals.items()
    }


def unused_paid_call_types(usage: dict[str, dict[str, float]]) -> list[str]:
    """Call types that were paid for (staffing days > 0) but never assigned."""
    return [
        t for t, v in usage.items()
        if v["staffing_days_mean"] > 0 and v["assignments_mean"] == 0
    ]


DRAFT_GINI_CAVEAT = (
    "Read as the distribution of premium earnings (drafting is premium-paid, allocated "
    "senior-first), not an imposed burden -- a high Gini is the expected result of "
    "senior-first allocation, not a warning sign. When drafts are rare relative to "
    "headcount, this number is arithmetic, not insight."
)


def compute_kpis(cfg: Any, sims: list[Any]) -> dict[str, Any]:
    """S1e-01: every KPI aggregated over the measurement window only (spec
    Sec2.1, Sec5.0.5) -- warm-up rows excluded, cool-down costs/counts
    attributed back to the window when their causal chain originates there
    (des.rows_in_measurement_window, the same rule measured_window_costs
    uses).
    """
    warmup_end, measurement_end = des.measurement_window_bounds(cfg)

    scenario_costs = des.measured_window_costs(cfg, sims)

    uncovered_counts: list[int] = []
    reserve_dispatch_counts: list[int] = []
    reserve_dollars: list[float] = []
    draft_counts_by_crew: dict[str, int] = {}
    total_draft_events = 0
    eligibility_samples: list[float] = []
    # One dict per scenario, category -> summed amount, so the eventual mean
    # divides by every scenario (n_scenarios), not just the scenarios where a
    # given category happened to book a row -- a category present in 3 of 20
    # scenarios must still average over 20, or the mean is biased upward.
    per_scenario_category_costs: list[dict[str, float]] = []
    # RESERVE_STAFFING is booked once per (reserve, covered calendar day) by
    # engine/costs.py::book_reserve_staffing, off the REAL roster's RESERVE
    # blocks -- counting these rows is the real "reserve-days bought"
    # denominator for utilization_rate, not a hand-parsed reading of the
    # policy YAML's stage1.reserves blocks (which would have to re-derive the
    # same day-of-week coverage logic book_reserve_staffing already computed,
    # and risks disagreeing with it -- R6.yaml alone is 6 reserves Mon-Fri but
    # 7 on weekends, so "R" is not a single constant per policy).
    reserve_staffing_days: list[int] = []

    for sim in sims:
        rows = des.rows_in_measurement_window(cfg, sim)
        uncovered_counts.append(count_uncovered(rows))

        reserve_rows = [r for r in rows if r.category == "RESERVE_UTILIZATION"]
        reserve_dispatch_counts.append(len(reserve_rows))
        reserve_dollars.append(sum(r.amount for r in reserve_rows))
        reserve_staffing_days.append(sum(1 for r in rows if r.category == "RESERVE_STAFFING"))

        scenario_costs_by_cat: dict[str, float] = {}
        for r in rows:
            scenario_costs_by_cat[r.category] = scenario_costs_by_cat.get(r.category, 0.0) + r.amount
            if r.category.startswith("DRAFT_TIER"):
                total_draft_events += 1
                if r.crew_id:
                    draft_counts_by_crew[r.crew_id] = draft_counts_by_crew.get(r.crew_id, 0) + 1
        per_scenario_category_costs.append(scenario_costs_by_cat)

        eligibility_samples.extend(sim.elig.get_distribution(min_time=warmup_end, max_time=measurement_end))

    # Mean per category across ALL scenarios (a category absent from a given
    # scenario contributes 0 to that scenario's total, via dict.get default) --
    # never zero-padded to include a category that never appeared in ANY
    # scenario, so this dict's keys are exactly "what this run actually booked."
    all_categories = sorted({cat for d in per_scenario_category_costs for cat in d})
    cost_by_category = {
        cat: float(np.mean([d.get(cat, 0.0) for d in per_scenario_category_costs]))
        for cat in all_categories
    }

    reserve_staffing_days_mean = float(np.mean(reserve_staffing_days)) if reserve_staffing_days else 0.0
    reserve_dispatches_mean_value = float(np.mean(reserve_dispatch_counts)) if reserve_dispatch_counts else 0.0
    utilization_rate = (
        reserve_dispatches_mean_value / reserve_staffing_days_mean if reserve_staffing_days_mean > 0 else None
    )

    # Same construct as gate V4 (S1d-04e): n_cascading_drafts / n_drafts per
    # scenario. Whole-simulation counters, not window-filtered -- a cascade
    # can be seeded by a draft made just before the window boundary, and
    # these counters (unlike the ledger) don't carry a root_event_uid to
    # attribute back with; consistent with how gate v4 already reports this.
    cascade_rates = [sim.n_cascading_drafts / sim.n_drafts for sim in sims if sim.n_drafts > 0]

    draft_counts = list(draft_counts_by_crew.values())

    # WN-004: spec Sec7.5's chance constraint, P(UncoveredLegs > u_max) <= epsilon.
    # cfg.service_level is None until configs/base.yaml carries a real
    # [CONFIRM: Crew Planning] threshold -- see config.py's own note on why
    # this has no numeric default. Computed from the SAME per-scenario
    # uncovered_counts distribution cvar95 already uses; no new simulation.
    service_level = None
    if cfg.service_level is not None and uncovered_counts:
        p_exceeds = sum(1 for u in uncovered_counts if u > cfg.service_level.u_max) / len(uncovered_counts)
        service_level = {
            "u_max": cfg.service_level.u_max,
            "epsilon": cfg.service_level.epsilon,
            "p_uncovered_exceeds_u_max": p_exceeds,
            "service_level_met": p_exceeds <= cfg.service_level.epsilon,
        }

    reserve_by_call_type = reserve_usage_by_call_type(cfg, sims)

    return {
        "n_scenarios": len(sims),
        "warmup_welch": welch_warmup_diagnostic(cfg, sims),
        "warmup_days": cfg.horizon.warmup_days,
        "measurement_days": cfg.horizon.measurement_days,
        "cooldown_days": cfg.horizon.cooldown_days,
        "expected_cost": float(np.mean(scenario_costs)) if scenario_costs else 0.0,
        "cvar95": des.cvar95(scenario_costs),
        "cost_by_category": cost_by_category,
        "uncovered_legs_mean": float(np.mean(uncovered_counts)) if uncovered_counts else 0.0,
        "service_level": service_level,
        "reserve_dispatches_mean": reserve_dispatches_mean_value,
        "reserve_staffing_days_mean": reserve_staffing_days_mean,
        "utilization_rate": utilization_rate,
        "reserve_dollars_mean": float(np.mean(reserve_dollars)) if reserve_dollars else 0.0,
        "reserve_by_call_type": reserve_by_call_type,
        "unused_paid_call_types": unused_paid_call_types(reserve_by_call_type),
        "eligibility_mean": float(np.mean(eligibility_samples)) if eligibility_samples else None,
        "eligibility_n_samples": len(eligibility_samples),
        "cascade_rate_mean": float(np.mean(cascade_rates)) if cascade_rates else None,
        "cascade_n_scenarios_with_drafts": len(cascade_rates),
        "total_draft_events": total_draft_events,
        "draft_counts_by_crew": draft_counts_by_crew,
        "draft_max": max(draft_counts) if draft_counts else 0,
        "draft_gini": _gini(draft_counts),
        "draft_gini_caveat": DRAFT_GINI_CAVEAT,
    }


def print_kpi_report(cfg: Any, result: dict[str, Any]) -> None:
    warmup_end, measurement_end = des.measurement_window_bounds(cfg)
    print(f"KPI report -- {result['n_scenarios']} scenario(s)")
    print(
        f"  Measurement window: minute {warmup_end:.0f} to {measurement_end:.0f} "
        f"({result['warmup_days']}d warm-up excluded, {result['measurement_days']}d measured, "
        f"{result['cooldown_days']}d cool-down costs attributed back if in-window-caused)"
    )
    print(f"\n  E[cost]                       = ${result['expected_cost']:,.2f}")
    print(f"  CVaR95                        = ${result['cvar95']:,.2f}")
    print(f"  Uncovered legs (mean/scenario) = {result['uncovered_legs_mean']:.2f}")
    print(
        f"  Reserve utilisation           = {result['reserve_dispatches_mean']:.2f} dispatches/scenario "
        f"(${result['reserve_dollars_mean']:,.2f})"
    )
    for call_type, usage in result.get("reserve_by_call_type", {}).items():
        print(
            f"    {call_type}: {usage['staffing_days_mean']:.2f} reserve-days paid "
            f"(${usage['staffing_dollars_mean']:,.2f}), "
            f"{usage['assignments_mean']:.2f} assignments/scenario"
        )
    for call_type in result.get("unused_paid_call_types", []):
        print(
            f"  [WARN] {call_type} reserves are paid for but were never assigned in any "
            f"measured scenario -- see configs/base.yaml -> legality / reserve_lines (IMP-117)"
        )
    if result["eligibility_mean"] is not None:
        print(
            f"  Eligibility (mean fraction)    = {result['eligibility_mean']:.3f} "
            f"({result['eligibility_n_samples']} events)"
        )
    else:
        print("  Eligibility (mean fraction)    = n/a (no eligibility events in window)")
    if result["cascade_rate_mean"] is not None:
        print(
            f"  Cascade rate (mean)            = {result['cascade_rate_mean']:.3f} "
            f"({result['cascade_n_scenarios_with_drafts']} scenario(s) with drafts)"
        )
    else:
        print("  Cascade rate (mean)            = n/a (no drafts in any scenario)")
    welch = result.get("warmup_welch")
    if welch is not None:
        day = welch["stabilized_day"]
        verdict = "OK" if welch["ok"] else "NOT VALIDATED"
        print(
            f"  Warm-up (Welch, ±{welch['tolerance']:.0%} of settled level "
            f"{welch['tail_mean']:.2f} open items/day): stabilises by day "
            f"{day if day is not None else '>measurement'} vs {welch['warmup_days']}d warm-up "
            f"[{verdict}]"
        )
    print(f"\n  Draft distribution: {result['total_draft_events']} events across "
          f"{len(result['draft_counts_by_crew'])} crew, max {result['draft_max']}, "
          f"Gini {result['draft_gini']:.3f}")
    print(f"  Note: {result['draft_gini_caveat']}")

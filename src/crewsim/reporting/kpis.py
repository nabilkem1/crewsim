from typing import Any

import numpy as np

from ..engine import des


def _gini(values: list[float]) -> float:
    """Gini concentration coefficient: 0 = perfectly even, 1 = everything on
    one individual. Closed-form statistical formula, not a business input."""
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    cumulative = sum((i + 1) * v for i, v in enumerate(ordered))
    return (2 * cumulative) / (n * sum(ordered)) - (n + 1) / n


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

    for sim in sims:
        rows = des.rows_in_measurement_window(cfg, sim)
        # Two distinct "never covered" outcomes: CANCELLATION (an item hit
        # its own deadline mid-simulation) and TERMINAL_PENALTY (an item
        # still open at horizon end) -- both are uncovered legs.
        uncovered_counts.append(sum(1 for r in rows if r.category in ("CANCELLATION", "TERMINAL_PENALTY")))

        reserve_rows = [r for r in rows if r.category == "RESERVE_UTILIZATION"]
        reserve_dispatch_counts.append(len(reserve_rows))
        reserve_dollars.append(sum(r.amount for r in reserve_rows))

        for r in rows:
            if r.category.startswith("DRAFT_TIER"):
                total_draft_events += 1
                if r.crew_id:
                    draft_counts_by_crew[r.crew_id] = draft_counts_by_crew.get(r.crew_id, 0) + 1

        eligibility_samples.extend(sim.elig.get_distribution(min_time=warmup_end, max_time=measurement_end))

    # Same construct as gate V4 (S1d-04e): n_cascading_drafts / n_drafts per
    # scenario. Whole-simulation counters, not window-filtered -- a cascade
    # can be seeded by a draft made just before the window boundary, and
    # these counters (unlike the ledger) don't carry a root_event_uid to
    # attribute back with; consistent with how gate v4 already reports this.
    cascade_rates = [sim.n_cascading_drafts / sim.n_drafts for sim in sims if sim.n_drafts > 0]

    draft_counts = list(draft_counts_by_crew.values())

    return {
        "n_scenarios": len(sims),
        "warmup_days": cfg.horizon.warmup_days,
        "measurement_days": cfg.horizon.measurement_days,
        "cooldown_days": cfg.horizon.cooldown_days,
        "expected_cost": float(np.mean(scenario_costs)) if scenario_costs else 0.0,
        "cvar95": des.cvar95(scenario_costs),
        "uncovered_legs_mean": float(np.mean(uncovered_counts)) if uncovered_counts else 0.0,
        "reserve_dispatches_mean": float(np.mean(reserve_dispatch_counts)) if reserve_dispatch_counts else 0.0,
        "reserve_dollars_mean": float(np.mean(reserve_dollars)) if reserve_dollars else 0.0,
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
    print(f"\n  Draft distribution: {result['total_draft_events']} events across "
          f"{len(result['draft_counts_by_crew'])} crew, max {result['draft_max']}, "
          f"Gini {result['draft_gini']:.3f}")
    print(f"  Note: {result['draft_gini_caveat']}")

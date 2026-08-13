"""Cascade analytics computed from real ledger chains -- §5.7's thesis, measured.

The argument this module exists to quantify is §5.5's worked ledger: one sick
call consumed a reserve, forced a draft, and -- two days later, via a cascade --
still ended in a cancellation, for $25,950 rather than the $800 a naive
draft-cost model records. That is an *amplification* claim, and it is testable
against the ledger because `root_event_uid` ties every downstream row back to
the disruption that started it (`cascade.py:71` propagates the root onto each
cascaded OpenTimeItem, so a whole chain shares one root).

So the headline here is the amplification ratio: what a chain that cascaded
costs, against what a chain that resolved on first contact costs.

Three things this module deliberately does NOT do, each because the data cannot
honestly support it:

* **No cascade "depth".** The ledger records each row's *root*, never its
  immediate parent (`LedgerRow.root_event_uid`), so a 4-level chain and a
  4-way-branching one are indistinguishable in it -- `tape.py::_depth_of`
  reads this same map and can therefore only ever return 0 or 1. Chain SIZE
  (distinct open items sharing a root) is what the ledger actually supports,
  so that is what is reported. Epic D's WD-002 asks for depth; it needs the
  engine to record parentage first.
* **No gate V4 verdict.** V4 is INCONCLUSIVE at present (S1d-04: holdout draft
  reconstruction recall is 0.000, so the historical band has zero width). A
  "validated cascade rate" figure would be exactly the fabrication this
  repo's own history keeps catching.
* **No invented reserve-loss cost.** `n_reserve_loss_cascades` is surfaced as
  a counter with its structural reason, not priced -- §4.4.2 defines no such
  coefficient, and S1d-02 established the path is unreachable from the
  production draft pool anyway.

Two populations are reported side by side, and they are NOT the same:

* **Cascade rate** comes from whole-simulation counters
  (`n_cascading_drafts / n_drafts`), matching `kpis.py`'s `cascade_rate_mean`
  and gate V4 -- those counters carry no `root_event_uid`, so they cannot be
  attributed to the measurement window.
* **Chain economics** come from `des.rows_in_measurement_window`, the repo's
  single attribution rule, so the dollars here reconcile with E[C].

Each is labelled with its own population where it is displayed; they are not
averaged together.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from ..engine import des

# A chain that ends in one of these never got covered. Everything else means
# the open item was resolved (by a reserve or by a draft) before its deadline.
UNCOVERED_CATEGORIES = ("CANCELLATION", "TERMINAL_PENALTY")

# `root_event_uid == 0` is des.py's sentinel for "no causal chain at all"
# (RESERVE_STAFFING booked daily, DELAY_AMBIENT drawn independently). Grouping
# those by root would collapse hundreds of unrelated background bookings into
# one fake shared chain -- the same trap `des.rows_in_measurement_window`
# documents and sidesteps.
NO_CHAIN_SENTINEL = 0

RESERVE_LOSS_NOTE = (
    "A draft can also destroy a future RESERVE block (§5.7's second cascade "
    "mechanism). It is counted, never priced: losing reserve capacity carries "
    "no direct dollar cost -- its cost is emergent, arriving later as a draft "
    "or cancellation a thinner pool could not prevent -- and §4.4.2 defines no "
    "coefficient for it. Expect a structural zero: drafting selects only from "
    "line holders, and roster_loader strips RESERVE blocks from line holders, "
    "so a draftee cannot hold one (S1d-02)."
)

DEPTH_NOTE = (
    "Chain SIZE, not depth. The ledger records each row's root, never its "
    "immediate parent, so a chain that cascaded four levels deep and one that "
    "broke four pairings at once are indistinguishable in it. Size is the "
    "honest measure the data supports."
)


def _chain_cost(rows: list[Any]) -> float:
    """A chain's attributable cost, on the same basis as E[C].

    DELAY_AMBIENT is excluded for the reason `des.EXCLUDED_FROM_OPTIMISED_COST`
    gives (real, but policy-invariant, so it dilutes rather than informs). In
    practice such rows carry the no-chain sentinel and are filtered out before
    they reach here; excluding them explicitly keeps this reconciling with
    `measured_window_costs` even if that ever changes.
    """
    return float(
        sum(r.amount for r in rows if r.category not in des.EXCLUDED_FROM_OPTIMISED_COST)
    )


def _group_chains(rows: list[Any]) -> dict[int, list[Any]]:
    """Ledger rows grouped into causal chains by root, sentinel rows dropped."""
    chains: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        if row.root_event_uid != NO_CHAIN_SENTINEL:
            chains[row.root_event_uid].append(row)
    return dict(chains)


def _chain_summary(scenario_id: int, root_uid: int, rows: list[Any]) -> dict[str, Any]:
    """One chain, flattened for transport to the API.

    `n_items` is the count of DISTINCT open items sharing this root: 1 means
    the disruption was absorbed where it landed, >1 means a draft broke
    something else and the chain grew.
    """
    ordered = sorted(rows, key=lambda r: r.sim_time)
    categories = [r.category for r in ordered]
    return {
        "scenario_id": scenario_id,
        "root_event_uid": root_uid,
        "n_items": len({r.event_uid for r in rows}),
        "cost": _chain_cost(rows),
        "start_minute": float(ordered[0].sim_time),
        "end_minute": float(ordered[-1].sim_time),
        "uncovered": any(c in UNCOVERED_CATEGORIES for c in categories),
        "categories": categories,
        "rows": [
            {
                "sim_time": float(r.sim_time),
                "event_uid": r.event_uid,
                "category": r.category,
                "crew_id": r.crew_id,
                "amount": float(r.amount),
            }
            for r in ordered
        ],
    }


def compute_cascade_analytics(
    cfg: Any, sims: list[Any], n_exemplars: int = 8
) -> dict[str, Any]:
    """Cascade analytics for one policy's CRN scenario set.

    Pure and picklable (plain dicts/floats/ints only), so it can be computed
    inside `grid._run_one_policy` while the Simulation objects are still in
    memory and survive joblib's process boundary -- deriving it later would
    mean re-running every scenario.
    """
    # ---- cascade rate: whole-simulation counters (kpis.py / gate V4 basis) ----
    per_scenario_rate = [
        {
            "scenario_id": sim.scenario_id,
            "n_drafts": sim.n_drafts,
            "n_cascading_drafts": sim.n_cascading_drafts,
            "rate": (sim.n_cascading_drafts / sim.n_drafts) if sim.n_drafts else None,
        }
        for sim in sims
    ]
    rates = [r["rate"] for r in per_scenario_rate if r["rate"] is not None]
    drafts_total = sum(sim.n_drafts for sim in sims)
    cascading_total = sum(sim.n_cascading_drafts for sim in sims)

    # Cascades are bursty -- measured, they concentrate in a minority of
    # scenarios rather than arriving at a steady rate. A mean alone hides
    # exactly the tail this simulation exists to price, so the concentration
    # is reported next to it rather than left to be inferred.
    n_with_cascade = sum(1 for sim in sims if sim.n_cascading_drafts > 0)

    # ---- chain economics: measurement-window attribution (E[C]'s own rule) ----
    all_chains: list[dict[str, Any]] = []
    for sim in sims:
        window_rows = des.rows_in_measurement_window(cfg, sim)
        for root_uid, rows in _group_chains(window_rows).items():
            all_chains.append(_chain_summary(sim.scenario_id, root_uid, rows))

    cascading = [c for c in all_chains if c["n_items"] > 1]
    simple = [c for c in all_chains if c["n_items"] == 1]

    mean_simple = statistics.mean([c["cost"] for c in simple]) if simple else None
    mean_cascading = statistics.mean([c["cost"] for c in cascading]) if cascading else None
    # The §5.5 claim, as a number: what a chain costs once it cascades, over
    # what it costs when it does not. None (not 1.0, not 0) when either side
    # has no observations -- an amplification of "1x" would read as "cascades
    # are free", which is a different statement from "none were observed".
    amplification = (
        mean_cascading / mean_simple
        if mean_simple and mean_cascading is not None and mean_simple > 0
        else None
    )

    total_chain_cost = sum(c["cost"] for c in all_chains)
    cascading_cost = sum(c["cost"] for c in cascading)

    size_hist = Counter(c["n_items"] for c in all_chains)

    # Draft tier mix. §5.6 defines tier 2 as "holds a future pairing that
    # conflicts" -- the tier whose own definition makes it a cascade
    # candidate -- so the tier mix is the leading indicator for the cascade
    # rate above, and the lever that moves it.
    tier_mix: Counter[str] = Counter()
    for sim in sims:
        for row in des.rows_in_measurement_window(cfg, sim):
            if row.category.startswith("DRAFT_TIER"):
                tier_mix[row.category] += 1

    exemplars = sorted(cascading, key=lambda c: -c["cost"])[:n_exemplars]

    return {
        "n_scenarios": len(sims),
        # -- rate (whole-simulation population) --
        "drafts_total": drafts_total,
        "cascading_drafts_total": cascading_total,
        "cascade_rate_mean": statistics.mean(rates) if rates else None,
        "cascade_rate_max": max(rates) if rates else None,
        "n_scenarios_with_drafts": len(rates),
        "n_scenarios_with_cascade": n_with_cascade,
        "share_of_scenarios_with_cascade": (n_with_cascade / len(sims)) if sims else None,
        "per_scenario": per_scenario_rate,
        # -- economics (measurement-window population) --
        "n_chains": len(all_chains),
        "n_cascading_chains": len(cascading),
        "mean_cost_simple_chain": mean_simple,
        "mean_cost_cascading_chain": mean_cascading,
        "amplification_ratio": amplification,
        "cascading_chain_cost_total": cascading_cost,
        "share_of_chain_cost_from_cascades": (
            cascading_cost / total_chain_cost if total_chain_cost > 0 else None
        ),
        "chain_size_histogram": {str(k): v for k, v in sorted(size_hist.items())},
        "max_chain_size": max(size_hist) if size_hist else 0,
        "tier_mix": dict(tier_mix),
        "n_uncovered_chains": sum(1 for c in all_chains if c["uncovered"]),
        # -- reserve-loss mechanism (counted, never priced) --
        "reserve_loss_cascades": sum(sim.n_reserve_loss_cascades for sim in sims),
        "reserve_blocks_lost": sum(sim.n_reserve_blocks_lost for sim in sims),
        "reserve_loss_note": RESERVE_LOSS_NOTE,
        # -- exemplar chains for the drill-down --
        "exemplar_chains": exemplars,
        "depth_note": DEPTH_NOTE,
    }

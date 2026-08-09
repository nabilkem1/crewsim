import re
import statistics
from typing import Any


def select_exemplar_scenarios(cfg: Any, sims: list[Any], k: int = 5) -> tuple[list[tuple[Any, float]], list[tuple[Any, float]]]:
    """S1e-03: the k costliest and k most-typical scenarios, by measurement-
    window cost. "Typical" = closest to the median cost, not the mean --
    cost distributions here are right-skewed (a handful of very bad months
    dominate CVaR), so the median is the representative "ordinary" scenario,
    not a mean pulled upward by the tail this drill-down's own "costliest"
    half already covers separately.
    """
    from ..engine import des

    costs = des.measured_window_costs(cfg, sims)
    paired = list(zip(sims, costs, strict=False))
    costliest = sorted(paired, key=lambda p: -p[1])[:k]
    median = statistics.median(costs) if costs else 0.0
    typical = sorted(paired, key=lambda p: abs(p[1] - median))[:k]
    return costliest, typical


def root_chain(sim: Any, root_uid: int) -> dict[str, Any]:
    """Every ledger row sharing `root_uid`, chronologically, plus the
    matching human-readable trace lines (spec Sec2.3/C2: "root_event_uid is
    what lets you attribute a Thursday cancellation back to the Tuesday
    sick call that caused it, three cascade levels earlier").

    Trace lines are matched by "item {uid}" text, not re-derived from crew/
    pairing objects -- Simulation.trace already narrates SICK_CALL/RESERVE/
    DRAFT/CANCELLED/cascade-visible events with real crew ids and pairing
    ids; re-deriving that narrative a second way risks a silently different
    story than what the ledger actually booked.
    """
    rows = sorted(sim.ledger.filter_by_root(root_uid), key=lambda r: r.sim_time)
    event_uids = {root_uid} | {r.event_uid for r in rows}
    trace_lines = [
        line for line in sim.trace
        if any(re.search(rf"\bitem {uid}\b", line) for uid in event_uids)
    ]
    return {"root_event_uid": root_uid, "rows": rows, "trace_lines": trace_lines}


def build_scenario_drilldown(cfg: Any, sim: Any, cost: float) -> dict[str, Any]:
    """One scenario's full auditable timeline (S1e-03's own acceptance bar):
    the real event trace, plus every CANCELLATION/TERMINAL_PENALTY row's
    full causal chain traced back to its root_event_uid -- "a cancellation
    shows its whole causal chain", not just its own booking line.
    """
    uncovered_roots = sorted({
        r.root_event_uid for r in sim.ledger.rows
        if r.category in ("CANCELLATION", "TERMINAL_PENALTY")
    })
    return {
        "scenario_id": sim.scenario_id,
        "cost": cost,
        "trace": list(sim.trace),
        "chains": [root_chain(sim, root_uid) for root_uid in uncovered_roots],
    }

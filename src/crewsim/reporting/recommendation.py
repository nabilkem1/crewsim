"""Real-R* policy recommendation, computed from an already-run scoreboard.

Reuses gates/v9_sensitivity.py's own recommender formula (spec Sec7.4:
argmin_R[E[cost] + lambda*CVaR95]) instead of a second heuristic --
reporting/report.py already imports across this same gates/reporting
boundary for the identical reason. No new simulation runs here: the
(mean, cvar) pairs already exist in a grid/batch run's scoreboard.
"""

from __future__ import annotations

import re
from typing import Any

from ..gates.v9_sensitivity import R_CANDIDATE_POLICIES, _real_r_recommender

_POLICY_R_RE = re.compile(r"^R(\d+)$")

# The full canonical R sweep (spec Sec7.4's own worked example), for labelling
# whether a recommendation compares all of it or only a subset the caller
# actually ran.
_CANONICAL_R_VALUES = sorted(int(p.lstrip("R")) for p in R_CANDIDATE_POLICIES)


def compute_r_recommendation(
    cfg: Any, terminal_penalty: float, scoreboard: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """None when fewer than 2 R-named policies with real cost figures are in
    the scoreboard, or cfg.sensitivity is not configured -- a recommendation
    among 0 or 1 options, or with no risk-dial values to sweep across, is not
    a recommendation.
    """
    if cfg.sensitivity is None:
        return None

    r_lookup: dict[tuple[int, float], tuple[float, float]] = {}
    # WN-004, spec Sec7.5's own enforcement table: "the optimiser never
    # proposes an infeasible R." A row's `service_level` (kpis.py, only
    # present once configs/base.yaml carries a real u_max/epsilon) says
    # whether THAT policy satisfied the chance constraint -- excluded here,
    # not silently dropped: reported back so a caller can say *why* a policy
    # is missing from the curve, per spec Sec9.3's "no black box" rule.
    excluded_infeasible: list[int] = []
    for row in scoreboard:
        name = row.get("policy") or row.get("policy_name") or ""
        m = _POLICY_R_RE.match(name)
        if not m:
            continue
        mean_cost = row.get("expected_cost")
        cvar95 = row.get("cvar95")
        if mean_cost is None or cvar95 is None:
            continue
        r_value = int(m.group(1))
        service_level = row.get("service_level")
        if service_level is not None and service_level.get("service_level_met") is False:
            excluded_infeasible.append(r_value)
            continue
        r_lookup[(r_value, terminal_penalty)] = (mean_cost, cvar95)

    if len(r_lookup) < 2:
        return None

    recommend = _real_r_recommender(r_lookup)
    curve = [
        {"lambda": lam, "recommended_r": recommend(0, terminal_penalty, lam)}
        for lam in cfg.sensitivity.lambda_risk_dial
    ]
    recommended_rs = [c["recommended_r"] for c in curve]
    r_values_compared = sorted(r for r, _ in r_lookup)

    return {
        "terminal_penalty": terminal_penalty,
        "curve": curve,
        "r_values_compared": r_values_compared,
        "full_r_sweep": r_values_compared == _CANONICAL_R_VALUES,
        "stable": (max(recommended_rs) - min(recommended_rs)) <= cfg.sensitivity.instability_threshold,
        "instability_threshold": cfg.sensitivity.instability_threshold,
        "excluded_infeasible_r": sorted(set(excluded_infeasible)),
    }

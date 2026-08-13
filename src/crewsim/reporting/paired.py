"""Paired CRN comparison of two policies.

Extracted from `cli.py`'s `compare` branch so the CLI and the web API compute
the difference the same way. Two copies of a t-test would be the same defect
this repo already documented when `engine/counterfactuals.py` duplicated
`des.py`'s cost-booking formula -- except worse, because a divergence here
changes a number a planner acts on rather than an internal ranking.

Why the pairing is valid without any extra machinery: `des.run_policy_crn`
draws scenario i's sick-call arrivals from `(master_seed, scenario_id)` alone,
never from the policy, and returns simulations in `scenario_id` order
(`for i in range(n_scenarios)`). So two policies run with the same master seed
produce cost vectors whose element i faces the identical arrival stream, and
element-wise subtraction isolates the policy effect from draw luck.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

# The two-sided 95% quantile. Same closed-form statistical constant already
# allowlisted in data/eligibility_target.py for the same purpose -- a property
# of the t distribution, not a tunable business or reporting input.
_TWO_SIDED_95 = 0.975

CONFIDENCE_LABEL = "95%"


def paired_diff(costs_a: list[float], costs_b: list[float]) -> dict[str, Any]:
    """`b - a` per scenario, with a paired t-test and a 95% CI on the mean.

    Returns `evaluated: False` rather than NaNs when there is only one
    scenario: a single pair has no dispersion to estimate, and a CI of
    [nan, nan] rendered into a UI reads as a computed result.
    """
    if len(costs_a) != len(costs_b):
        raise ValueError(
            f"paired comparison needs equal-length cost vectors, "
            f"got {len(costs_a)} and {len(costs_b)} -- the two policies did not "
            f"run over the same scenario set"
        )

    n = len(costs_a)
    a = np.asarray(costs_a, dtype=float)
    b = np.asarray(costs_b, dtype=float)
    diff = b - a
    mean_diff = float(np.mean(diff)) if n else 0.0

    if n < 2:
        return {
            "evaluated": False,
            "reason": "a confidence interval needs at least 2 paired scenarios",
            "n_scenarios": n,
            "mean_diff": mean_diff,
        }

    se = float(np.std(diff, ddof=1) / np.sqrt(n))
    half_width = float(stats.t.ppf(_TWO_SIDED_95, n - 1) * se)
    t_stat, p_value = stats.ttest_rel(b, a)

    return {
        "evaluated": True,
        "n_scenarios": n,
        "mean_diff": mean_diff,
        "half_width": half_width,
        "ci_lower": mean_diff - half_width,
        "ci_upper": mean_diff + half_width,
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "confidence_label": CONFIDENCE_LABEL,
    }


def format_paired_diff(name_a: str, name_b: str, result: dict[str, Any]) -> str:
    """The one-line summary both the CLI and the UI show."""
    if not result["evaluated"]:
        return f"Paired CRN diff ({name_b} - {name_a}): not evaluated -- {result['reason']}"
    return (
        f"Paired CRN diff ({name_b} - {name_a}): "
        f"{result['mean_diff']:+,.0f} +/- {result['half_width']:,.0f} "
        f"({result['confidence_label']} CI), t = {result['t_stat']:.1f}"
    )

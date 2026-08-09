from collections import Counter
from typing import Any

from ..engine import des
from ..engine.policy import Policy
from . import kpis

NOT_A_RECOMMENDATION = (
    "NOT A RECOMMENDATION -- junior_first and myopic_total_cost exist only to price "
    "Air Transat's mandated drafting rule (impact tier, then senior-first). Neither "
    "may appear in a candidate policy: both are CLI-only draft_mode values, never a "
    "Policy/Stage2Config field (spec Sec5.6)."
)

DRAFT_MODES = ("mandated", "junior_first", "myopic_total_cost")


def _tier_breakdown(cfg: Any, sims: list[Any]) -> dict[str, int]:
    """How many measurement-window drafts landed in each impact tier --
    the reordering a counterfactual makes only changes cost if it also
    changes which tier a draft is satisfied from, not just who within a
    tier is picked."""
    counts: Counter[str] = Counter()
    for sim in sims:
        for row in des.rows_in_measurement_window(cfg, sim):
            if row.category.startswith("DRAFT_TIER"):
                counts[row.category] += 1
    return dict(counts)


def run_counterfactual_comparison(
    cfg: Any, costs: Any, policy: Policy, n_scenarios: int, master_seed: str = "master"
) -> dict[str, dict[str, Any]]:
    """Same policy (same stage1 reserve counts), same CRN scenario set,
    3 draft_modes -- isolates the price of the mandated rule from every
    other policy choice."""
    results = {}
    for mode in DRAFT_MODES:
        sims = des.run_policy_crn(cfg, costs, policy, n_scenarios, master_seed, draft_mode=mode)
        result = kpis.compute_kpis(cfg, sims)
        result["tier_breakdown"] = _tier_breakdown(cfg, sims)
        results[mode] = result
    return results


def print_counterfactual_report(policy_id: str, results: dict[str, dict[str, Any]]) -> None:
    mandated = results["mandated"]["expected_cost"]
    print(NOT_A_RECOMMENDATION)
    print(f"\nCounterfactual draft-selection comparison -- policy {policy_id}, "
          f"{results['mandated']['n_scenarios']} scenario(s) (CRN-paired)")
    print(f"  {'draft_mode':<20}{'E[cost]':>18}{'vs mandated':>18}  tier breakdown")
    for mode in DRAFT_MODES:
        e_cost = results[mode]["expected_cost"]
        delta = e_cost - mandated
        label = "" if mode == "mandated" else f"${delta:>+,.2f}"
        tiers = ", ".join(f"{k}={v}" for k, v in sorted(results[mode]["tier_breakdown"].items()))
        print(f"  {mode:<20}${e_cost:>17,.2f}{label:>18}  {tiers or 'no drafts'}")

    tier_sets = {mode: set(results[mode]["tier_breakdown"]) for mode in DRAFT_MODES}
    if all(tiers <= {"DRAFT_TIER1"} for tiers in tier_sets.values()):
        print("\n  Note: every draft in this run, under all 3 draft_modes, was satisfied from "
              "tier 1 (day-off candidates) -- the mandated rule only redistributes WHO earns the "
              "draft premium here (senior-first vs junior-first), not the total dollar amount, "
              "since tier-1 capacity was never exhausted at this scale of data. The rule has "
              "a real price only in scenarios where tier 1 runs out and the draft reaches tier 2+, "
              "where junior_first/myopic_total_cost can pick a lower-cost tier than mandated senior-"
              "first would.")

    print(f"\n{NOT_A_RECOMMENDATION}")

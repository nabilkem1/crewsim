import itertools
import sys
from typing import Any

import numpy as np

# Real candidate reserve levels -- these five policy files already exist
# and match spec §7.4's own worked example table (R=4,6,8,10,14) exactly.
R_CANDIDATE_POLICIES = ["R4", "R6", "R8", "R10", "R14"]

# IMP-213: swept parameters that the REAL engine never reads, with the reason.
# Sweeping one produces an identical R* at every point, which reads as
# "stable" when it is really "not exercised". On the real path V9 collapses
# such an axis to its configured value and reports it as NOT_EXERCISED rather
# than counting it as stability evidence.
ENGINE_INVARIANT_PARAMETERS: dict[str, str] = {
    "roster_size": (
        "population.roster_size is not read by the engine -- the roster is the "
        "corpus's active crew (load_rosters), whatever this value is"
    ),
}

EXERCISED = "EXERCISED"
NOT_EXERCISED = "NOT_EXERCISED"


def build_r_star_lookup(
    cfg: Any,
    costs: Any,
    n_scenarios: int,
    master_seed: str = "master",
    policies: list[str] = R_CANDIDATE_POLICIES,
    terminal_penalties: list[float] | None = None,
) -> dict[tuple[int, float], tuple[float, float]]:
    """S1d-05: real per-(R, terminal_penalty) mean cost / CVaR95, from
    actual CRN-paired simulation runs (des.run_policy_crn) -- what
    run_v9_gate's real R* argmin (spec §7.4: E[cost] + lam*CVaR95) needs.

    Expensive: len(policies) x len(terminal_penalties) x n_scenarios real
    simulation runs. lambda is NOT swept here -- it's applied afterward to
    the already-computed (mean, cvar) pairs, so it doesn't multiply the
    simulation count (see run_v9_gate).
    """
    from .. import config
    from ..engine import des
    from ..engine.policy import load_policy

    if terminal_penalties is None:
        terminal_penalties = cfg.sensitivity.terminal_penalty

    combos = [(p, tp) for p in policies for tp in terminal_penalties if tp > 1.0]
    lookup: dict[tuple[int, float], tuple[float, float]] = {}
    for i, (policy_name, term_pen) in enumerate(combos, start=1):
        # DisruptionCosts.terminal_penalty_multiple must strictly exceed 1.0
        # (config.py's own validator; spec §7.3: "It must exceed q^cnl, or
        # the model learns that abandoning an item is cheaper than
        # cancelling it"). Not a value a real cost config can ever take, so
        # tp<=1.0 combos are excluded above, not simulated.
        r_value = int(policy_name.lstrip("R"))
        pol_path = config.policy_path(policy_name)
        policy = load_policy(pol_path)
        print(f"  combo {i}/{len(combos)}: policy {policy_name}, terminal_penalty={term_pen}...", file=sys.stderr)

        def _progress(done: int, total: int) -> None:
            print(f"\r    scenario {done}/{total}", end="", file=sys.stderr, flush=True)

        new_disruption = costs.disruption.model_copy(update={"terminal_penalty_multiple": term_pen})
        term_costs = costs.model_copy(update={"disruption": new_disruption})
        sims = des.run_policy_crn(cfg, term_costs, policy, n_scenarios, master_seed, on_progress=_progress)
        print(file=sys.stderr)
        scenario_costs = des.measured_window_costs(cfg, sims)
        lookup[(r_value, term_pen)] = (float(np.mean(scenario_costs)), des.cvar95(scenario_costs))
    return lookup


def real_r_recommender(r_lookup: dict[tuple[int, float], tuple[float, float]]):
    """mock_r_function-shaped closure (r_size, term_pen, lam) -> R* over the
    REAL simulated (mean, cvar) pairs in r_lookup: the real objective from
    spec §7.4, argmin_R[ E[cost](R) + lam * CVaR95(R) ].

    r_size (roster_size) is accepted for call-signature compatibility with
    the surface loop in run_v9_gate but has no effect on the result -- see
    ENGINE_INVARIANT_PARAMETERS. run_v9_gate therefore does not sweep it on
    the real path (IMP-213).
    """
    def recommend(r_size: int, term_pen: float, lam: float) -> int:
        candidates = {r: mean + lam * cvar for (r, tp), (mean, cvar) in r_lookup.items() if tp == term_pen}
        if not candidates:
            raise ValueError(f"no simulated data for terminal_penalty={term_pen!r} in r_lookup")
        return min(candidates, key=lambda r: candidates[r])
    return recommend


def run_v9_gate(cfg: Any, mock_r_function=None, r_lookup=None) -> dict[str, Any]:
    """
    Runs Gate V9 parameter sensitivity sweep.
    Sweeps roster_size, terminal_penalty, and lambda_risk_dial.
    Returns the sensitivity surface, the instability report, and
    `parameters`: per swept parameter, EXERCISED or NOT_EXERCISED (IMP-213).

    On the real path (r_lookup), a parameter in ENGINE_INVARIANT_PARAMETERS
    is not swept: its axis collapses to the configured value
    (population.roster_size) and it is reported NOT_EXERCISED, so an
    identical R* across its nominal range is never counted as stability. An
    injected mock_r_function may depend on any axis, so every axis is swept
    and reported EXERCISED there.
    """
    if not cfg.sensitivity:
        raise ValueError("Sensitivity configuration is missing in base.yaml")

    roster_sizes = cfg.sensitivity.roster_size
    terminal_penalties = cfg.sensitivity.terminal_penalty
    lambdas = cfg.sensitivity.lambda_risk_dial
    parameters = {"roster_size": EXERCISED, "terminal_penalty": EXERCISED, "lambda": EXERCISED}
    not_exercised: dict[str, str] = {}

    if mock_r_function is None:
        if r_lookup is None:
            raise ValueError(
                "run_v9_gate needs either mock_r_function (tests, a fixed synthetic "
                "surface) or r_lookup (real usage -- see build_r_star_lookup). The "
                "old unconditional 'completely hypothetical' default formula has "
                "been removed now that a real recommender exists (S1d-05)."
            )
        # Real path: sweep exactly the terminal_penalty values that were
        # actually simulated (r_lookup's own keys), not cfg.sensitivity's
        # full nominal list -- some of those (e.g. <=1.0) are never
        # simulated at all (see build_r_star_lookup) and have no data here.
        terminal_penalties = sorted({tp for _, tp in r_lookup})
        mock_r_function = real_r_recommender(r_lookup)
        population = getattr(cfg, "population", None)
        roster_sizes = [population.roster_size] if population is not None else roster_sizes[:1]
        for name, reason in ENGINE_INVARIANT_PARAMETERS.items():
            parameters[name] = NOT_EXERCISED
            not_exercised[name] = reason

    surface = []

    for r_size, term_pen, lam in itertools.product(roster_sizes, terminal_penalties, lambdas):
        r_rec = mock_r_function(r_size, term_pen, lam)
        surface.append({
            "roster_size": r_size,
            "terminal_penalty": term_pen,
            "lambda": lam,
            "R": r_rec
        })

    # Determine instability
    # If R varies by more than instability_threshold units across a single
    # swept parameter alone (holding others constant), it's unstable.
    unstable = False
    findings = []

    # Check instability on terminal_penalty
    for r_size in roster_sizes:
        for lam in lambdas:
            rs = [s["R"] for s in surface if s["roster_size"] == r_size and s["lambda"] == lam]
            if max(rs) - min(rs) > cfg.sensitivity.instability_threshold:
                unstable = True
                findings.append(f"R* is highly sensitive to terminal_penalty (varies by {max(rs) - min(rs)} units) at roster_size={r_size}, lambda={lam}")

    # Check instability on lambda
    for r_size in roster_sizes:
        for term_pen in terminal_penalties:
            rs = [s["R"] for s in surface if s["roster_size"] == r_size and s["terminal_penalty"] == term_pen]
            if max(rs) - min(rs) > cfg.sensitivity.instability_threshold:
                unstable = True
                findings.append(f"R* is highly sensitive to lambda (varies by {max(rs) - min(rs)} units) at roster_size={r_size}, terminal_penalty={term_pen}")

    # Deduplicate findings keeping only a few representative ones
    findings = list(set(findings))[:3]

    return {
        "surface": surface,
        "unstable": unstable,
        "findings": findings,
        "parameters": parameters,
        "not_exercised": not_exercised,
    }

def print_v9_report(result: dict[str, Any]):
    parameters = result.get("parameters", {})
    swept = [p for p, status in parameters.items() if status == EXERCISED] or [
        "roster_size", "terminal_penalty", "lambda"
    ]
    print("Gate V9: Parameter Sensitivity")
    print("====================================")
    print(f"Sweeping {', '.join(swept)}...")
    for name, reason in result.get("not_exercised", {}).items():
        print(f"[{NOT_EXERCISED}] {name}: not swept -- {reason}. "
              f"It is not evidence of stability either way.")

    if result["unstable"]:
        print("\n[WARNING] INSTABILITY DETECTED: The recommended reserve level R* is highly sensitive to assumed parameters!")
        for finding in result["findings"]:
            print(f"  - {finding}")
        print("Conclusion: A recommendation resting on a judgement call is visible as such.\n")
    else:
        print(f"\n[STABLE] R* recommendation is robust across the swept parameters ({', '.join(swept)}).\n")

    print("Sensitivity Surface (Sample):")
    print(f"{'Roster':<10} | {'Term Pen':<10} | {'Lambda':<10} | {'Recommended R':<15}")
    print("-" * 55)

    # Print a diverse sample of the surface
    surface = result["surface"]
    # We pick first, middle, last, and some variations
    samples = [surface[0], surface[len(surface)//2], surface[-1]]
    for row in samples:
        print(f"{row['roster_size']:<10} | {row['terminal_penalty']:<10.2f} | {row['lambda']:<10.2f} | {row['R']:<15}")

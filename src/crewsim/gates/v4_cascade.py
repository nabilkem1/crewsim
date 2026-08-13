"""Gate V4 — realised cascade frequency against the historical band (S1d-04, §9.2).

Two things this module deliberately will not do, both learned the hard way:

1. It will not read a key it guessed. The recall check used to be
   `hist["draft_recall"].get("rate", 1.0)`, with its own comment admitting
   *"Assuming draft_recall has a 'rate' or similar"*. The real key is `recall`,
   so the lookup returned the 1.0 default on every run and the marginal-recall
   warning -- S1d-04's own third acceptance criterion -- could never fire. It
   went unnoticed because the test built its input by hand using the same
   guessed key, validating a copy of the mechanism rather than the mechanism.
   `_recall_of` now fails loudly on an unrecognised shape instead of defaulting
   to "everything is fine".

2. It will not render PASS/FAIL on a band it cannot trust. The historical side
   is a reconstruction, and when that reconstruction finds no drafts at all the
   band collapses to [0.0, 0.0] -- an interval a simulated rate can only land in
   by being exactly zero. The gate then reports a confident verdict, naming
   suspect mechanisms that are all on the SIMULATED side, when the real problem
   is that there is nothing to compare against. That is worse than no gate. It
   now returns INCONCLUSIVE and says which precondition failed.
"""
from typing import Any

import numpy as np

from crewsim.data.cascades import cascade_target

# Verdicts. INCONCLUSIVE is not a soft FAIL: it means the comparison could not
# be made, and the caller must not read it as either outcome.
PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"


def _recall_of(draft_recall: dict[str, Any] | None) -> float | None:
    """The reconstruction's recall, or None when the corpus ships no ground truth.

    Raises on an unrecognised shape rather than defaulting. A default here is
    indistinguishable from "recall is fine", which is exactly how the marginal
    warning stayed dead: `.get("rate", 1.0)` on a dict whose key is `recall`
    silently reported perfect recall for every run this gate has ever done.
    """
    if not draft_recall:
        # data/drafts.py::score_recall returns None when _ground_truth.json is
        # absent -- real data has no ground truth, and that is not an error.
        return None
    if "recall" not in draft_recall:
        raise KeyError(
            f"draft_recall has no 'recall' key (got {sorted(draft_recall)}). "
            f"score_recall's contract changed -- fix this lookup rather than "
            f"defaulting, or the marginal-recall warning silently dies again."
        )
    value = draft_recall["recall"]
    # None means "undefined", not "zero": score_recall returns it when the
    # window holds no ground-truth drafts to find. The key must still be
    # PRESENT -- that contract is what keeps this lookup honest -- but a
    # present None is a real answer and must not be coerced to 0.0, which
    # would fire the zero-recall blocker for a window that simply had
    # nothing to reconstruct.
    return None if value is None else float(value)


def run_v4_gate(cfg: Any, sim_cascade_rates: Any, window: str = "holdout") -> dict[str, Any]:
    """Validate a simulated distribution of cascade rates against the historical band.

    Returns a dict carrying `verdict` (PASS/FAIL/INCONCLUSIVE) and, for callers
    that only want a boolean, `pass` -- which is True only for PASS. An
    INCONCLUSIVE run is not a pass.
    """
    hist = cascade_target(cfg, window_name=window)

    sim_mean = float(np.mean(sim_cascade_rates)) if len(sim_cascade_rates) > 0 else 0.0
    gap = sim_mean - hist["rate"]

    recall = _recall_of(hist.get("draft_recall"))
    marginal = cfg.quality_gates.d4_link_marginal
    recall_warning = recall is not None and recall < marginal

    # -- preconditions on the HISTORICAL side, checked before any verdict -----
    # Each is a reason the band cannot support a comparison, not a reason the
    # simulation is wrong. Collected rather than short-circuited so the report
    # can state all of them at once.
    blockers: list[str] = []
    if hist["n_drafts"] == 0:
        blockers.append(
            f"the {window} reconstruction found 0 drafts, so the historical band "
            f"[{hist['ci_low']:.3f}, {hist['ci_high']:.3f}] has zero width and no "
            f"simulated rate except exactly 0.000 could ever fall inside it"
        )
    if recall is not None and recall == 0.0:
        blockers.append(
            f"draft reconstruction recall is 0.000 "
            f"({hist['draft_recall'].get('found', 0)} of "
            f"{hist['draft_recall'].get('true_n', '?')} known drafts found) -- the "
            f"historical side is not a measurement of anything"
        )
    if not sim_cascade_rates:
        blockers.append("no simulated scenario produced a single draft, so there is no rate to compare")

    if blockers:
        verdict = INCONCLUSIVE
        passed = False
    else:
        passed = bool(hist["ci_low"] <= sim_mean <= hist["ci_high"])
        verdict = PASS if passed else FAIL

    return {
        "verdict": verdict,
        "pass": passed,
        "blockers": blockers,
        "sim_mean": sim_mean,
        "hist_mean": hist["rate"],
        "ci_lower": hist["ci_low"],
        "ci_upper": hist["ci_high"],
        "n_hist_drafts": hist["n_drafts"],
        "gap": gap,
        "recall_warning": recall_warning,
        "draft_recall_rate": recall,
    }


def print_v4_report(result: dict[str, Any], window: str) -> None:
    print(f"Gate V4: Cascade Frequency Validation ({window} window)")
    print(f"Historical Band: [{result['ci_lower']:.3f}, {result['ci_upper']:.3f}] "
          f"(Mean: {result['hist_mean']:.3f}, from {result['n_hist_drafts']} reconstructed drafts)")
    print(f"Simulated Mean : {result['sim_mean']:.3f}")
    print(f"Gap            : {result['gap']:+.3f}")

    # S1d-04 AC3: on the same page as the verdict, not in a log somewhere.
    if result["recall_warning"]:
        print(f"\n[WARNING] S0-03 draft reconstruction recall is {result['draft_recall_rate']:.3f}, "
              f"below the marginal bar.")
        print("          This historical band inherits that recall and may understate true cascades.")

    if result["verdict"] == INCONCLUSIVE:
        print("\nVerdict: [INCONCLUSIVE] No comparison could be made. This is not a pass.")
        for reason in result["blockers"]:
            print(f"  - {reason}")
        print("  The simulated side is not implicated by any of the above. Fix the historical")
        print("  reconstruction (S0-03) before reading anything into the simulated rate.")
    elif result["verdict"] == PASS:
        print("\nVerdict: [PASS] Simulated cascade rate matches history.")
    else:
        print("\nVerdict: [FAIL] Simulated cascade rate deviates significantly from history.")
        print("Suspect mechanism: Visibility lag, rule implementations, or base composition.")

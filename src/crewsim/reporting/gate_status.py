"""Real V1/V2/V7 gate status, structured as data.

V1, V2 and V7 each need their own small, independent simulation run --
unlike V3/V4 (which read off whatever sims a caller already produced) or V9
(a real argmin over data a caller already has), there is nothing here to
reuse from a batch run's own scenarios. Extracted out of reporting/report.py
so its HTML gate table and api/routers/processing.py's native JSON gates call
the exact same gate computation, not two copies that can silently drift --
the same "test validates a copy, not the real thing" pattern this project has
found and fixed repeatedly elsewhere.
"""

from __future__ import annotations

from typing import Any

# How much real simulation each gate costs on every call. V7 stopped being
# free when it started hashing real ledgers instead of synthetic draws
# (S1a-11); V2 the moment it started measuring a real Erlang-B shortfall
# (S1b-07). Small and fixed regardless of how many policies/scenarios the
# caller's own batch run used.
V2_SCENARIOS = 2
V7_SCENARIOS = 2
V7_JOBS = 2


def compute_core_gates(cfg: Any, costs: Any, policy: Any, master_seed: str) -> list[dict[str, Any]]:
    """V1 (degeneracy), V2 (Erlang-B bound), V7 (CRN reproducibility), as
    structured {"gate", "verdict", "detail"} rows -- the same shape
    reporting/report.py's gate_rows table and api results consume alike."""
    from ..gates.v1_degeneracy import run_v1_gate
    from ..gates.v2_erlang import run_v2_gate
    from ..gates.v7_reproducibility import run_v7_gate

    v1_result = run_v1_gate(cfg, costs, policy, master_seed=master_seed)
    v2_result = run_v2_gate(cfg, costs, policy, n_scenarios=V2_SCENARIOS, master_seed=master_seed)
    v7_result = run_v7_gate(
        cfg, costs, policy, n_scenarios=V7_SCENARIOS, jobs=V7_JOBS, master_seed=master_seed,
    )

    return [
        {
            "gate": "V1",
            "verdict": "PASS" if v1_result["pass"] else "FAIL",
            "detail": "; ".join(f"{c['name']}: {c['computed']}" for c in v1_result["configurations"]),
        },
        {
            "gate": "V2",
            "verdict": "PASS" if v2_result["pass"] else "FAIL",
            "detail": (
                f"DES shortfall {v2_result['p_hat']:.3f} "
                f"[{v2_result['ci_low']:.3f}, {v2_result['ci_high']:.3f}] vs Erlang-B "
                f"{v2_result['theory']:.3f} at s={v2_result['servers']}, a={v2_result['offered_load']:.2f} "
                f"(bound p_hat >= B; containment is informational)"
            ),
        },
        {
            "gate": "V7",
            "verdict": "PASS" if v7_result["pass"] else "FAIL",
            "detail": (
                f"{v7_result['n_scenarios']} real ledger(s) hashed, sequential vs "
                f"{v7_result['jobs']} worker(s)"
            ),
        },
    ]

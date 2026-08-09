"""Gate V7 -- bit-identical ledgers under multiprocessing (S1a-11, spec Sec9.2).

The acceptance criterion is "same policy, same master seed, twice -> bit-identical
LEDGER", run multi-process, because single-process reproducibility is not the
configuration v2 failed. So this gate runs real scenarios through
des.run_scenario and compares CostLedger.content_hash() -- sequentially first,
then again under joblib.

(This replaces a version that hashed 1000 synthetic floats drawn straight from
crn.event_rng. That exercised the CRN dispatch helpers and nothing else: it
never loaded a policy, never constructed a Simulation and never produced a
ledger, so it could not have detected the v2 defect it exists to catch -- a
process-salted seed used somewhere INSIDE the simulation.)
"""
from __future__ import annotations

from typing import Any

from .. import config
from ..engine import des
from ..engine.policy import Policy


def scenario_ledger_hash(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    scenario_id: int,
    master_seed: str,
    n_scenarios: int,
) -> str:
    """One real scenario -> the content hash of the ledger it produces.

    A module-level function rather than a closure or a lambda: joblib's loky
    backend pickles the callable to hand it to a worker process, and only a
    top-level name survives that. It returns the hash, not the Simulation, so
    nothing depends on a Simulation (which owns a simpy.Environment) being
    picklable.
    """
    sim = des.run_scenario(
        cfg, costs, policy, scenario_id=scenario_id, master_seed=master_seed,
        n_scenarios=n_scenarios,
    )
    return sim.ledger.content_hash()


def run_v7_gate(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    n_scenarios: int,
    jobs: int,
    master_seed: str = "master",
) -> dict[str, Any]:
    """Sequential vs joblib ledger hashes for the same policy and master seed.

    n_scenarios and jobs are required, not defaulted: each scenario is a full
    DES run, so how many to pay for and how widely to spread them is the
    caller's call, and a silent default here would be an unowned cost.

    Sequential runs FIRST on purpose: _load_daily_sick_calls generates the
    scenario-set parquet cache on demand, and letting several worker processes
    race to create the same file is a flake this gate does not need to own.
    """
    import joblib

    hashes_sequential = [
        scenario_ledger_hash(cfg, costs, policy, i, master_seed, n_scenarios)
        for i in range(n_scenarios)
    ]
    hashes_parallel: list[str] = list(
        joblib.Parallel(n_jobs=jobs)(
            joblib.delayed(scenario_ledger_hash)(cfg, costs, policy, i, master_seed, n_scenarios)
            for i in range(n_scenarios)
        )
    )

    mismatches = [
        {"scenario_id": i, "sequential": a, "parallel": b}
        for i, (a, b) in enumerate(zip(hashes_sequential, hashes_parallel, strict=True))
        if a != b
    ]
    return {
        "pass": not mismatches and len(hashes_sequential) == n_scenarios,
        "policy_id": policy.policy_id,
        "master_seed": master_seed,
        "n_scenarios": n_scenarios,
        "jobs": jobs,
        "hashes_sequential": hashes_sequential,
        "hashes_parallel": hashes_parallel,
        "mismatches": mismatches,
    }


def print_v7_report(result: dict[str, Any]) -> None:
    print(
        f"Gate V7: Reproducibility under multiprocessing -- policy {result['policy_id']}, "
        f"master_seed={result['master_seed']!r}, {result['n_scenarios']} scenario(s), "
        f"jobs={result['jobs']}\n"
    )
    for i, (a, b) in enumerate(zip(result["hashes_sequential"], result["hashes_parallel"], strict=True)):
        mark = "==" if a == b else "!="
        print(f"  scenario {i:>3}  sequential {a}  {mark}  parallel {b}")
    if result["pass"]:
        print(
            f"\n  Computed: {result['n_scenarios']} bit-identical ledger(s) across "
            f"{result['jobs']} worker(s). [PASS]"
        )
    else:
        print(f"\n  Computed: {len(result['mismatches'])} ledger(s) differ between "
              f"sequential and multi-process runs. [FAIL]")
        for m in result["mismatches"]:
            print(f"    scenario {m['scenario_id']}: {m['sequential']} != {m['parallel']}")

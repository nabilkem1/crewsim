"""Gate V7 -- bit-identical ledgers under multiprocessing (S1a-11).

Imports the same run_v7_gate the CLI's `gate v7` dispatch calls (S1e-02 fix --
the CLI used to keep its own copy of this logic, which had drifted to reference
undefined variables and crashed with a NameError on every real invocation, while
this test's own copy stayed green because it defined its own locals).

What changed here beyond that: the gate now runs REAL scenarios and compares
real CostLedger hashes. It previously hashed 1000 synthetic floats drawn from
crn.event_rng, which never loaded a policy or built a ledger and so could not
have caught v2's actual defect -- a process-salted seed used inside the sim.

n_scenarios is kept small: each one is a full ~1s DES run, and the property
under test (does process topology change the answer) does not get truer with
more of them.
"""
from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine.policy import load_policy
from crewsim.gates.v7_reproducibility import run_v7_gate, scenario_ledger_hash

N_SCENARIOS = 3


@pytest.fixture(scope="module")
def sim_inputs():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    return cfg, costs, policy


def test_v7_ledgers_are_bit_identical_across_processes(sim_inputs) -> None:
    cfg, costs, policy = sim_inputs
    result = run_v7_gate(cfg, costs, policy, master_seed="v7_master_seed",
                         n_scenarios=N_SCENARIOS, jobs=4)
    assert result["pass"], f"multi-process ledgers differ: {result['mismatches']}"
    assert len(result["hashes_sequential"]) == N_SCENARIOS
    assert result["hashes_sequential"] == result["hashes_parallel"]


def test_v7_hashes_a_real_ledger_not_a_synthetic_draw(sim_inputs) -> None:
    """Guards the specific regression this rewrite fixes: if the gate ever goes
    back to hashing draws instead of a ledger, the hash stops depending on the
    policy, and two materially different reserve pools hash the same."""
    cfg, costs, policy = sim_inputs
    other = load_policy(config.repo_root() / "configs" / "policies" / "R14.yaml")

    h_r6 = scenario_ledger_hash(cfg, costs, policy, 0, "v7_master_seed", N_SCENARIOS)
    h_r14 = scenario_ledger_hash(cfg, costs, other, 0, "v7_master_seed", N_SCENARIOS)
    assert h_r6 != h_r14, (
        "two policies with different reserve pools produced the same ledger hash -- "
        "the hash is not derived from the ledger"
    )


def test_v7_hash_is_stable_across_repeated_runs(sim_inputs) -> None:
    """Same policy, same master seed, twice -> identical (the AC's own words),
    in-process. The multi-process half is the test above."""
    cfg, costs, policy = sim_inputs
    a = scenario_ledger_hash(cfg, costs, policy, 0, "v7_master_seed", N_SCENARIOS)
    b = scenario_ledger_hash(cfg, costs, policy, 0, "v7_master_seed", N_SCENARIOS)
    assert a == b


def test_v7_different_master_seeds_give_different_ledgers(sim_inputs) -> None:
    """CRN's premise: the master seed is what selects a scenario. If it did not
    reach the ledger, every 'reproducible' claim above would be trivially true."""
    cfg, costs, policy = sim_inputs
    a = scenario_ledger_hash(cfg, costs, policy, 0, "seed_a", N_SCENARIOS)
    b = scenario_ledger_hash(cfg, costs, policy, 0, "seed_b", N_SCENARIOS)
    assert a != b

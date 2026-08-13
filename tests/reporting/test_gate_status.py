"""reporting/gate_status.py -- V1/V2/V7 as structured data, shared by
reporting/report.py's HTML gate table and api/routers/processing.py's native
JSON gates so the two surfaces cannot silently disagree about whether a gate
passed."""

from __future__ import annotations

from crewsim import config
from crewsim.engine.policy import load_policy
from crewsim.reporting.gate_status import compute_core_gates


def test_compute_core_gates_returns_v1_v2_v7_with_real_verdicts():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    rows = compute_core_gates(cfg, costs, policy, master_seed="master")

    gates = {row["gate"] for row in rows}
    assert gates == {"V1", "V2", "V7"}
    for row in rows:
        assert row["verdict"] in ("PASS", "FAIL")
        assert row["detail"]  # never an empty explanation


def test_compute_core_gates_v1_passes_on_a_real_run():
    """V1's degeneracy configurations (0 sick calls, all-reserve, 0 reserves)
    are closed-form -- a real run should pass unless the engine regressed."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    rows = compute_core_gates(cfg, costs, policy, master_seed="master")
    v1 = next(row for row in rows if row["gate"] == "V1")
    assert v1["verdict"] == "PASS"

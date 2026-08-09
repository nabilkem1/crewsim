from crewsim import config
from crewsim.engine import des
from crewsim.engine.policy import load_policy
from crewsim.reporting.grid import load_grid_config, run_grid


def test_load_grid_config_reads_the_r_axis():
    """S1e-04 scoped to the R axis only (see configs/grid_mvp.yaml's own
    header comment) -- confirms the 5 real policy files load, not 24."""
    policies = load_grid_config(config.repo_root() / "configs" / "grid_mvp.yaml")
    assert policies == ["R4", "R6", "R8", "R10", "R14"]


def test_grid_combinations_are_crn_paired():
    """The story's own fails_if: 'each combination regenerates its own
    scenarios -- the comparison is unpaired'.

    Proven by spying on des._load_daily_sick_calls -- the one call in
    run_scenario that pulls this scenario's arrival counts from the cached
    scenario set -- across two DIFFERENT real policies. If the call
    arguments (season, master_seed, n_scenarios, scenario_id) match for
    every scenario regardless of which policy is running, the two policies
    are drawing from the identical underlying scenario set: a genuinely
    unpaired comparison (e.g. a bug deriving the cache key from policy_id)
    would show up here as differing call args between pol_a and pol_b.

    What's deliberately NOT asserted: that the two policies produce
    identical sick-call trace lines. They don't -- roster composition
    differs by R (different line-holder/reserve split), so the same
    arrival-count draw can land on a different crew member, or on nobody
    currently on a pairing, under a different policy. That's downstream of
    the shared scenario set, not evidence against pairing.
    """
    import crewsim.engine.des as des_module

    cfg = config.load()
    costs = config.load_costs(cfg)
    pol_a = load_policy(config.repo_root() / "configs" / "policies" / "R4.yaml")
    pol_b = load_policy(config.repo_root() / "configs" / "policies" / "R14.yaml")

    real = des_module._load_daily_sick_calls
    calls: dict[str, list[tuple]] = {"a": [], "b": []}

    def spy(which):
        def _inner(cfg_, season, master_seed, n_scenarios, scenario_id):
            calls[which].append((season, master_seed, n_scenarios, scenario_id))
            return real(cfg_, season, master_seed, n_scenarios, scenario_id)
        return _inner

    des_module._load_daily_sick_calls = spy("a")
    try:
        des.run_policy_crn(cfg, costs, pol_a, 3, "master")
    finally:
        des_module._load_daily_sick_calls = real

    des_module._load_daily_sick_calls = spy("b")
    try:
        des.run_policy_crn(cfg, costs, pol_b, 3, "master")
    finally:
        des_module._load_daily_sick_calls = real

    assert calls["a"] == calls["b"]
    assert len(calls["a"]) == 3


def test_run_grid_matches_direct_run_policy_crn():
    """run_grid must not perturb master_seed per policy (e.g. by mixing the
    policy name into it) -- its result for one policy must exactly match
    calling run_policy_crn/compute_kpis directly with the same inputs."""
    from crewsim.reporting.kpis import compute_kpis

    cfg = config.load()
    costs = config.load_costs(cfg)

    results = run_grid(cfg, costs, ["R6"], n_scenarios=2, master_seed="master")
    assert len(results) == 1

    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    sims = des.run_policy_crn(cfg, costs, policy, 2, "master")
    expected = compute_kpis(cfg, sims)

    assert results[0]["expected_cost"] == expected["expected_cost"]
    assert results[0]["cvar95"] == expected["cvar95"]
    assert results[0]["policy_name"] == "R6"
    assert results[0]["policy_id"] == policy.policy_id


def test_run_grid_parallel_matches_sequential():
    """joblib parallelism (jobs>1) must return the same results, in the
    same policy order, as the sequential (jobs=1) path."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    names = ["R4", "R6", "R8"]

    seq = run_grid(cfg, costs, names, n_scenarios=2, master_seed="master", jobs=1)
    par = run_grid(cfg, costs, names, n_scenarios=2, master_seed="master", jobs=3)

    assert [r["policy_name"] for r in seq] == names
    assert [r["policy_name"] for r in par] == names
    for s, p in zip(seq, par, strict=False):
        assert s["expected_cost"] == p["expected_cost"]
        assert s["cvar95"] == p["cvar95"]


def test_run_grid_result_shape():
    cfg = config.load()
    costs = config.load_costs(cfg)
    results = run_grid(cfg, costs, ["R4", "R10"], n_scenarios=2, master_seed="master")
    assert len(results) == 2
    for row in results:
        for key in ("expected_cost", "cvar95", "uncovered_legs_mean", "reserve_dispatches_mean",
                    "cascade_rate_mean", "policy_name", "policy_id", "policy_hash"):
            assert key in row

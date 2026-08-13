from unittest import mock

import joblib
import pytest

from crewsim import config
from crewsim.engine import des
from crewsim.engine.policy import load_policy
from crewsim.reporting.grid import (
    load_grid_config,
    parallel_hides_scenario_progress,
    run_grid,
)


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


def test_negative_jobs_actually_runs_in_parallel():
    """joblib's convention: n_jobs=-1 means every core, -2 all but one.

    The dispatch used to read `if jobs > 1`, so every negative value fell
    through to the sequential branch -- `crewsim grid --jobs -1`, which the
    flag's own help advertises as "joblib parallelism across policies", ran
    single-process and said nothing. Asserted through joblib.Parallel itself
    rather than by timing, which would be flaky on a loaded machine.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)
    names = ["R4", "R6"]

    seen: list[int | None] = []
    real_parallel = joblib.Parallel

    def spy(*args, **kwargs):
        seen.append(kwargs.get("n_jobs"))
        return real_parallel(*args, **kwargs)

    with mock.patch.object(joblib, "Parallel", spy):
        results = run_grid(cfg, costs, names, n_scenarios=2, master_seed="master", jobs=-1)

    assert seen == [-1], "jobs=-1 must reach joblib.Parallel, not the sequential branch"
    assert [r["policy_name"] for r in results] == names


def test_jobs_zero_is_rejected_not_treated_as_sequential():
    cfg = config.load()
    costs = config.load_costs(cfg)
    with pytest.raises(ValueError, match="not a valid parallelism setting"):
        run_grid(cfg, costs, ["R4"], n_scenarios=1, master_seed="master", jobs=0)


def test_run_grid_returns_per_scenario_costs_for_pairing():
    """The paired CRN difference needs the vector, not the mean.

    Two policies over the same seed must yield equal-length vectors in
    scenario_id order -- that ordering is what makes element-wise subtraction
    a paired comparison rather than a difference of two unrelated samples.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)
    n = 3
    results = run_grid(cfg, costs, ["R4", "R10"], n_scenarios=n, master_seed="master")
    a, b = results
    assert len(a["scenario_costs"]) == n
    assert len(b["scenario_costs"]) == n
    # And they must be the aggregate's own source, not a second measurement.
    assert a["expected_cost"] == pytest.approx(
        sum(a["scenario_costs"]) / n
    )


def test_scenario_progress_fires_per_scenario_not_per_policy():
    """The signal a progress bar needs.

    `on_progress` counts POLICIES, so a single policy over N scenarios reports
    nothing until it is completely finished and then jumps to 100% -- which is
    the common case and looked like a hung run. run_policy_crn has reported
    per-scenario progress all along; _run_one_policy simply never passed a
    callback down to it.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)
    n = 3

    seen: list[tuple[int, int]] = []
    run_grid(cfg, costs, ["R6"], n_scenarios=n, master_seed="master",
             on_scenario_progress=lambda done, total: seen.append((done, total)))

    assert seen == [(1, n), (2, n), (3, n)]


def test_scenario_progress_counts_across_the_whole_grid():
    """Scenario 1 of the second policy is 4/6 in a 2x3 grid, not 1/3 again."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    n = 3

    seen: list[tuple[int, int]] = []
    run_grid(cfg, costs, ["R6", "R10"], n_scenarios=n, master_seed="master",
             on_scenario_progress=lambda done, total: seen.append((done, total)))

    assert seen == [(1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6)]
    assert [d for d, _ in seen] == sorted(d for d, _ in seen), "must advance monotonically"


def test_parallel_hides_scenario_progress_is_honest_about_joblib():
    """Callbacks cannot cross joblib's process boundary, so a caller has to be
    able to ask -- otherwise it renders a bar that never moves."""
    assert parallel_hides_scenario_progress(1) is False
    assert parallel_hides_scenario_progress(-1) is True
    assert parallel_hides_scenario_progress(4) is True


def test_run_grid_returns_per_scenario_cascading_drafts_and_uncovered_legs():
    """The scenario distribution view (api/routers/processing.py's
    /scenarios endpoint) needs a real per-scenario figure for each, not just
    the grid-wide cascade_rate_mean/uncovered_legs_mean -- and those means
    must be exactly derivable from these same per-scenario lists, not a
    second, independently-computed source that could disagree with them."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    n = 3
    results = run_grid(cfg, costs, ["R6"], n_scenarios=n, master_seed="master")
    row = results[0]

    assert len(row["scenario_cascading_drafts"]) == n
    assert len(row["scenario_uncovered_legs"]) == n
    assert all(isinstance(v, int) for v in row["scenario_cascading_drafts"])
    assert all(isinstance(v, int) for v in row["scenario_uncovered_legs"])
    assert row["uncovered_legs_mean"] == pytest.approx(
        sum(row["scenario_uncovered_legs"]) / n
    )


def test_run_grid_result_shape():
    cfg = config.load()
    costs = config.load_costs(cfg)
    results = run_grid(cfg, costs, ["R4", "R10"], n_scenarios=2, master_seed="master")
    assert len(results) == 2
    for row in results:
        for key in ("expected_cost", "cvar95", "uncovered_legs_mean", "reserve_dispatches_mean",
                    "cascade_rate_mean", "policy_name", "policy_id", "policy_hash"):
            assert key in row

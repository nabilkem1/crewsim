import types

from crewsim import config
from crewsim.engine import des
from crewsim.engine.ledger import CostLedger
from crewsim.engine.policy import load_policy


def test_run_policy_crn_returns_n_scenarios():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy("configs/policies/R10.yaml")

    sims = des.run_policy_crn(cfg, costs, policy, 3, master_seed="crn-count-check")
    assert len(sims) == 3
    assert [sim.scenario_id for sim in sims] == [0, 1, 2]


def test_run_policy_crn_reproducible_and_scenarios_differ():
    """Same master_seed replays identically; different scenario_ids within one
    run are not just the same draw repeated."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy("configs/policies/R10.yaml")

    sims1 = des.run_policy_crn(cfg, costs, policy, 3, master_seed="crn-repro-check")
    sims2 = des.run_policy_crn(cfg, costs, policy, 3, master_seed="crn-repro-check")
    costs1 = des.measured_window_costs(cfg, sims1)
    costs2 = des.measured_window_costs(cfg, sims2)
    assert costs1 == costs2

    assert len({round(c) for c in costs1}) > 1, "3 scenarios producing an identical cost each is implausible"


def test_scenario_cache_keyed_by_n_scenarios():
    """Regression test for S1d-04d's own bug: generate_scenarios' cache key used
    to omit n_scenarios, so a cache written for a small n_scenarios request got
    silently reused (and read as all-zero for the missing scenario_ids) by a
    later, larger request under the same master_seed. Reproduce the exact
    sequence that triggered it and confirm the larger request sees real data."""
    cfg = config.load()
    season = cfg.scope.season
    master_seed = "crn-cache-key-regression"

    des._load_daily_sick_calls(cfg, season, master_seed, n_scenarios=3, scenario_id=0)

    counts = des._load_daily_sick_calls(cfg, season, master_seed, n_scenarios=20, scenario_id=15)
    assert sum(counts) > 0, (
        "scenario 15 of a 20-scenario request returned all-zero sick-call counts -- "
        "the cache-key regression is back"
    )


def test_scenario_cache_prefix_stable_across_n_scenarios():
    """crn.generate_streams' children are stable regardless of how many total
    streams were requested (numpy SeedSequence.spawn semantics) -- the cache
    fix must not break that: scenario 0's daily counts must be identical
    whether requested as part of a 3-scenario or a 20-scenario cache."""
    cfg = config.load()
    season = cfg.scope.season
    master_seed = "crn-prefix-stability-check"

    small = des._load_daily_sick_calls(cfg, season, master_seed, n_scenarios=3, scenario_id=0)
    large = des._load_daily_sick_calls(cfg, season, master_seed, n_scenarios=20, scenario_id=0)
    assert small == large


def _generate_in_subprocess(master_seed: str, n_scenarios: int) -> list[int]:
    """Module-level (not a closure) so ProcessPoolExecutor can pickle it."""
    from crewsim import config as config_module
    from crewsim.engine import des as des_module

    cfg = config_module.load()
    return des_module._load_daily_sick_calls(cfg, cfg.scope.season, master_seed, n_scenarios, scenario_id=0)


def test_scenario_cache_concurrent_first_generation_does_not_corrupt():
    """S1e-04's own real 1000-scenario, 5-policy manual check hit this for
    real: joblib.Parallel runs each grid policy as a separate OS process, and
    generate_scenarios' cache check (`if out_file.is_file(): return None`)
    followed by a direct `df.write_parquet(out_file)` is a classic TOCTOU race
    -- several processes all miss an uncached (master_seed, n_scenarios) the
    first time, then write the same path concurrently, and a reader can catch
    the file mid-write (polars.exceptions.ComputeError: "File out of
    specification"). Fixed via write-to-temp-then-os.replace (atomic rename).
    Reproduce with several real OS processes racing the exact same cache key
    that has never been generated before."""
    import concurrent.futures

    cfg = config.load()
    master_seed = "crn-concurrent-cache-regression"
    n_scenarios = 150  # large enough to make the write race reliably win, small enough to stay fast

    # Force a genuinely uncached key every run (not just the first): a
    # second run would otherwise hit the on-disk cache for every worker and
    # never actually race. _scenario_cache_path both computes the path AND
    # generates it as a side effect, so call it once here purely to learn
    # the path, then delete what it just wrote before the real race below.
    cache_path = des._scenario_cache_path(cfg, cfg.scope.season, master_seed, n_scenarios)
    cache_path.unlink(missing_ok=True)
    for tmp in cache_path.parent.glob(f"{cache_path.name}.tmp.*"):
        tmp.unlink()

    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_generate_in_subprocess, master_seed, n_scenarios) for _ in range(8)]
        results = [f.result() for f in futures]

    assert all(sum(r) >= 0 for r in results), "a corrupted cache read raises, it doesn't return partial data"
    assert all(r == results[0] for r in results), "every process must read the same, fully-written scenario"


def test_measured_window_costs_excludes_warmup():
    cfg = config.load()
    warmup_end = cfg.horizon.warmup_days * 1440.0

    ledger = CostLedger()
    ledger.book(scenario_id=0, policy_id="P", sim_time=0.0, event_uid=0, root_event_uid=0,
                crew_id=None, category="RESERVE_STAFFING", amount=1000.0)  # in warm-up, excluded
    ledger.book(scenario_id=0, policy_id="P", sim_time=warmup_end + 10.0, event_uid=1, root_event_uid=1,
                crew_id="C1", category="DRAFT_TIER1", amount=500.0)  # after warm-up, counted

    fake_sim = types.SimpleNamespace(ledger=ledger)
    measured = des.measured_window_costs(cfg, [fake_sim])
    assert measured == [500.0]


def test_measured_window_costs_cooldown_attribution():
    """S1e-01, spec Sec5.0.5: a cool-down-booked row counts only if its
    causal chain ORIGINATES inside the measurement window -- not merely
    because it was booked after warm-up (the bug this replaces: the old
    min_time=warmup_end/no-max_time filter counted every cool-down row,
    including ones from a brand-new sick call that itself arrived during
    cool-down). Also proves root_event_uid==0 rows (the "no causal chain"
    sentinel, e.g. RESERVE_STAFFING) are never grouped together as if they
    shared one origin -- each uses its own booking time."""
    cfg = config.load()
    warmup_end = cfg.horizon.warmup_days * 1440.0
    measurement_end = (cfg.horizon.warmup_days + cfg.horizon.measurement_days) * 1440.0

    ledger = CostLedger()
    # Chain A: root event fires INSIDE the measurement window, but its cost
    # (e.g. a terminal penalty on a cascade) isn't booked until cool-down --
    # must be attributed BACK to the window.
    ledger.book(scenario_id=0, policy_id="P", sim_time=warmup_end + 5.0, event_uid=1,
                root_event_uid=1, crew_id="C1", category="DRAFT_TIER1", amount=500.0)
    ledger.book(scenario_id=0, policy_id="P", sim_time=measurement_end + 100.0, event_uid=2,
                root_event_uid=1, crew_id=None, category="TERMINAL_PENALTY", amount=9000.0)
    # Chain B: root event AND its cost both fire during cool-down (a new
    # sick call arriving in cool-down, not a window-seeded cascade) -- must
    # be excluded entirely, even though it's booked after warm-up.
    ledger.book(scenario_id=0, policy_id="P", sim_time=measurement_end + 50.0, event_uid=3,
                root_event_uid=3, crew_id="C2", category="DRAFT_TIER1", amount=7000.0)
    # Two independent root_event_uid==0 background bookings (RESERVE_STAFFING
    # style) -- must NOT be grouped into one shared "chain": one falls in the
    # window, one in cool-down, and they must be judged independently.
    ledger.book(scenario_id=0, policy_id="P", sim_time=warmup_end + 1.0, event_uid=0,
                root_event_uid=0, crew_id=None, category="RESERVE_STAFFING", amount=250.0)
    ledger.book(scenario_id=0, policy_id="P", sim_time=measurement_end + 1.0, event_uid=0,
                root_event_uid=0, crew_id=None, category="RESERVE_STAFFING", amount=250.0)

    fake_sim = types.SimpleNamespace(ledger=ledger)
    measured = des.measured_window_costs(cfg, [fake_sim])
    # 500 (chain A, in-window) + 9000 (chain A, pulled back from cool-down)
    # + 250 (in-window RESERVE_STAFFING row) = 9750. Chain B's 7000 and the
    # cool-down RESERVE_STAFFING row's 250 are correctly excluded.
    assert measured == [9750.0]


def test_cvar95_is_mean_of_worst_5_percent():
    # 100 scenarios, costs 1..100 -- worst 5% is the top 5 (96..100), mean 98.
    costs = [float(i) for i in range(1, 101)]
    assert des.cvar95(costs) == 98.0


def test_cvar95_empty_is_zero():
    assert des.cvar95([]) == 0.0

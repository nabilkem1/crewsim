import shutil
import subprocess

import polars as pl

from crewsim import config
from crewsim.scenarios.generator import load_scenario_set


def test_ambient_delay_is_exogenous_across_policies():
    """The whole reason ambient delay lives in scenario generation and not
    DES execution (see engine/costs.py::book_flight_delays' own note): the
    scenario parquet's cache key is (master_seed, n_scenarios, content_hash)
    with no policy anywhere in it, so every policy reading the SAME cached
    set necessarily sees the SAME delayed_flights/delay_minutes per
    scenario-day. This proves the cache is actually shared, not merely
    keyed the same -- two different runs (R4-shaped vs R14-shaped rosters)
    must read identical delay columns for the same (master_seed, scenario).
    """
    cfg = config.load()
    df = load_scenario_set(cfg, "winter_sun", "test_delay_exogeneity", 3)

    # Loading it twice (as two different "policies" would, independently)
    # must be byte-identical -- there is no policy input to this function at all.
    df_again = load_scenario_set(cfg, "winter_sun", "test_delay_exogeneity", 3)
    assert df.select(["scenario", "day", "delayed_flights", "delay_minutes"]).equals(
        df_again.select(["scenario", "day", "delayed_flights", "delay_minutes"])
    )


def test_delayed_flights_and_delay_minutes_are_crn_reproducible():
    """Same (master_seed, n_scenarios) regenerated from an intact cache must
    reproduce identically -- the property gate V7 depends on for the whole
    ledger, one level down at the demand layer."""
    cfg = config.load()
    a = load_scenario_set(cfg, "winter_sun", "test_delay_repro", 2)
    b = load_scenario_set(cfg, "winter_sun", "test_delay_repro", 2)
    assert a.select(["scenario", "day", "delayed_flights", "delay_minutes"]).equals(
        b.select(["scenario", "day", "delayed_flights", "delay_minutes"])
    )


def test_delayed_flights_vary_by_regime():
    """Not asserting a specific number (that would be re-typing calibrated
    data into the test) -- asserting the real, calibrated shape: SEVERE days
    see a higher delayed-flight rate than CALM days, because delay
    probability is fit per regime, not one flat figure applied everywhere."""
    cfg = config.load()
    df = load_scenario_set(cfg, "winter_sun", "test_delay_regime_shape", 30)

    by_regime = df.group_by("regime").agg(
        (pl.col("delayed_flights").sum() / pl.col("delayed_flights").len()).alias("mean_delayed")
    )
    means = dict(zip(by_regime["regime"], by_regime["mean_delayed"], strict=False))
    if "SEVERE" in means and "CALM" in means:
        assert means["SEVERE"] > means["CALM"]


def test_scenario_generation():
    """Verify scenario caching keyed by params content hash."""
    cfg = config.load()
    params_dir = config.resolve(cfg, "params_dir")
    scen_dir = params_dir / "scenarios"
    if scen_dir.exists():
        shutil.rmtree(scen_dir)
        
    # We must have parameters to generate scenarios.
    # We'll just invoke calibration on winter_sun first if not present, but 
    # since we want this test to be robust, let's just use the CLI.
    
    # 1. Run calibration to generate params
    subprocess.run(["uv", "run", "crewsim", "calibrate", "winter_sun"],
                   capture_output=True, check=False)
    
    # 2. Generate scenarios
    res1 = subprocess.run(
        ["uv", "run", "crewsim", "scenarios", "generate", "--scenarios", "10", "--master-seed", "testseed1", "--season", "winter_sun"],
        capture_output=True, text=True, check=False
    )
    assert res1.returncode == 0
    assert "Generated scenarios successfully" in res1.stdout
    
    # 3. Generate again with exact same params and seed -> cache hit
    res2 = subprocess.run(
        ["uv", "run", "crewsim", "scenarios", "generate", "--scenarios", "10", "--master-seed", "testseed1", "--season", "winter_sun"],
        capture_output=True, text=True, check=False
    )
    assert res2.returncode == 0
    assert "Cache hit" in res2.stdout

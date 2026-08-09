import hashlib
import json
import os

import numpy as np
import polars as pl

from .. import config
from ..engine import crn


def generate_scenarios(cfg: config.BaseConfig, season: str, master_seed: str, n_scenarios: int) -> str | None:
    """
    Generates scenarios directly from frozen parameters.
    Returns None if cache hit, else path to generated parquet.
    """
    params_dir = config.resolve(cfg, "params_dir")
    import importlib.metadata
    try:
        version = importlib.metadata.version("crewsim")
    except Exception:  # noqa: BLE001 - a version lookup must not abort generation
        version = "unknown"
        
    params_path = params_dir / f"params_v{version}_{season}.json"
    if not params_path.is_file():
        raise FileNotFoundError(f"Missing parameter store for {season}. Run calibration first.")
        
    with open(params_path) as f:
        store = json.load(f)
        
    content_hash = store.get("content_hash", "missing")

    # Cache key. n_scenarios must be part of it: crn.generate_streams's
    # per-scenario streams are stable across different n_scenarios (a fresh
    # SeedSequence(seed).spawn(n) always yields the same first n children
    # regardless of n), but the cached parquet itself only has rows for
    # scenario_ids < the n_scenarios it was generated with. Without this, a
    # cache written for n_scenarios=3 gets silently reused for a later
    # n_scenarios=20 request under the same master_seed -- scenarios 3..19
    # then have no rows, and callers reading them (des.py's
    # _load_daily_sick_calls) see all-zero daily counts with no error.
    # S1d-04d found this the first time anything called generate_scenarios
    # with varying n_scenarios under the same master_seed.
    cache_key = f"{master_seed}_{n_scenarios}_{content_hash}"
    h = hashlib.blake2b(cache_key.encode(), digest_size=16).hexdigest()
    
    # Scenario sets live under params_dir/scenarios -- they are derived from
    # the frozen parameter store, not a report artefact.
    scen_dir = params_dir / "scenarios"
    scen_dir.mkdir(exist_ok=True)
    out_file = scen_dir / f"scenario_set_{h}.parquet"
    
    if out_file.is_file():
        return None # Cache hit
        
    # Generate scenarios
    streams = crn.generate_streams(master_seed, n_scenarios)
    
    horizon_days = cfg.horizon.horizon_days
    
    # From store
    pi0 = store["markov_steady_state_pi0"]
    P = store["markov_transition_matrix_P"]
    multipliers = store["intensity_multipliers"]
    
    states = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]
    
    # Build transition matrix array
    P_matrix = np.zeros((4, 4))
    for i, s1 in enumerate(states):
        for j, s2 in enumerate(states):
            P_matrix[i, j] = P[s1][s2]
            
    pi0_array = np.array([pi0[s] for s in states])
    
    rows = []
    
    for scen_idx, stream in enumerate(streams):
        rng = crn.event_rng(stream, "scenario_generation")
        
        current_state_idx = -1
        
        for day in range(horizon_days):
            if day == 0:
                # Use pi0 for day 1
                current_state_idx = rng.choice(4, p=pi0_array)
            else:
                current_state_idx = rng.choice(4, p=P_matrix[current_state_idx])
                
            current_state = states[current_state_idx]
            mult = multipliers[current_state]
            
            # Apply multipliers to generate sick calls and delays
            # Here we just mock the event materialization 
            # In a real engine, we'd sample NHPP for sick calls and mixture for delays.
            base_sick = 5
            base_delay = 10
            
            sick_calls = rng.poisson(base_sick * mult)
            delays = rng.poisson(base_delay * mult)
            
            rows.append({
                "scenario": scen_idx,
                "day": day,
                "regime": current_state,
                "multiplier": mult,
                "sick_calls": sick_calls,
                "delays": delays
            })
            
    df = pl.DataFrame(rows)
    # Write-then-rename, not a direct write to out_file: the grid runner
    # (S1e-04) runs several policies as separate OS processes via joblib, and
    # each one independently misses the is_file() cache check above the
    # first time a given (master_seed, n_scenarios) pair is uncached -- a
    # direct write lets one process's partial parquet bytes be read by
    # another mid-write (polars.exceptions.ComputeError: "File out of
    # specification"), found via S1e-04's own real 1000-scenario, 5-policy
    # manual check. os.replace is atomic on the same filesystem, so a reader
    # always sees either the fully-old state (file absent) or the
    # fully-new one, never a partial write. Content is a pure function of
    # (master_seed, n_scenarios, content_hash), so two processes racing to
    # both generate and rename is wasted duplicate work, not a correctness
    # issue -- whichever rename lands last still produces identical bytes.
    tmp_file = out_file.with_name(f"{out_file.name}.tmp.{os.getpid()}")
    df.write_parquet(tmp_file)
    os.replace(tmp_file, out_file)

    return str(out_file)

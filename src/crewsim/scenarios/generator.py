import json
import pathlib
import hashlib
import numpy as np
import polars as pl
from typing import Any
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
    except Exception:
        version = "unknown"
        
    params_path = params_dir / f"params_v{version}_{season}.json"
    if not params_path.is_file():
        raise FileNotFoundError(f"Missing parameter store for {season}. Run calibration first.")
        
    with open(params_path, "r") as f:
        store = json.load(f)
        
    content_hash = store.get("content_hash", "missing")
    
    # Cache key
    cache_key = f"{master_seed}_{content_hash}"
    h = hashlib.blake2b(cache_key.encode(), digest_size=16).hexdigest()
    
    # Check if exists
    out_dir = config.ensure_dir(cfg, "reports_dir")  # or wherever scenarios go, say corpus_dir or params_dir
    # Let's put scenario sets in params_dir / scenarios for now
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
    state_to_idx = {s: i for i, s in enumerate(states)}
    
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
    df.write_parquet(out_file)
    
    return str(out_file)

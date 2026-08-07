import json
import hashlib
from datetime import datetime, timezone
from typing import Any
import importlib.metadata

from .. import config
from . import regime, nhpp, delays

def run_pipeline(cfg: config.BaseConfig, season: str, window_name: str = "fitting") -> dict[str, Any]:
    """Runs the full calibration pipeline and emits the parameter store."""
    
    # 1. Run all independent fitters
    regime_res = regime.fit_regime(cfg, season)
    nhpp_res = nhpp.fit_sick_calls(cfg)
    delays_res = delays.fit_delays(cfg, season)
    
    # Get project version
    try:
        version = importlib.metadata.version("crewsim")
    except Exception:
        version = "unknown"
        
    # 2. Build the parameter store
    window: dict[str, Any] = {}
    if cfg.windows is not None:
        w = cfg.windows.get(window_name)
        window = {"start": w.start.isoformat(), "end": w.end.isoformat()}

    store = {
        "params_version": f"v{version}",
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "data_window": window,
        "season": season,
        "markov_steady_state_pi0": regime_res["pi0"],
        "markov_transition_matrix_P": regime_res["matrix"],
        "intensity_multipliers": regime_res["multipliers"],
        "sick_call_nhpp": {
            "coefficients": nhpp_res["coefficients"],
            "dispersion": nhpp_res["dispersion"],
            "duration_lognorm_shape": nhpp_res["duration_lognorm_shape"],
            "duration_lognorm_scale": nhpp_res["duration_lognorm_scale"]
        },
        "flight_delay_mixture": {
            "base_delay_probability": delays_res["base_delay_probability"],
            "components": delays_res["components"]
        },
        "diagnostics": {},
        "validation_targets": {}
    }
    
    # 3. Hash for determinism guarantee
    receipt_str = json.dumps(store, sort_keys=True)
    h = hashlib.blake2b(receipt_str.encode(), digest_size=20)
    store["content_hash"] = "blake2b:" + h.hexdigest()
    
    # 4. Save to JSON
    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / f"params_v{version}_{season}.json"
    
    with open(out_path, "w") as f:
        json.dump(store, f, indent=2)
        
    store["_saved_path"] = str(out_path)
    return store

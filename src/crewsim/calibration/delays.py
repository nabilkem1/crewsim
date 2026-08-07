import json
import hashlib
import polars as pl
import numpy as np
from typing import Any
from sklearn.mixture import GaussianMixture

from .. import config
from ..data import loaders

def fit_delays(cfg: config.BaseConfig, season: str) -> dict[str, Any]:
    """Fits the base delay probability and duration mixture normal distribution."""
    
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    d9 = loaders.load_dataset(cfg, "d9_station_days")
    
    # Get all days and regimes for the target season from D9
    grid = d9.filter(
        pl.col("season") == season
    ).select([
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
        pl.col("station").alias("origin"),
        pl.col("disruption_class").alias("regime")
    ])
    
    # Filter D8 flights to just the dates in our grid and add the regime
    df = d8.with_columns(
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date")
    ).join(grid, on=["date", "origin"], how="inner")
    
    # 1. Base Delay Probability (for a NORMAL day)
    normal_flights = df.filter(pl.col("regime") == "NORMAL")
    delayed_normal = normal_flights.filter(pl.col("delay_minutes") > 0).height
    total_normal = normal_flights.height
    
    base_delay_probability = delayed_normal / total_normal if total_normal > 0 else 0.0
    
    # 2. Duration Mixture (using ALL delays in the season)
    delayed_flights = df.filter(pl.col("delay_minutes") > 0)
    durations = delayed_flights["delay_minutes"].to_numpy().reshape(-1, 1)
    
    # Fit the short-delay / long-delay Gaussian Mixture (configs/base.yaml -> calibration)
    gmm = GaussianMixture(
        n_components=cfg.calibration.delay_gmm_components,
        random_state=cfg.calibration.delay_gmm_random_state,
    )
    gmm.fit(durations)
    
    weights = gmm.weights_
    means = gmm.means_.flatten()
    std_devs = np.sqrt(gmm.covariances_.flatten())
    
    # Sort components by mean (short delay first, long delay second)
    sort_idx = np.argsort(means)
    
    components = []
    for i in sort_idx:
        components.append({
            "weight": float(weights[i]),
            "mean_mins": float(means[i]),
            "std_dev": float(std_devs[i])
        })
        
    out_dict = {
        "season": season,
        "base_delay_probability": float(base_delay_probability),
        "components": components
    }
    
    receipt_str = json.dumps(out_dict, sort_keys=True)
    out_dict["content_hash"] = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]
    
    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / f"delay_mixture_{season}.json"
    
    with open(out_path, "w") as f:
        json.dump(out_dict, f, indent=2)
        
    out_dict["_saved_path"] = str(out_path)
    return out_dict

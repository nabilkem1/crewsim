"""Severity-regime labelling and Markov fit (S0-06)."""

from typing import Any
import yaml
import polars as pl
from datetime import datetime

from .. import config
from ..data import loaders

STATES = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]

def fit_regime(cfg: config.BaseConfig, season: str) -> dict[str, Any]:
    """Fits the 4x4 Markov transition matrix and intensity multipliers."""
    seasons_path = config.resolve(cfg, "seasons_file")
    with open(seasons_path) as f:
        seasons = yaml.safe_load(f)["seasons"]
        
    if season not in seasons:
        raise ValueError(f"Unknown season {season}")
        
    months = seasons[season]["months"]
    
    d4 = loaders.load_dataset(cfg, "d4_absences")
    d8 = loaders.load_dataset(cfg, "d8_flight_movements")
    
    # Get total date range from D8
    min_date = d8.select(pl.col("date").min()).item()
    max_date = d8.select(pl.col("date").max()).item()
    
    if isinstance(min_date, str):
        start = datetime.strptime(min_date, "%Y-%m-%d").date()
    else:
        start = min_date
        
    if isinstance(max_date, str):
        end = datetime.strptime(max_date, "%Y-%m-%d").date()
    else:
        end = max_date
        
    all_dates = pl.DataFrame({
        "date_obj": pl.date_range(
            start, 
            end, 
            "1d",
            eager=True
        )
    }).with_columns(
        pl.col("date_obj").dt.to_string("%Y-%m-%d").alias("date"),
        pl.col("date_obj").dt.month().alias("month")
    ).filter(pl.col("month").is_in(months))
    
    d4_daily = d4.with_columns(
        pl.col("absence_start").cast(pl.String).str.slice(0, 10).alias("date")
    ).group_by("date").len().rename({"len": "sick_calls"})
    
    d8_disruptions = d8.filter(
        (pl.col("delay_minutes") > 0) | (pl.col("cancelled") == 1)
    )
    d8_daily = d8_disruptions.with_columns(
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date")
    ).group_by("date").len().rename({"len": "delays"})
    
    df = all_dates.join(d4_daily, on="date", how="left").join(d8_daily, on="date", how="left")
    df = df.fill_null(0).with_columns(
        (pl.col("sick_calls") + pl.col("delays")).alias("chaos")
    ).sort("date")
    
    quantiles = cfg.calibration.regime_quantiles
    p50 = df.select(pl.col("chaos").quantile(quantiles.p_calm)).item()
    p80 = df.select(pl.col("chaos").quantile(quantiles.p_normal)).item()
    p95 = df.select(pl.col("chaos").quantile(quantiles.p_disrupted)).item()
    
    df = df.with_columns(
        pl.when(pl.col("chaos") <= p50).then(pl.lit("CALM"))
        .when(pl.col("chaos") <= p80).then(pl.lit("NORMAL"))
        .when(pl.col("chaos") <= p95).then(pl.lit("DISRUPTED"))
        .otherwise(pl.lit("SEVERE"))
        .alias("state")
    )
    
    normal_mean = df.filter(pl.col("state") == "NORMAL").select(pl.col("chaos").mean()).item()
    if normal_mean is None or normal_mean == 0:
        normal_mean = 1.0
        
    multipliers = {}
    for state in STATES:
        state_mean = df.filter(pl.col("state") == state).select(pl.col("chaos").mean()).item()
        if state_mean is None: state_mean = 0.0
        multipliers[state] = state_mean / normal_mean
        
    df = df.with_columns(
        pl.col("state").shift(-1).alias("next_state"),
        pl.col("date_obj").shift(-1).alias("next_date_obj")
    ).filter(
        pl.col("next_state").is_not_null() & 
        ((pl.col("next_date_obj") - pl.col("date_obj")).dt.total_days() == 1)
    )
    
    counts = {s: {s2: 0 for s2 in STATES} for s in STATES}
    totals = {s: 0 for s in STATES}
    
    for row in df.iter_rows(named=True):
        i = row["state"]
        j = row["next_state"]
        counts[i][j] += 1
        totals[i] += 1
        
    matrix = {}
    for s in STATES:
        if totals[s] > 0:
            matrix[s] = {s2: counts[s][s2] / totals[s] for s2 in STATES}
        else:
            # Fallback to identity to ensure rows sum to 1.0
            matrix[s] = {s2: (1.0 if s == s2 else 0.0) for s2 in STATES}

    # Calculate pi0 (steady-state probabilities)
    pi0 = {}
    total_days = df.height
    for s in STATES:
        pi0[s] = df.filter(pl.col("state") == s).height / total_days if total_days > 0 else 0.0
            
    import hashlib, json
    
    out_dict = {
        "season": season,
        "matrix": matrix,
        "multipliers": multipliers,
        "pi0": pi0,
        "quantiles": {"p50": p50, "p80": p80, "p95": p95}
    }
    receipt_str = json.dumps(out_dict, sort_keys=True)
    content_hash = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]
    out_dict["content_hash"] = content_hash
    
    # Save to the parameter store
    params_dir = config.ensure_dir(cfg, "params_dir")
    model_filename = seasons[season].get("regime_model", f"regimes_{season}.json")
    out_path = params_dir / model_filename
    
    with open(out_path, "w") as f:
        json.dump(out_dict, f, indent=2)
        
    out_dict["_saved_path"] = str(out_path)
    return out_dict

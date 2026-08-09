"""Sick-call NHPP calibration (S0-07)."""

import hashlib
import json
from typing import Any

import polars as pl
import statsmodels.formula.api as smf
from scipy import stats

from .. import config
from ..data import loaders


def fit_sick_calls(cfg: config.BaseConfig) -> dict[str, Any]:
    """Fits the sick-call intensity GLM and absence duration distribution."""
    
    # 1. Load Data
    d1 = loaders.load_dataset(cfg, "d1_crew_master")
    d4 = loaders.load_dataset(cfg, "d4_absences")
    d9 = loaders.load_dataset(cfg, "d9_station_days")
    
    # 2. Get active pilot combos (base, fleet, position)
    combos = d1.filter(
        (pl.col("crew_group") == "PILOT") & (pl.col("employment_status") == "ACTIVE")
    ).select(["base", "fleet", "position"]).unique()
    
    # 3. Get all days and regimes from D9
    grid = d9.select([
        pl.col("season"),
        pl.col("date").cast(pl.String).str.slice(0, 10).alias("date"),
        pl.col("station").alias("base"),
        pl.col("disruption_class").alias("regime")
    ])
    
    # Add day of week (0=Mon, 6=Sun)
    grid = grid.with_columns(
        pl.col("date").str.to_date("%Y-%m-%d").dt.weekday().cast(pl.String).alias("day_of_week")
    )
    
    # Cross join: every day/base/regime with every valid fleet/position at that base
    exposure = grid.join(combos, on="base", how="inner")
    
    # 4. Count actual sick calls from D4
    d4_counts = d4.filter(
        pl.col("absence_start").is_not_null()
    ).with_columns(
        pl.col("absence_start").cast(pl.String).str.slice(0, 10).alias("date")
    ).group_by(["date", "base", "fleet", "position"]).len().rename({"len": "sick_calls"})
    
    # Merge sick calls onto exposure grid (fill nulls with 0)
    df = exposure.join(
        d4_counts,
        on=["date", "base", "fleet", "position"],
        how="left"
    ).fill_null(0)
    
    # Convert to pandas for statsmodels
    pdf = df.to_pandas()
    
    # We want base to be categorical so that YUL isn't treated as a continuous variable, etc.
    # The C() syntax inside the formula does this automatically.
    formula = "sick_calls ~ C(season) + C(day_of_week) + C(base) + C(fleet) + C(position) + C(regime)"
    
    # Fit Negative Binomial Model
    model = smf.negativebinomial(formula, data=pdf)
    res = model.fit(disp=0)
    
    coefs = res.params.to_dict()
    # In statsmodels NB, alpha is the dispersion parameter
    alpha = coefs.get("alpha", 0.0)
    dispersion = 1.0 + alpha
    
    # 5. Fit Absence Duration (Lognormal)
    d4_dur = d4.filter(
        pl.col("duration_days").is_not_null() & (pl.col("duration_days") > 0)
    )
    durations = d4_dur["duration_days"].to_numpy()
    
    shape, _loc, scale = stats.lognorm.fit(durations, floc=0)
    
    out_dict = {
        "coefficients": coefs,
        "dispersion": dispersion,
        "duration_lognorm_shape": shape,
        "duration_lognorm_scale": scale
    }
    
    receipt_str = json.dumps(out_dict, sort_keys=True)
    out_dict["content_hash"] = hashlib.sha256(receipt_str.encode()).hexdigest()[:8]
    
    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / "nhpp_sick_calls.json"
    
    with open(out_path, "w") as f:
        json.dump(out_dict, f, indent=2)
        
    out_dict["_saved_path"] = str(out_path)
    return out_dict

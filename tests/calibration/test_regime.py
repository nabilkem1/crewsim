"""Test for severity regime calibration (S0-06)."""

from typing import Any

import polars as pl
import pytest

from crewsim import config
from crewsim.calibration import regime


def test_regime_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    # We mock loaders to provide D4 and D8
    # We mock config to return seasons

    def mock_resolve(cfg: config.BaseConfig, key: str) -> str:
        if key == "seasons_file":
            return "configs/seasons.yaml"
        return ""

    def mock_ensure_dir(cfg: config.BaseConfig, key: str) -> Any:
        import pathlib
        return pathlib.Path("/tmp")

    def mock_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        if name == "d4_absences":
            return pl.DataFrame({
                "absence_start": [f"2023-01-{i:02d}T08:00:00" for i in range(1, 21) for _ in range(i)]
            })
        elif name == "d8_flight_movements":
            return pl.DataFrame({
                "date": [f"2023-01-{i:02d}" for i in range(1, 21)],
                "delay_minutes": [0]*20,
                "cancelled": [0]*20
            })
        return pl.DataFrame()
        
    monkeypatch.setattr(regime.config, "resolve", mock_resolve)
    monkeypatch.setattr(regime.config, "ensure_dir", mock_ensure_dir)
    monkeypatch.setattr(regime.loaders, "load_dataset", mock_load_dataset)

    res = regime.fit_regime(config.load(), "winter_sun")
    
    assert res["season"] == "winter_sun"
    assert "CALM" in res["multipliers"]
    assert "NORMAL" in res["multipliers"]
    assert "DISRUPTED" in res["multipliers"]
    assert "SEVERE" in res["multipliers"]
    
    # Check monotonicity
    mults = res["multipliers"]
    assert mults["CALM"] <= mults["NORMAL"] <= mults["DISRUPTED"] <= mults["SEVERE"]
    
    # Check matrix rows sum to 1.0 (approx)
    for row in res["matrix"].values():
        total = sum(row.values())
        if total > 0:
            assert abs(total - 1.0) < 1e-6

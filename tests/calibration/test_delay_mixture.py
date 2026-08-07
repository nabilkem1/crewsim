from typing import Any

import polars as pl
import pytest

from crewsim import config
from crewsim.calibration import delays


def test_delay_mixture(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_ensure_dir(cfg: config.BaseConfig, key: str) -> Any:
        import pathlib
        return pathlib.Path("/tmp")

    def mock_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        if name == "d8_flight_movements":
            return pl.DataFrame({
                "date": ["2023-01-01", "2023-01-01", "2023-01-02", "2023-01-02"],
                "origin": ["YUL", "YYZ", "YUL", "YYZ"],
                "delay_minutes": [0, 15, 0, 150]
            })
        elif name == "d9_station_days":
            return pl.DataFrame({
                "season": ["winter_sun"] * 4,
                "date": ["2023-01-01", "2023-01-01", "2023-01-02", "2023-01-02"],
                "station": ["YUL", "YYZ", "YUL", "YYZ"],
                "disruption_class": ["NORMAL", "NORMAL", "SEVERE", "SEVERE"]
            })
        return pl.DataFrame()

    monkeypatch.setattr(delays.config, "ensure_dir", mock_ensure_dir)
    monkeypatch.setattr(delays.loaders, "load_dataset", mock_load_dataset)

    res = delays.fit_delays(config.load(), "winter_sun")
    
    assert res["season"] == "winter_sun"
    assert "base_delay_probability" in res
    assert "components" in res
    assert len(res["components"]) == 2
    
    # Base delay probability should be 0.5 because on the NORMAL day (2023-01-01),
    # there were 2 flights (YUL, YYZ), and 1 had a delay > 0.
    assert res["base_delay_probability"] == 0.5
    
    # Components should be sorted by mean (short first)
    c1 = res["components"][0]
    c2 = res["components"][1]
    assert c1["mean_mins"] < c2["mean_mins"]

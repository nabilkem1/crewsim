"""Test for NHPP sick-calls calibration (S0-07)."""

from typing import Any

import polars as pl
import pytest

from crewsim.calibration import nhpp


def test_nhpp_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_ensure_dir(cfg: dict[str, Any], key: str) -> Any:
        import pathlib
        return pathlib.Path("/tmp")
        
    def mock_load_dataset(cfg: dict[str, Any], name: str) -> pl.DataFrame:
        import numpy as np
        np.random.seed(42)
        if name == "d1_crew_master":
            grid = []
            for b in ["YUL", "YYZ"]:
                for f in ["A321neoLR", "A330-200"]:
                    for p in ["CP", "FO"]:
                        grid.append({"crew_group": "PILOT", "employment_status": "ACTIVE", "base": b, "fleet": f, "position": p})
            return pl.DataFrame(grid)
        elif name == "d4_absences":
            dates = [f"2023-01-{i:02d}T08:00:00" for i in range(1, 30)] * 5
            return pl.DataFrame({
                "absence_start": dates,
                "base": np.random.choice(["YUL", "YYZ"], len(dates)),
                "fleet": np.random.choice(["A321neoLR", "A330-200"], len(dates)),
                "position": np.random.choice(["CP", "FO"], len(dates)),
                "duration_days": np.random.randint(1, 5, len(dates))
            })
        elif name == "d9_station_days":
            dates = [f"2023-01-{i:02d}" for i in range(1, 30)]
            grid = []
            for d in dates:
                for b in ["YUL", "YYZ"]:
                    grid.append({"season": "winter_sun", "date": d, "station": b, "disruption_class": np.random.choice(["NORMAL", "CALM", "SEVERE"])})
            return pl.DataFrame(grid)
        return pl.DataFrame()
        
    monkeypatch.setattr(nhpp.config, "ensure_dir", mock_ensure_dir)
    monkeypatch.setattr(nhpp.loaders, "load_dataset", mock_load_dataset)
    
    res = nhpp.fit_sick_calls({})
    
    assert "coefficients" in res
    assert "dispersion" in res
    assert res["dispersion"] >= 1.0
    assert res["duration_lognorm_shape"] > 0
    assert res["duration_lognorm_scale"] > 0

from typing import Any

import polars as pl
import pytest

from crewsim import config
from crewsim.calibration import delays


def test_delay_mixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    cfg = config.load()
    base = cfg.scope.base
    fleet = cfg.scope.fleet

    def mock_ensure_dir(cfg: config.BaseConfig, key: str) -> Any:
        # pytest's tmp_path, not a literal "/tmp": that does not exist on Windows.
        return tmp_path

    def mock_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        if name == "d8_flight_movements":
            return pl.DataFrame({
                "date": [
                    "2023-01-01", "2023-01-01", "2023-01-02",
                    "2023-01-03", "2023-01-03",
                    # Wrong fleet at the right station/day -- must be excluded.
                    "2023-01-01",
                    # Right fleet at the wrong station -- must be excluded.
                    "2023-01-01",
                ],
                "origin": [base, base, base, base, base, base, "YYZ"],
                "fleet": [fleet, fleet, fleet, fleet, fleet, "B737", fleet],
                "delay_minutes": [0, 20, 0, 100, 200, 999, 999],
            })
        raise AssertionError(f"fit_delays must not load {name} (F-42: no D9)")

    # F-42: the regime of each day is the computed HMM label table, passed in
    # by the pipeline -- not a D9 file.
    regime_days = pl.DataFrame({
        "season": ["winter_sun"] * 4,
        "date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-01"],
        "station": [base, base, base, "YYZ"],
        "disruption_class": ["NORMAL", "NORMAL", "SEVERE", "NORMAL"],
    })

    monkeypatch.setattr(delays.config, "ensure_dir", mock_ensure_dir)
    monkeypatch.setattr(delays.loaders, "load_dataset", mock_load_dataset)

    res = delays.fit_delays(cfg, "winter_sun", regime_days=regime_days)

    assert res["season"] == "winter_sun"
    assert "delay_by_regime" in res
    assert "components" in res
    assert len(res["components"]) == 2

    # NORMAL: 3 in-scope flights (2023-01-01 x2, 2023-01-02 x1) over 2 days,
    # 1 delayed. The wrong-fleet and wrong-station rows must not count.
    normal = res["delay_by_regime"]["NORMAL"]
    assert normal["delay_probability"] == pytest.approx(1 / 3)
    assert normal["mean_flights_per_day"] == pytest.approx(3 / 2)

    # SEVERE: 2 in-scope flights (2023-01-03 x2) over 1 day, both delayed.
    severe = res["delay_by_regime"]["SEVERE"]
    assert severe["delay_probability"] == pytest.approx(1.0)
    assert severe["mean_flights_per_day"] == pytest.approx(2.0)

    # Regimes absent from the fitting window get an honest zero, not a
    # fabricated fallback.
    for regime in ("CALM", "DISRUPTED"):
        assert res["delay_by_regime"][regime] == {
            "delay_probability": 0.0,
            "mean_flights_per_day": 0.0,
        }

    # Kept for the calibration UI's existing "P(delayed | NORMAL-regime day)"
    # display -- must be exactly the same figure as delay_by_regime["NORMAL"],
    # not an independently computed number that could disagree with it.
    assert res["base_delay_probability"] == normal["delay_probability"]

    # Components should be sorted by mean (short first)
    c1 = res["components"][0]
    c2 = res["components"][1]
    assert c1["mean_mins"] < c2["mean_mins"]


def test_sample_delay_minutes_is_always_at_least_one_minute() -> None:
    """The fitted population is delay_minutes > 0 in whole minutes, so 1.0 is
    the definitional floor -- the short-delay component's own Gaussian tail
    can otherwise draw a non-positive duration."""
    import numpy as np

    rng = np.random.default_rng(0)
    # A component whose mean/std put most of its mass below zero, to force
    # the floor to actually bind rather than pass by chance.
    components = [{"weight": 1.0, "mean_mins": 0.5, "std_dev": 5.0}]
    draws = [delays.sample_delay_minutes(rng, components) for _ in range(200)]
    assert all(d >= 1.0 for d in draws)
    assert any(d == 1.0 for d in draws), "the floor should bind at least once over 200 draws"

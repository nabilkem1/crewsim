"""Test for NHPP sick-calls calibration (S0-07)."""

import datetime
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import pytest
import statsmodels.formula.api as smf

from crewsim import config
from crewsim.calibration import nhpp


def test_nhpp_fit(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    def mock_ensure_dir(cfg: dict[str, Any], key: str) -> Any:
        # pytest's tmp_path, not a literal "/tmp": that does not exist on Windows.
        return tmp_path
        
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
            # Real dates: fit_sick_calls reads D4's recorded span (IMP-516) off the column.
            dates = [datetime.date(2023, 1, i) for i in range(1, 30)] * 5
            return pl.DataFrame({
                "absence_start": dates,
                "base": np.random.choice(["YUL", "YYZ"], len(dates)),
                "fleet": np.random.choice(["A321neoLR", "A330-200"], len(dates)),
                "position": np.random.choice(["CP", "FO"], len(dates)),
                "duration_days": np.random.randint(1, 5, len(dates))
            })
        raise AssertionError(f"fit_sick_calls must not load {name} (F-42: no D9)")

    # F-42: the regime of each station-day is the computed HMM label table
    # (calibration.regime.labels_frame), passed in by the pipeline.
    rng = np.random.default_rng(42)
    regime_days = pl.DataFrame([
        {"season": "winter_sun", "date": f"2023-01-{i:02d}", "station": b,
         "disruption_class": str(rng.choice(["NORMAL", "CALM", "SEVERE"]))}
        for i in range(1, 30) for b in ["YUL", "YYZ"]
    ])

    monkeypatch.setattr(nhpp.config, "ensure_dir", mock_ensure_dir)
    monkeypatch.setattr(nhpp.loaders, "load_dataset", mock_load_dataset)

    res = nhpp.fit_sick_calls(config.load(quiet=True), regime_days=regime_days)

    assert "coefficients" in res
    assert "dispersion" in res
    assert res["dispersion"] >= 1.0
    assert res["duration_lognorm_shape"] > 0
    assert res["duration_lognorm_scale"] > 0
    # scenarios/generator.py needs these to reconstruct the fit's dummy
    # encoding without re-deriving "alphabetically first" itself -- see
    # test_predict_intensity_matches_glm_predict below.
    assert set(res["category_levels"]) == {
        "season", "day_of_week", "base", "fleet", "position", "regime"
    }
    for levels in res["category_levels"].values():
        assert levels == sorted(levels)


def test_predict_intensity_matches_glm_predict() -> None:
    """predict_intensity() must reproduce statsmodels' own res.predict() on
    covariate combinations it was never called with during fitting -- this is
    the actual proof that scenarios/generator.py's real-data sick-call
    intensity (replacing the old hardcoded base_sick=5) is computed
    correctly, not just plausibly."""
    rng = np.random.default_rng(7)
    n = 600
    df = pd.DataFrame({
        "season": rng.choice(["shoulder", "summer_atlantic", "winter_sun"], n),
        "day_of_week": rng.choice([str(i) for i in range(1, 8)], n),
        "base": rng.choice(["YUL", "YVR", "YYZ"], n),
        "fleet": rng.choice(["A321neoLR", "A330-200", "A330-300"], n),
        "position": rng.choice(["CP", "FO"], n),
        "regime": rng.choice(["CALM", "NORMAL", "DISRUPTED", "SEVERE"], n),
    })
    lin = (
        -2.0
        + 0.3 * (df["season"] == "winter_sun").to_numpy()
        + 1.0 * (df["regime"] == "SEVERE").to_numpy()
        + 0.5 * (df["fleet"] == "A321neoLR").to_numpy()
    )
    mu = np.exp(lin)
    df["sick_calls"] = rng.negative_binomial(5, 5 / (5 + mu))

    formula = "sick_calls ~ C(season) + C(day_of_week) + C(base) + C(fleet) + C(position) + C(regime)"
    res = smf.negativebinomial(formula, data=df).fit(disp=0)
    coefficients = res.params.to_dict()
    category_levels = {
        col: sorted(df[col].astype(str).unique().tolist())
        for col in ["season", "day_of_week", "base", "fleet", "position", "regime"]
    }

    probe_rng = np.random.default_rng(0)
    for _ in range(20):
        row = {col: probe_rng.choice(levels) for col, levels in category_levels.items()}
        mine = nhpp.predict_intensity(coefficients, category_levels, row)
        theirs = float(res.predict(pd.DataFrame([row])).iloc[0])
        assert mine == pytest.approx(theirs, rel=1e-9)


def test_predict_intensity_rejects_unseen_level() -> None:
    with pytest.raises(ValueError, match="never observed"):
        nhpp.predict_intensity(
            {"Intercept": 0.0},
            {"base": ["YUL", "YVR"]},
            {"base": "YXE"},
        )


def test_sample_count_poisson_limit_matches_mean() -> None:
    rng = np.random.default_rng(1)
    draws = [nhpp.sample_count(rng, mean=8.0, dispersion=1.0) for _ in range(20000)]
    assert np.mean(draws) == pytest.approx(8.0, rel=0.05)


def test_sample_count_zero_mean_is_zero() -> None:
    rng = np.random.default_rng(1)
    assert nhpp.sample_count(rng, mean=0.0, dispersion=1.3) == 0


def test_sample_count_overdispersed_has_more_variance_than_poisson_mean() -> None:
    rng = np.random.default_rng(2)
    mean = 6.0
    draws = np.array([nhpp.sample_count(rng, mean=mean, dispersion=2.5) for _ in range(20000)])
    assert draws.mean() == pytest.approx(mean, rel=0.1)
    # NB2 variance = mean + alpha*mean^2 = 6 + 1.5*36 = 60, Poisson would be 6.
    assert draws.var() > mean * 3

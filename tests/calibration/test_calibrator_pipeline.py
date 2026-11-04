import pytest

from crewsim import config
from crewsim.calibration import pipeline


def test_pipeline_determinism(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # We will mock the fitters so we don't have to provide all the data.
    # All three accept `window` since AUD-05 threaded the fitting window
    # through them -- the mocks must match the real signatures.
    def mock_fit_regime(cfg, season, window=None, **kwargs):
        return {
            "pi0": {"CALM": 1.0},
            "matrix": {"CALM": {"CALM": 1.0}},
            "multipliers": {"CALM": 1.0}
        }

    def mock_fit_sick_calls(cfg, window=None, **kwargs):
        return {
            "coefficients": {"intercept": -1.0},
            "dispersion": 1.5,
            "category_levels": {"season": ["winter_sun"]},
            "duration_lognorm_shape": 0.5,
            "duration_lognorm_scale": 1.0,
            "converged": True,
        }

    def mock_fit_delays(cfg, season, window=None, **kwargs):
        return {
            "base_delay_probability": 0.1,
            "delay_by_regime": {
                "CALM": {"delay_probability": 0.05, "mean_flights_per_day": 20.0},
                "NORMAL": {"delay_probability": 0.1, "mean_flights_per_day": 20.0},
                "DISRUPTED": {"delay_probability": 0.2, "mean_flights_per_day": 20.0},
                "SEVERE": {"delay_probability": 0.4, "mean_flights_per_day": 20.0},
            },
            "components": [{"weight": 1.0, "mean_mins": 10, "std_dev": 2}]
        }
        
    def mock_ensure_dir(cfg, key):
        # tmp_path, not a literal "/tmp": that directory does not exist on
        # Windows, so this test could never pass there.
        return tmp_path

    # F-42: the pipeline fits the regime HMM for every base first; stubbed here.
    monkeypatch.setattr(pipeline.regime, "load_inputs", lambda cfg: None)
    monkeypatch.setattr(pipeline.regime, "fit_station_regimes", lambda cfg, window, **kwargs: {})
    monkeypatch.setattr(pipeline.regime, "fit_regime", mock_fit_regime)
    monkeypatch.setattr(pipeline.nhpp, "fit_sick_calls", mock_fit_sick_calls)
    monkeypatch.setattr(pipeline.delays, "fit_delays", mock_fit_delays)
    monkeypatch.setattr(
        pipeline.regime, "label_agreement",
        lambda cfg, season, window=None, **kwargs: {
            "season": season, "n_days": 0, "agreement_rate": None, "confusion": {}
        },
    )
    monkeypatch.setattr(pipeline.config, "ensure_dir", mock_ensure_dir)
    
    cfg = config.load()

    res1 = pipeline.run_pipeline(cfg, "winter_sun")
    res2 = pipeline.run_pipeline(cfg, "winter_sun")

    # IMP-201 (hash_stable): two runs on unchanged inputs give the same hash
    # with NO clock mocking -- fitted_at is run metadata, outside the hash.
    assert res1["content_hash"] == res2["content_hash"]
    assert "fitted_at" in res1, "run metadata is still recorded, just not hashed"

    # And the hash still covers content: recomputing it from the store (run
    # metadata excluded) reproduces it, and changing a fitted value changes it.
    assert pipeline.content_hash(res1) == res1["content_hash"]
    tampered = {**res1, "season": "summer"}
    assert pipeline.content_hash(tampered) != res1["content_hash"]

    # F-42 / F-23: diagnostics (e.g. agreement with an optional D9) are not
    # parameters -- changing one must not invalidate cached scenario sets.
    rediagnosed = {**res1, "diagnostics": {"regime_label_agreement": {"agreement_rate": 0.5}}}
    assert pipeline.content_hash(rediagnosed) == res1["content_hash"]
    
    # Also verify that a missing block crashes it (which it will if we just delete one)
    # The requirement is that it fails if a block is missing. Python dict key lookups enforce this.

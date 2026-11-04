import json
import os

import pytest

from crewsim import config
from crewsim.calibration import pipeline


def test_param_store_structure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
        return tmp_path
        
    # F-42: the pipeline fits the regime HMM for every base first; stubbed here.
    monkeypatch.setattr(pipeline.regime, "load_inputs", lambda cfg: None)
    monkeypatch.setattr(pipeline.regime, "fit_station_regimes", lambda cfg, window, **kwargs: {})
    monkeypatch.setattr(pipeline.regime, "fit_regime", mock_fit_regime)
    monkeypatch.setattr(pipeline.nhpp, "fit_sick_calls", mock_fit_sick_calls)
    monkeypatch.setattr(pipeline.delays, "fit_delays", mock_fit_delays)
    monkeypatch.setattr(
        pipeline.regime, "label_agreement",
        lambda cfg, season, window=None, **kwargs: {"season": season, "n_days": 0, "agreement_rate": None, "confusion": {}},
    )
    monkeypatch.setattr(pipeline.config, "ensure_dir", mock_ensure_dir)
    
    cfg = config.load()

    res = pipeline.run_pipeline(cfg, "winter_sun")
    
    out_file = res["_saved_path"]
    assert os.path.exists(out_file)
    
    with open(out_file) as f:
        data = json.load(f)
        
    expected_keys = [
        "params_version", "fitted_at", "data_window", "season", 
        "markov_steady_state_pi0", "markov_transition_matrix_P", 
        "intensity_multipliers", "regime_hmm", "sick_call_nhpp", 
        "flight_delay_mixture", "content_hash",
        "diagnostics", "validation_targets"
    ]
    
    for key in expected_keys:
        assert key in data
        
    assert data["content_hash"].startswith("blake2b:")
    assert "coefficients" in data["sick_call_nhpp"]

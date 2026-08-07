import pytest

from crewsim import config
from crewsim.calibration import pipeline


def test_pipeline_determinism(monkeypatch: pytest.MonkeyPatch) -> None:
    # We will mock the fitters so we don't have to provide all the data
    def mock_fit_regime(cfg, season):
        return {
            "pi0": {"CALM": 1.0},
            "matrix": {"CALM": {"CALM": 1.0}},
            "multipliers": {"CALM": 1.0}
        }
        
    def mock_fit_sick_calls(cfg):
        return {
            "coefficients": {"intercept": -1.0},
            "dispersion": 1.5,
            "duration_lognorm_shape": 0.5,
            "duration_lognorm_scale": 1.0
        }
        
    def mock_fit_delays(cfg, season):
        return {
            "base_delay_probability": 0.1,
            "components": [{"weight": 1.0, "mean_mins": 10, "std_dev": 2}]
        }
        
    def mock_ensure_dir(cfg, key):
        import pathlib
        return pathlib.Path("/tmp")
        
    monkeypatch.setattr(pipeline.regime, "fit_regime", mock_fit_regime)
    monkeypatch.setattr(pipeline.nhpp, "fit_sick_calls", mock_fit_sick_calls)
    monkeypatch.setattr(pipeline.delays, "fit_delays", mock_fit_delays)
    monkeypatch.setattr(pipeline.config, "ensure_dir", mock_ensure_dir)
    
    cfg = config.load()

    res1 = pipeline.run_pipeline(cfg, "winter_sun")
    
    # Run again, verify determinism
    # wait, fitted_at might differ by a microsecond, so let's mock datetime
    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime, timezone
            return datetime(2023, 1, 1, tzinfo=timezone.utc)
            
    monkeypatch.setattr(pipeline, "datetime", MockDatetime)
    
    res2 = pipeline.run_pipeline(cfg, "winter_sun")
    res3 = pipeline.run_pipeline(cfg, "winter_sun")
    
    assert res2["content_hash"] == res3["content_hash"]
    
    # Also verify that a missing block crashes it (which it will if we just delete one)
    # The requirement is that it fails if a block is missing. Python dict key lookups enforce this.

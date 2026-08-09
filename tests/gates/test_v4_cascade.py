import types

from crewsim.gates.v4_cascade import run_v4_gate


def test_v4_cascade_gate(monkeypatch):
    # Mock config
    cfg = types.SimpleNamespace()
    cfg.windows = types.SimpleNamespace()
    cfg.windows.holdout = types.SimpleNamespace(start=1000, end=2000)
    cfg.quality_gates = types.SimpleNamespace()
    cfg.quality_gates.d6_d7_join_pass = 0.8
    cfg.quality_gates.d4_link_marginal = 0.9
    
    # Mock cascade_target
    def mock_cascade_target(cfg, window_name):
        return {
            "rate": 0.15,
            "ci_low": 0.10,
            "ci_high": 0.20,
            "draft_recall": {"rate": 0.85} # Below 0.9 -> marginal
        }
        
    monkeypatch.setattr("crewsim.gates.v4_cascade.cascade_target", mock_cascade_target)
    
    sim_rates = [0.12, 0.16, 0.15]
    result = run_v4_gate(cfg, sim_rates, window="holdout")
    
    # Assert
    assert result["pass"] is True
    assert result["recall_warning"] is True
    
def test_v4_cascade_gate_fail(monkeypatch):
    # Mock config
    cfg = types.SimpleNamespace()
    cfg.windows = types.SimpleNamespace()
    cfg.windows.holdout = types.SimpleNamespace(start=1000, end=2000)
    cfg.quality_gates = types.SimpleNamespace()
    cfg.quality_gates.d6_d7_join_pass = 0.8
    cfg.quality_gates.d4_link_marginal = 0.9
    
    # Mock cascade_target
    def mock_cascade_target(cfg, window_name):
        return {
            "rate": 0.15,
            "ci_low": 0.10,
            "ci_high": 0.20,
            "draft_recall": {"rate": 0.95} # Good recall
        }
        
    monkeypatch.setattr("crewsim.gates.v4_cascade.cascade_target", mock_cascade_target)
    
    # Rate of 0.25 is way outside [0.10, 0.20]
    sim_rates = [0.25, 0.26]
    result = run_v4_gate(cfg, sim_rates, window="holdout")
    
    # Assert
    assert result["pass"] is False
    assert result["recall_warning"] is False

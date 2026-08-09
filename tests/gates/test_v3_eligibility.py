from crewsim import config
from crewsim.data.eligibility_target import reconstruct_eligibility
from crewsim.gates.v3_eligibility import run_v3_gate


def _real_holdout_band():
    """S1c-05: reconstruct_eligibility is real (S0-04) -- it needs a real
    cfg (load_rosters, cfg.windows, cfg.scope), not the SimpleNamespace()
    mock this file used when the historical side was a hardcoded ~0.30
    fake. Computed once per test rather than hardcoded, so these tests
    stay correct if the corpus is ever regenerated."""
    cfg = config.load()
    hist = reconstruct_eligibility(cfg, "holdout")
    return cfg, hist


def test_v3_gate_passes_when_in_bounds():
    cfg, hist = _real_holdout_band()

    # A simulated distribution centered exactly on the real historical mean.
    sim_dist = [hist["mean"]] * 100

    result = run_v3_gate(cfg, sim_dist, window="holdout")

    assert result["pass"] is True
    assert "ci_lower" in result
    assert "ci_upper" in result
    assert result["ci_lower"] <= result["sim_mean"] <= result["ci_upper"]

def test_v3_gate_fails_when_out_of_bounds():
    cfg, hist = _real_holdout_band()

    # A simulated distribution far above the real historical band -- not a
    # hardcoded literal, so this stays a genuine out-of-bounds case even if
    # the real historical mean itself changes (e.g. a corpus regeneration).
    sim_dist = [hist["ci_upper"] + 0.20] * 100

    result = run_v3_gate(cfg, sim_dist, window="holdout")

    assert result["pass"] is False
    assert result["sim_mean"] > result["ci_upper"]

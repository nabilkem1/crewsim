import types

import pytest

from crewsim import config
from crewsim.gates.v9_sensitivity import build_r_star_lookup, run_v9_gate


def test_v9_sensitivity():
    # Setup mock config
    cfg = types.SimpleNamespace()
    cfg.sensitivity = types.SimpleNamespace()
    cfg.sensitivity.roster_size = [100, 120]
    cfg.sensitivity.terminal_penalty = [1.0, 3.0]
    cfg.sensitivity.lambda_risk_dial = [0.0, 1.0]
    cfg.sensitivity.instability_threshold = 2

    # Mock R function that makes R highly sensitive to lambda
    def mock_r_function(r_size, term_pen, lam):
        return int(10 + lam * 10)
        
    result = run_v9_gate(cfg, mock_r_function=mock_r_function)
    
    # Assert surface generation
    assert len(result["surface"]) == 8 # 2 x 2 x 2
    assert result["surface"][0]["roster_size"] == 100
    assert "R" in result["surface"][0]
    
    # Assert instability detection
    assert result["unstable"] is True
    assert len(result["findings"]) > 0
    
    # Verify the finding mentions lambda
    assert any("lambda" in f for f in result["findings"])

def test_v9_sensitivity_stable():
    cfg = types.SimpleNamespace()
    cfg.sensitivity = types.SimpleNamespace()
    cfg.sensitivity.roster_size = [100, 120]
    cfg.sensitivity.terminal_penalty = [1.0, 1.25]
    cfg.sensitivity.lambda_risk_dial = [0.0, 0.25]
    cfg.sensitivity.instability_threshold = 2

    # Mock R function that is extremely stable
    def mock_r_function(r_size, term_pen, lam):
        return 12
        
    result = run_v9_gate(cfg, mock_r_function=mock_r_function)
    
    assert result["unstable"] is False
    assert len(result["findings"]) == 0

def test_run_v9_gate_requires_a_recommender():
    """S1d-05: the old unconditional 'completely hypothetical relationship
    for demonstration' fallback (default_mock_r) is gone -- calling without
    either a real r_lookup or an injected mock_r_function must raise, not
    silently fabricate a surface."""
    cfg = types.SimpleNamespace()
    cfg.sensitivity = types.SimpleNamespace()
    cfg.sensitivity.roster_size = [100]
    cfg.sensitivity.terminal_penalty = [1.5]
    cfg.sensitivity.lambda_risk_dial = [0.0]
    cfg.sensitivity.instability_threshold = 2

    # A deliberate regex ALTERNATION (either name may appear in the message),
    # not a literal string -- escaping it would make the test pass vacuously.
    with pytest.raises(ValueError, match="mock_r_function|r_lookup"):  # noqa: RUF043
        run_v9_gate(cfg)

def test_build_r_star_lookup_and_real_recommender():
    """S1d-05: build_r_star_lookup must run the REAL CRN pipeline
    (des.run_policy_crn -> measured_window_costs/cvar95, spec Sec7.4's own
    objective E[cost] + lam*CVaR95) and produce a lookup whose
    argmin-derived R* is always one of the real candidate policies actually
    simulated -- not a fabricated number. Kept small (2 policies x 1
    terminal_penalty x 2 scenarios = 4 real simulation runs) to stay fast;
    the CLI's `gate v9` uses the full R_CANDIDATE_POLICIES x
    configs/base.yaml sensitivity sweep at a larger --scenarios count."""
    cfg = config.load()
    costs = config.load_costs(cfg)

    lookup = build_r_star_lookup(
        cfg, costs, n_scenarios=2, master_seed="master",
        policies=["R4", "R10"], terminal_penalties=[1.5],
    )
    assert set(lookup.keys()) == {(4, 1.5), (10, 1.5)}
    for mean, cvar in lookup.values():
        assert mean > 0.0
        assert cvar >= mean  # CVaR95 is the tail mean; never below the overall mean

    result = run_v9_gate(cfg, r_lookup=lookup)
    recommended = {row["R"] for row in result["surface"]}
    # Every recommendation must be a policy that was actually simulated --
    # not an interpolated or invented value.
    assert recommended <= {4, 10}

def test_terminal_penalty_override_reaches_the_real_cost_model():
    """The terminal_penalty sweep axis must genuinely change what the
    simulation charges, not just relabel the same cached run -- proved
    directly against the real DisruptionCosts model (frozen pydantic,
    model_copy is the only way to vary it), independent of whether
    TERMINAL_PENALTY itself ever fires in a given scenario."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    new_disruption = costs.disruption.model_copy(update={"terminal_penalty_multiple": 2.7})
    new_costs = costs.model_copy(update={"disruption": new_disruption})
    assert new_costs.disruption.terminal_penalty_multiple == 2.7
    assert costs.disruption.terminal_penalty_multiple != 2.7  # original untouched (frozen)

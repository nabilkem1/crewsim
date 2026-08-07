from crewsim.data.eligibility_target import reconstruct_eligibility

def test_reconstruct_eligibility():
    """Verify that reconstruct_eligibility generates a distribution with mean ~30%."""
    # We pass None for cfg since our mock implementation doesn't strictly need it right now.
    res = reconstruct_eligibility(None, "winter_sun")
    
    assert "mean" in res
    assert "ci_lower" in res
    assert "ci_upper" in res
    assert "distribution" in res
    
    mean = res["mean"]
    assert 0.25 <= mean <= 0.35, f"Expected mean ~30%, got {mean:.2%}"
    
    dist = res["distribution"]
    assert len(dist) == 1000
    
    assert res["ci_lower"] < mean < res["ci_upper"]

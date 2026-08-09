from crewsim import config
from crewsim.data.eligibility_target import reconstruct_eligibility


def test_reconstruct_eligibility():
    """S0-04: reconstruct_eligibility must be a real historical
    reconstruction (real D4 absences, real D2 reserve blocks, real
    is_legal_assignment), not the fake np.random.binomial(pool_size, 0.30)
    mock this test used to check the output of -- that mock's own docstring
    admitted it was fabricated, and this test only verified the mock
    matched its own hardcoded parameters. A real historical mean has no
    reason to be near any particular fixed number (S1c-05 found the real
    rate is under 1%, nothing like the mock's ~30%), so this only checks
    the structural properties S0-04's own acceptance criterion requires:
    a genuine distribution with a confidence interval, not a point.
    """
    cfg = config.load()
    res = reconstruct_eligibility(cfg, "holdout")

    assert "mean" in res
    assert "ci_lower" in res
    assert "ci_upper" in res
    assert "distribution" in res

    mean = res["mean"]
    assert 0.0 <= mean <= 1.0

    dist = res["distribution"]
    # A DISTRIBUTION, not a point (S0-04's own manual-check bar) -- real
    # history in this corpus yields hundreds of events, not a token handful.
    assert len(dist) > 100

    assert res["ci_lower"] <= mean <= res["ci_upper"]
    assert res["ci_lower"] >= 0.0

def test_reconstruct_eligibility_differs_by_window():
    """The fitting and holdout windows cover different real historical
    periods (S0-09) -- a real reconstruction has no reason to produce the
    same distribution for both (the old fake mock did, since it ignored
    its `season`/window argument entirely, which was itself a sign it
    wasn't touching real data)."""
    cfg = config.load()
    fitting = reconstruct_eligibility(cfg, "fitting")
    holdout = reconstruct_eligibility(cfg, "holdout")

    # Not a bare != : a real reconstruction should differ by a real margin,
    # not just in some far decimal place from floating-point noise.
    assert abs(fitting["mean"] - holdout["mean"]) > 0.0001

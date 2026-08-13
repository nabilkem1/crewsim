"""reporting/recommendation.py -- real R* recommendation from an
already-computed scoreboard, reusing gates/v9_sensitivity.py's own formula."""

from __future__ import annotations

import types

from crewsim.reporting.recommendation import compute_r_recommendation


def _cfg(lambdas: list[float] = (0.0, 1.0, 5.0), instability_threshold: int = 2) -> types.SimpleNamespace:
    sensitivity = types.SimpleNamespace(
        lambda_risk_dial=list(lambdas), instability_threshold=instability_threshold
    )
    return types.SimpleNamespace(sensitivity=sensitivity)


def test_recommends_the_cvar_minimizer_at_lambda_zero() -> None:
    # At lambda=0 the objective is pure E[cost], so R6 (cheapest mean) wins.
    scoreboard = [
        {"policy": "R4", "expected_cost": 100_000.0, "cvar95": 400_000.0},
        {"policy": "R6", "expected_cost": 90_000.0, "cvar95": 300_000.0},
        {"policy": "R10", "expected_cost": 120_000.0, "cvar95": 150_000.0},
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[0.0]), terminal_penalty=1.5, scoreboard=scoreboard)
    assert rec is not None
    assert rec["curve"] == [{"lambda": 0.0, "recommended_r": 6}]


def test_high_lambda_favours_the_low_cvar_policy() -> None:
    # At a large lambda the CVaR term dominates, so R10 (lowest CVaR) wins
    # even though it has the highest mean cost.
    scoreboard = [
        {"policy": "R4", "expected_cost": 100_000.0, "cvar95": 400_000.0},
        {"policy": "R6", "expected_cost": 90_000.0, "cvar95": 300_000.0},
        {"policy": "R10", "expected_cost": 120_000.0, "cvar95": 150_000.0},
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[10.0]), terminal_penalty=1.5, scoreboard=scoreboard)
    assert rec is not None
    assert rec["curve"] == [{"lambda": 10.0, "recommended_r": 10}]


def test_fewer_than_two_policies_is_not_a_recommendation() -> None:
    assert compute_r_recommendation(_cfg(), 1.5, [{"policy": "R6", "expected_cost": 1.0, "cvar95": 2.0}]) is None
    assert compute_r_recommendation(_cfg(), 1.5, []) is None


def test_non_r_named_policies_are_ignored_not_crashed_on() -> None:
    scoreboard = [
        {"policy": "custom-policy.yaml", "expected_cost": 1.0, "cvar95": 2.0},
        {"policy": "R6", "expected_cost": 90_000.0, "cvar95": 300_000.0},
    ]
    assert compute_r_recommendation(_cfg(), 1.5, scoreboard) is None  # only 1 real R policy


def test_rows_missing_cost_figures_are_skipped() -> None:
    scoreboard = [
        {"policy": "R4", "expected_cost": None, "cvar95": None},
        {"policy": "R6", "expected_cost": 90_000.0, "cvar95": 300_000.0},
        {"policy": "R10", "expected_cost": 120_000.0, "cvar95": 150_000.0},
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[0.0]), 1.5, scoreboard)
    assert rec is not None
    assert rec["r_values_compared"] == [6, 10]


def test_full_r_sweep_flag_reflects_all_five_canonical_policies() -> None:
    full_board = [
        {"policy": name, "expected_cost": float(i * 1000), "cvar95": float(i * 2000)}
        for i, name in enumerate(["R4", "R6", "R8", "R10", "R14"], start=1)
    ]
    rec_full = compute_r_recommendation(_cfg(lambdas=[0.0]), 1.5, full_board)
    assert rec_full is not None
    assert rec_full["full_r_sweep"] is True

    partial_board = full_board[:2]
    rec_partial = compute_r_recommendation(_cfg(lambdas=[0.0]), 1.5, partial_board)
    assert rec_partial is not None
    assert rec_partial["full_r_sweep"] is False


def test_stability_flag_uses_the_configured_threshold() -> None:
    # R* jumps from 4 (lambda=0) to 14 (lambda=10) -- a 10-unit swing, above
    # the default instability_threshold of 2.
    scoreboard = [
        {"policy": "R4", "expected_cost": 50_000.0, "cvar95": 900_000.0},
        {"policy": "R14", "expected_cost": 500_000.0, "cvar95": 100_000.0},
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[0.0, 10.0], instability_threshold=2), 1.5, scoreboard)
    assert rec is not None
    assert rec["stable"] is False

    rec_lenient = compute_r_recommendation(
        _cfg(lambdas=[0.0, 10.0], instability_threshold=20), 1.5, scoreboard
    )
    assert rec_lenient is not None
    assert rec_lenient["stable"] is True


def test_sensitivity_not_configured_returns_none() -> None:
    cfg = types.SimpleNamespace(sensitivity=None)
    scoreboard = [
        {"policy": "R6", "expected_cost": 90_000.0, "cvar95": 300_000.0},
        {"policy": "R10", "expected_cost": 120_000.0, "cvar95": 150_000.0},
    ]
    assert compute_r_recommendation(cfg, 1.5, scoreboard) is None


def test_infeasible_policies_are_excluded_from_the_argmin_and_reported() -> None:
    """WN-004, spec Sec7.5: 'the optimiser never proposes an infeasible R.'
    R4 is the cheapest policy but fails the service-level constraint -- it
    must never win the argmin, and its exclusion must be visible, not silent
    (spec Sec9.3's 'no black box' rule)."""
    scoreboard = [
        {
            "policy": "R4",
            "expected_cost": 10_000.0,
            "cvar95": 20_000.0,
            "service_level": {"service_level_met": False},
        },
        {
            "policy": "R6",
            "expected_cost": 90_000.0,
            "cvar95": 300_000.0,
            "service_level": {"service_level_met": True},
        },
        {
            "policy": "R10",
            "expected_cost": 120_000.0,
            "cvar95": 150_000.0,
            "service_level": {"service_level_met": True},
        },
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[0.0]), 1.5, scoreboard)
    assert rec is not None
    assert rec["curve"] == [{"lambda": 0.0, "recommended_r": 6}]  # not R4, despite its lower cost
    assert rec["r_values_compared"] == [6, 10]
    assert rec["excluded_infeasible_r"] == [4]


def test_service_level_absent_or_true_does_not_exclude() -> None:
    """A row with no service_level key (older jobs, before WN-004 shipped) or
    service_level_met explicitly True must be treated as feasible -- absence
    of information is not the same as failing the constraint."""
    scoreboard = [
        {"policy": "R4", "expected_cost": 100_000.0, "cvar95": 400_000.0},  # no service_level key
        {
            "policy": "R6",
            "expected_cost": 90_000.0,
            "cvar95": 300_000.0,
            "service_level": {"service_level_met": True},
        },
    ]
    rec = compute_r_recommendation(_cfg(lambdas=[0.0]), 1.5, scoreboard)
    assert rec is not None
    assert rec["r_values_compared"] == [4, 6]
    assert rec["excluded_infeasible_r"] == []

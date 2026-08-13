"""reporting/paired.py -- the paired CRN difference the CLI and the web API share.

This module exists because `compare` and the processing API must never report
different differences for the same inputs, so the tests that matter are the
ones pinning the arithmetic and the refusals, not the plumbing.
"""

from __future__ import annotations

import math

import pytest

from crewsim.reporting.paired import format_paired_diff, paired_diff


def test_mean_difference_is_b_minus_a_elementwise() -> None:
    a = [100.0, 200.0, 300.0, 400.0]
    b = [110.0, 190.0, 330.0, 380.0]
    result = paired_diff(a, b)
    # +10, -10, +30, -20 -> mean +2.5
    assert result["mean_diff"] == pytest.approx(2.5)


def test_pairing_is_elementwise_not_distributional() -> None:
    """The same two multisets, re-ordered, must give a different answer.

    If this ever passes with equal means, the pairing has been lost and the
    comparison has silently become an unpaired one -- which is exactly the
    property CRN exists to buy.
    """
    a = [100.0, 200.0, 300.0]
    paired = paired_diff(a, [110.0, 180.0, 360.0])
    shuffled = paired_diff(a, [360.0, 110.0, 180.0])
    assert paired["mean_diff"] == pytest.approx(shuffled["mean_diff"])  # means match
    # ...but the dispersion, and therefore the CI and t, do not.
    assert paired["half_width"] != pytest.approx(shuffled["half_width"])


def test_identical_vectors_give_zero_difference_and_no_significance() -> None:
    costs = [1000.0, 2000.0, 1500.0, 1800.0]
    result = paired_diff(costs, list(costs))
    assert result["mean_diff"] == pytest.approx(0.0)
    assert result["half_width"] == pytest.approx(0.0)
    # A zero-variance paired t-test is 0/0; scipy reports nan rather than a
    # spurious verdict, and we must not turn that into one either.
    assert math.isnan(result["t_stat"]) or result["t_stat"] == pytest.approx(0.0)


def test_ci_brackets_the_mean() -> None:
    a = [100.0, 120.0, 90.0, 130.0, 110.0]
    b = [150.0, 160.0, 140.0, 175.0, 155.0]
    r = paired_diff(a, b)
    assert r["ci_lower"] < r["mean_diff"] < r["ci_upper"]
    assert r["half_width"] == pytest.approx(r["ci_upper"] - r["mean_diff"])


def test_single_scenario_refuses_rather_than_reporting_nan() -> None:
    """One pair has no dispersion to estimate.

    A CI of [nan, nan] rendered into a table reads as a computed result, so
    this reports `evaluated: False` with a reason instead.
    """
    result = paired_diff([100.0], [150.0])
    assert result["evaluated"] is False
    assert result["mean_diff"] == pytest.approx(50.0)
    assert "ci_lower" not in result
    assert "2 paired scenarios" in result["reason"]


def test_mismatched_lengths_raise_rather_than_truncate() -> None:
    """Unequal vectors mean the two policies did not run the same scenario set.

    Truncating to the shorter one would silently compare scenario i of one
    policy against scenario i of a different set -- a wrong number, not a
    smaller one.
    """
    with pytest.raises(ValueError, match="same scenario set"):
        paired_diff([1.0, 2.0, 3.0], [1.0, 2.0])


def test_format_reports_the_direction_of_the_difference() -> None:
    text = format_paired_diff("R6", "R10", paired_diff([100.0, 100.0], [90.0, 80.0]))
    assert "R10 - R6" in text
    assert "-15" in text  # mean of -10 and -20, signed
    assert "95% CI" in text


def test_format_says_so_when_not_evaluated() -> None:
    text = format_paired_diff("R6", "R10", paired_diff([100.0], [150.0]))
    assert "not evaluated" in text
    assert "95% CI" not in text

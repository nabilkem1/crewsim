"""Gate V4 — cascade frequency against the historical band (S1d-04).

The design constraint on this file, learned from the defect it failed to catch:
**a hand-built `cascade_target` stand-in must match the real function's shape,
and one test must prove that it does.**

The previous version mocked `{"draft_recall": {"rate": 0.85}}` and asserted the
marginal-recall warning fired. It passed. But `data/drafts.py::score_recall`
returns `{"recall": ...}` -- there is no `rate` key -- so the production lookup
`.get("rate", 1.0)` read its own default on every real run, reported perfect
recall, and S1d-04's third acceptance criterion never once fired. Recall on the
holdout window is in fact 0.000 (0 of 2,584 known drafts found).

The test validated a copy of the mechanism. `test_the_mock_matches_the_real_
cascade_target_contract` below is what stops that recurring: it drives the real
function and asserts the keys these mocks depend on actually exist.
"""
import types

import pytest

from crewsim.gates.v4_cascade import FAIL, INCONCLUSIVE, PASS, run_v4_gate


def _cfg():
    cfg = types.SimpleNamespace()
    cfg.windows = types.SimpleNamespace()
    cfg.windows.holdout = types.SimpleNamespace(start=1000, end=2000)
    cfg.quality_gates = types.SimpleNamespace()
    cfg.quality_gates.d6_d7_join_pass = 0.8
    cfg.quality_gates.d4_link_marginal = 0.9
    return cfg


def _hist(rate=0.15, ci=(0.10, 0.20), recall=0.95, n_drafts=120):
    """A stand-in shaped like the real cascade_target -- `recall`, not `rate`.
    Pinned against the real contract by the last test in this file."""
    return {
        "rate": rate,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "n_drafts": n_drafts,
        "draft_recall": {"recall": recall, "found": 100, "true_n": 105},
    }


def _patch(monkeypatch, hist):
    monkeypatch.setattr("crewsim.gates.v4_cascade.cascade_target",
                        lambda cfg, window_name: hist)


def test_v4_cascade_gate(monkeypatch):
    _patch(monkeypatch, _hist(recall=0.85))          # below the 0.9 marginal bar
    result = run_v4_gate(_cfg(), [0.12, 0.16, 0.15], window="holdout")
    assert result["verdict"] == PASS
    assert result["pass"] is True
    assert result["recall_warning"] is True


def test_v4_cascade_gate_fail(monkeypatch):
    _patch(monkeypatch, _hist(recall=0.95))
    result = run_v4_gate(_cfg(), [0.25, 0.26], window="holdout")   # outside [0.10, 0.20]
    assert result["verdict"] == FAIL
    assert result["pass"] is False
    assert result["recall_warning"] is False


# ===================================== the defect this file failed to catch ==
def test_marginal_recall_warning_actually_fires_on_the_real_key(monkeypatch):
    """The regression test for the dead warning.

    Under the old `.get("rate", 1.0)` lookup this fails: the mock carries only
    `recall`, so the code would read its 1.0 default and report no warning.
    """
    _patch(monkeypatch, _hist(recall=0.10))
    result = run_v4_gate(_cfg(), [0.15], window="holdout")
    assert result["recall_warning"] is True
    assert result["draft_recall_rate"] == pytest.approx(0.10)


def test_an_unrecognised_recall_shape_raises_instead_of_defaulting(monkeypatch):
    """Defaulting is indistinguishable from "recall is fine", which is exactly
    how the warning stayed dead for the whole life of this gate."""
    hist = _hist()
    hist["draft_recall"] = {"rate": 0.85}      # the old, wrong shape
    _patch(monkeypatch, hist)
    with pytest.raises(KeyError, match="no 'recall' key"):
        run_v4_gate(_cfg(), [0.15], window="holdout")


def test_absent_ground_truth_is_not_an_error(monkeypatch):
    """Real data ships no _ground_truth.json, so score_recall returns None.
    That is a known state, not a marginal-recall condition."""
    hist = _hist()
    hist["draft_recall"] = None
    _patch(monkeypatch, hist)
    result = run_v4_gate(_cfg(), [0.15], window="holdout")
    assert result["recall_warning"] is False
    assert result["draft_recall_rate"] is None
    assert result["verdict"] == PASS


# ============================ a verdict requires a band worth comparing to ===
def test_zero_width_band_is_inconclusive_not_a_verdict(monkeypatch):
    """A reconstruction that found no drafts yields [0.0, 0.0]. Containment in
    a zero-width interval means only an exactly-0.000 simulated rate can pass,
    so both outcomes are artefacts of the empty band, not measurements."""
    _patch(monkeypatch, _hist(rate=0.0, ci=(0.0, 0.0), recall=0.0, n_drafts=0))
    result = run_v4_gate(_cfg(), [0.043], window="holdout")
    assert result["verdict"] == INCONCLUSIVE
    assert result["pass"] is False, "INCONCLUSIVE must never read as a pass"
    assert any("0 drafts" in b for b in result["blockers"])
    assert any("recall is 0.000" in b for b in result["blockers"])


def test_a_zero_simulated_rate_does_not_sneak_a_pass_out_of_an_empty_band(monkeypatch):
    """The failure mode before this change: sim 0.0 vs band [0.0, 0.0] reported
    PASS, and the epic recorded the gate as passing on that basis."""
    _patch(monkeypatch, _hist(rate=0.0, ci=(0.0, 0.0), recall=0.0, n_drafts=0))
    result = run_v4_gate(_cfg(), [0.0, 0.0], window="holdout")
    assert result["verdict"] == INCONCLUSIVE
    assert result["pass"] is False


def test_no_simulated_drafts_is_inconclusive(monkeypatch):
    _patch(monkeypatch, _hist())
    result = run_v4_gate(_cfg(), [], window="holdout")
    assert result["verdict"] == INCONCLUSIVE
    assert any("no simulated scenario" in b for b in result["blockers"])


# ================================== the mocks above must match reality =======
def test_the_mock_matches_the_real_cascade_target_contract():
    """Drives the REAL cascade_target and asserts the keys every mock in this
    file depends on. Without this, the mocks are free to drift from the
    function they stand in for -- which is precisely what happened."""
    from crewsim import config
    from crewsim.data.cascades import cascade_target

    hist = cascade_target(config.load(), window_name="holdout")
    for key in ("rate", "ci_low", "ci_high", "n_drafts", "draft_recall"):
        assert key in hist, f"cascade_target no longer returns {key!r}; the mocks here are stale"
    if hist["draft_recall"] is not None:
        assert "recall" in hist["draft_recall"], (
            "score_recall's key changed -- v4_cascade._recall_of and every mock "
            "in this file must be updated together"
        )

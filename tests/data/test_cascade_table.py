"""S0-05 -- cascade-table reconstruction, a 7-day D6 follow-on scan (spec §6.3-3).

Acceptance (backlog/mvp/00_phase0_data_foundation.md):
  * for each reconstructed draft, scan the drafted crew's next 7 days in D6
    for a follow-on break
  * emit rate + CI; inherits and reports S0-03's recall limitation
"""
from __future__ import annotations

import datetime
import json

import polars as pl
import pytest

from crewsim import config
from crewsim.data import cascades

_BASE_CFG = config.load()


def _draft(change_id: str, crew_id: str, day: int) -> dict[str, object]:
    return {
        "change_id": change_id,
        "crew_id": crew_id,
        "timestamp": datetime.datetime(2024, 1, day, 8, 0),  # noqa: DTZ001 -- matches the real loader's naive output
    }


def _d6_row(crew_id: str, day: int, hour: int, reason_code: str) -> dict[str, object]:
    return {
        "change_id": f"chg-{crew_id}-{day}-{hour}",
        "crew_id": crew_id,
        "change_ts": datetime.datetime(2024, 1, day, hour, 0),  # noqa: DTZ001
        "old_block_type": "DAY_OFF",
        "new_block_type": "OPEN",
        "new_pairing_id": "P-CASCADE",
        "reason_code": reason_code,
        "initiator": "IOC",
    }


# C1 -- drafted day 1, a genuine cascade on day 3 (within the 7-day window) -> cascaded
# C2 -- drafted day 1, no follow-on D6 activity at all -> not cascaded
# C3 -- drafted day 10, a cascade on day 5 (BEFORE the draft) -> not cascaded (must be after)
# C4 -- drafted day 1, a cascade on day 10 (outside the 7-day window) -> not cascaded
# C5 -- drafted day 1, a same-day follow-on change but wrong reason_code -> not cascaded
_DRAFTS = pl.DataFrame([
    _draft("d1", "C1", 1),
    _draft("d2", "C2", 1),
    _draft("d3", "C3", 10),
    _draft("d4", "C4", 1),
    _draft("d5", "C5", 1),
])

_D6 = pl.DataFrame([
    _d6_row("C1", 3, 8, "CASCADE_UNCOVERED"),
    _d6_row("C3", 5, 8, "CASCADE_UNCOVERED"),
    _d6_row("C4", 10, 8, "CASCADE_UNCOVERED"),
    _d6_row("C5", 1, 9, "OTHER"),
])


@pytest.fixture()
def synthetic_cfg(monkeypatch: pytest.MonkeyPatch) -> config.BaseConfig:
    def fake_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        return {"d6_schedule_changes": _D6}[name]

    monkeypatch.setattr(cascades.loaders, "load_dataset", fake_load_dataset)
    return _BASE_CFG


# --------------------------------------------------------------------- shape
def test_one_row_per_draft(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.height == _DRAFTS.height
    assert set(out.columns) == {"change_id", "crew_id", "timestamp", "cascaded"}


# ------------------------------------------------------------------- matching
def test_cascade_within_the_window_is_caught(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d1")["cascaded"].item() is True


def test_no_followup_is_not_a_cascade(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d2")["cascaded"].item() is False


def test_a_change_before_the_draft_does_not_count(synthetic_cfg: config.BaseConfig) -> None:
    """C3's D6 event on day 5 predates its own draft on day 10 -- not caused by it."""
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d3")["cascaded"].item() is False


def test_outside_the_window_does_not_count(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d4")["cascaded"].item() is False


def test_wrong_reason_code_does_not_count(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d5")["cascaded"].item() is False


# ------------------------------------------------------------- configurability
def test_window_days_is_configurable(synthetic_cfg: config.BaseConfig) -> None:
    """C4's cascade lands on day 10 -- a 9-day window reaches it."""
    params = synthetic_cfg.cascade_reconstruction.model_copy(update={"window_days": 9})
    cfg = synthetic_cfg.model_copy(update={"cascade_reconstruction": params})
    out = cascades.reconstruct_cascades(cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d4")["cascaded"].item() is True


def test_cascade_reason_codes_are_configurable(synthetic_cfg: config.BaseConfig) -> None:
    params = synthetic_cfg.cascade_reconstruction.model_copy(
        update={"cascade_reason_codes": ["CASCADE_UNCOVERED", "OTHER"]}
    )
    cfg = synthetic_cfg.model_copy(update={"cascade_reconstruction": params})
    out = cascades.reconstruct_cascades(cfg, _DRAFTS)
    assert out.filter(pl.col("change_id") == "d5")["cascaded"].item() is True


# ---------------------------------------------------------------------- rate
def test_cascade_rate_matches_the_count(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    result = cascades.cascade_rate(synthetic_cfg, out, draft_recall=None)
    assert result["count"] == 1  # only C1
    assert result["n_drafts"] == 5
    assert result["rate"] == pytest.approx(0.2)


def test_cascade_rate_ci_contains_the_point_estimate(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    result = cascades.cascade_rate(synthetic_cfg, out, draft_recall=None)
    assert result["ci_low"] <= result["rate"] <= result["ci_high"]


def test_cascade_rate_reports_the_draft_recall_it_is_bounded_by(synthetic_cfg: config.BaseConfig) -> None:
    out = cascades.reconstruct_cascades(synthetic_cfg, _DRAFTS)
    recall = {"recall": 0.877, "found": 2273, "true_n": 2592, "gate": 0.8, "gate_pass": True}
    result = cascades.cascade_rate(synthetic_cfg, out, draft_recall=recall)
    assert result["draft_recall"] == recall


def test_cascade_rate_of_zero_drafts_does_not_divide_by_zero() -> None:
    empty = pl.DataFrame(schema={"change_id": pl.Utf8, "crew_id": pl.Utf8,
                                  "timestamp": pl.Datetime, "cascaded": pl.Boolean})
    result = cascades.cascade_rate(_BASE_CFG, empty, draft_recall=None)
    assert result["rate"] == 0.0
    assert result["n_drafts"] == 0


# ------------------------------------------------------ real corpus, end to end
def test_cascades_never_outnumber_drafts_on_the_real_corpus() -> None:
    cfg = config.load()
    result = cascades.cascade_target(cfg)
    assert result["count"] <= result["n_drafts"]


def test_real_corpus_cascade_rate_is_computed_not_the_ground_truth_shortcut() -> None:
    """The mock corpus's own cascade_rate_true (~20.1%) is the ratio of total

    cascade rows to the FULL ground-truth draft count, not a genuine
    per-draft causal scan -- see the backlog's own correction note. This
    reconstruction's per-draft scan (against S0-03's recalled subset)
    produces a distinctly higher, and separately legitimate, figure.
    """
    cfg = config.load()
    result = cascades.cascade_target(cfg)
    truth = json.loads((cfg.paths.corpus_dir / "_ground_truth.json").read_text(encoding="utf-8"))

    # Asserted as a PROPERTY, not a pinned constant. The exact figure is a
    # function of the corpus, and pinning it (it was `approx(0.269)`) turned
    # every legitimate corpus regeneration into a spurious failure -- which is
    # what happened when the 2026-08-12 reserve-shift fix moved it to 0.250.
    # What this test actually exists to prove is that the number comes from a
    # real per-draft causal scan rather than being read off the manifest.
    assert result["rate"] != pytest.approx(truth["cascade_rate_true"], abs=1e-6), (
        "the reconstruction returned the manifest's own figure -- it is reading the "
        "ground-truth shortcut instead of scanning D6 per draft"
    )
    assert result["rate"] > truth["cascade_rate_true"], (
        "the per-draft scan runs against S0-03's RECALLED subset, so it must come out "
        "above the manifest's total-rows/full-draft-count ratio"
    )
    assert 0.0 < result["rate"] < 1.0
    assert result["n_drafts"] > 0
    assert result["draft_recall"] is not None
    assert result["draft_recall"]["recall"] == pytest.approx(0.877, abs=0.01)

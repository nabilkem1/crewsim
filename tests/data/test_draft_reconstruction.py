"""S0-03 -- draft-event reconstruction from D6 x D7 (spec §6.3-1).

Acceptance (backlog/mvp/00_phase0_data_foundation.md):
  * the join is configurable: premium pay codes, short-notice reason codes,
    and the initiator filter all come from config, never a literal
  * emits the draft-event table: timestamp, crew, prior status, covering pairing
  * reports recall against a labelled sample -- on the mock corpus, against
    `_ground_truth.json`
  * a NULL initiator is never silently dropped
"""
from __future__ import annotations

import datetime
import pathlib

import polars as pl
import pytest

from crewsim import config
from crewsim.data import drafts

_BASE_CFG = config.load()


def _row(
    change_id: str, crew_id: str, reason_code: str, initiator: str | None,
    pairing_id: str, old_block_type: str = "DAY_OFF", new_block_type: str = "PAIRING",
) -> dict[str, object]:
    return {
        "change_id": change_id,
        "crew_id": crew_id,
        "change_ts": datetime.datetime(2024, 1, int(change_id[-1]), 8, 0),  # noqa: DTZ001 -- naive, matching the real loader's output (local time, no tz)
        "old_block_type": old_block_type,
        "new_block_type": new_block_type,
        "new_pairing_id": pairing_id,
        "reason_code": reason_code,
        "initiator": initiator,
    }


# One row per behaviour this reconstruction has to get right:
#   C1 -- ordinary short-notice draft, IOC-initiated -> counted
#   C2 -- short-notice draft, NULL initiator (older record) -> counted, not dropped
#   C3 -- short-notice draft, initiator not in the default filter -> excluded
#   C4 -- reason_code not short-notice -> excluded
#   C5 -- short-notice, IOC, but no matching D7 premium -> excluded
#   C6 -- short-notice, IOC, premium paid under a non-default pay code -> excluded by default
#   C7 -- a non-default reason_code, premium paid -> excluded by default
#   C8 -- short-notice, IOC, premium paid, but never placed onto a pairing
#         (new_block_type=OPEN -- the trip became uncovered, not a draft-in) -> excluded
_D6 = pl.DataFrame([
    _row("chg1", "C1", "SHORT_NOTICE_COVER", "IOC", "P1"),
    _row("chg2", "C2", "SHORT_NOTICE_COVER", None, "P2", old_block_type="PAIRING"),
    _row("chg3", "C3", "SHORT_NOTICE_COVER", "PLANNER", "P3"),
    _row("chg4", "C4", "CASCADE_UNCOVERED", "IOC", "P4"),
    _row("chg5", "C5", "SHORT_NOTICE_COVER", "IOC", "P5"),
    _row("chg6", "C6", "SHORT_NOTICE_COVER", "IOC", "P6"),
    _row("chg7", "C7", "PLANNED_CHANGE", "IOC", "P7"),
    _row("chg8", "C8", "SHORT_NOTICE_COVER", "IOC", "P8", new_block_type="OPEN"),
])

_D7 = pl.DataFrame({
    "crew_id": ["C1", "C2", "C3", "C4", "C6", "C7", "C8"],
    "pay_period": ["2024-01"] * 7,
    "pay_code": ["DRAFT_PREM", "DRAFT_PREM", "DRAFT_PREM", "DRAFT_PREM", "OTHER_PREM", "DRAFT_PREM", "DRAFT_PREM"],
    "amount_cad": [500.0] * 7,
    "duty_date": [datetime.date(2024, 1, 1)] * 7,
    "linked_pairing_id": ["P1", "P2", "P3", "P4", "P6", "P7", "P8"],
    # C5 deliberately has no D7 row at all.
})


@pytest.fixture()
def synthetic_cfg(monkeypatch: pytest.MonkeyPatch) -> config.BaseConfig:
    def fake_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        return {"d6_schedule_changes": _D6, "d7_pay_register": _D7}[name]

    monkeypatch.setattr(drafts.loaders, "load_dataset", fake_load_dataset)
    return _BASE_CFG


# --------------------------------------------------------------------- shape
def test_draft_event_table_has_the_required_columns(synthetic_cfg: config.BaseConfig) -> None:
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert set(df.columns) == {
        "change_id", "crew_id", "timestamp", "prior_status", "covering_pairing_id", "initiator",
    }


def test_default_config_finds_exactly_the_two_genuine_drafts(synthetic_cfg: config.BaseConfig) -> None:
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert set(df["crew_id"].to_list()) == {"C1", "C2"}


# ------------------------------------------------------------- null initiator
def test_null_initiator_is_not_silently_dropped(synthetic_cfg: config.BaseConfig) -> None:
    """C2 has no initiator recorded (an older record) but otherwise qualifies."""
    df = drafts.reconstruct_drafts(synthetic_cfg)
    c2 = df.filter(pl.col("crew_id") == "C2")
    assert c2.height == 1
    assert c2["initiator"].to_list() == [None]


# --------------------------------------------------------- new_block_type
def test_change_that_never_placed_crew_on_a_pairing_is_excluded(synthetic_cfg: config.BaseConfig) -> None:
    """C8 looks urgent and was paid a premium, but new_block_type=OPEN --

    §6.3-1 step 3 requires the crew to have actually been placed on a
    flight. Not a config parameter: this is part of what a draft *is*.
    """
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert "C8" not in df["crew_id"].to_list()


# -------------------------------------------------------- initiator filter
def test_initiator_not_in_the_filter_is_excluded(synthetic_cfg: config.BaseConfig) -> None:
    """C3 was PLANNER-initiated; the default filter only accepts IOC."""
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert "C3" not in df["crew_id"].to_list()


def test_initiator_filter_is_configurable(synthetic_cfg: config.BaseConfig) -> None:
    params = synthetic_cfg.draft_reconstruction.model_copy(
        update={"initiator_filter": ["IOC", "PLANNER"]}
    )
    cfg = synthetic_cfg.model_copy(update={"draft_reconstruction": params})
    df = drafts.reconstruct_drafts(cfg)
    assert "C3" in df["crew_id"].to_list()


# --------------------------------------------------- short-notice reason codes
def test_reason_code_not_configured_as_short_notice_is_excluded(synthetic_cfg: config.BaseConfig) -> None:
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert "C4" not in df["crew_id"].to_list()
    assert "C7" not in df["crew_id"].to_list()


def test_short_notice_reason_codes_are_configurable(synthetic_cfg: config.BaseConfig) -> None:
    params = synthetic_cfg.draft_reconstruction.model_copy(
        update={"short_notice_reason_codes": ["SHORT_NOTICE_COVER", "PLANNED_CHANGE"]}
    )
    cfg = synthetic_cfg.model_copy(update={"draft_reconstruction": params})
    df = drafts.reconstruct_drafts(cfg)
    assert "C7" in df["crew_id"].to_list()


# --------------------------------------------------------- premium pay codes
def test_pay_code_not_configured_as_a_premium_is_excluded(synthetic_cfg: config.BaseConfig) -> None:
    """C6's premium was paid under OTHER_PREM, not the default DRAFT_PREM."""
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert "C6" not in df["crew_id"].to_list()


def test_premium_pay_codes_are_configurable(synthetic_cfg: config.BaseConfig) -> None:
    params = synthetic_cfg.draft_reconstruction.model_copy(
        update={"premium_pay_codes": ["DRAFT_PREM", "OTHER_PREM"]}
    )
    cfg = synthetic_cfg.model_copy(update={"draft_reconstruction": params})
    df = drafts.reconstruct_drafts(cfg)
    assert "C6" in df["crew_id"].to_list()


def test_no_matching_premium_row_is_excluded(synthetic_cfg: config.BaseConfig) -> None:
    """C5 has a qualifying D6 row but D7 never paid a premium for it."""
    df = drafts.reconstruct_drafts(synthetic_cfg)
    assert "C5" not in df["crew_id"].to_list()


def test_premium_split_across_two_pay_periods_does_not_duplicate_the_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single draft whose premium was paid across a pay-period boundary

    must still be counted once, not once per matching D7 row -- the join's
    `premium.unique()` dedup exists exactly to prevent this fan-out.
    """
    d6 = pl.DataFrame([_row("chg1", "C1", "SHORT_NOTICE_COVER", "IOC", "P1")])
    d7 = pl.DataFrame({
        "crew_id": ["C1", "C1"],
        "pay_period": ["2023-12", "2024-01"],
        "pay_code": ["DRAFT_PREM", "DRAFT_PREM"],
        "amount_cad": [250.0, 250.0],
        "duty_date": [datetime.date(2023, 12, 31), datetime.date(2024, 1, 1)],
        "linked_pairing_id": ["P1", "P1"],
    })

    def fake_load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
        return {"d6_schedule_changes": d6, "d7_pay_register": d7}[name]

    monkeypatch.setattr(drafts.loaders, "load_dataset", fake_load_dataset)
    df = drafts.reconstruct_drafts(_BASE_CFG)
    assert df.height == 1


# ---------------------------------------------------------- prior status / tiers
def test_prior_status_distribution_sums_to_one(synthetic_cfg: config.BaseConfig) -> None:
    df = drafts.reconstruct_drafts(synthetic_cfg)
    dist = drafts.prior_status_distribution(df)
    assert dist.keys() == {"DAY_OFF", "PAIRING"}
    assert sum(dist.values()) == pytest.approx(1.0)


def test_prior_status_distribution_of_empty_table_is_empty() -> None:
    empty = pl.DataFrame(
        schema={"crew_id": pl.Utf8, "prior_status": pl.Utf8},
    )
    assert drafts.prior_status_distribution(empty) == {}


# --------------------------------------------------------------- recall scoring
def test_score_recall_is_none_without_ground_truth(
    synthetic_cfg: config.BaseConfig, tmp_path: pathlib.Path
) -> None:
    new_paths = synthetic_cfg.paths.model_copy(update={"corpus_dir": tmp_path})
    cfg = synthetic_cfg.model_copy(update={"paths": new_paths})
    df = drafts.reconstruct_drafts(cfg)
    assert drafts.score_recall(cfg, df) is None


def test_score_recall_reuses_the_section_6_2_join_recovery_gate(synthetic_cfg: config.BaseConfig) -> None:
    """§6.3-1 explicitly names this the *same* 80% Reality Check gate as §6.2."""
    df = drafts.reconstruct_drafts(synthetic_cfg)
    result = drafts.score_recall(synthetic_cfg, df)
    assert result is not None
    assert result["gate"] == synthetic_cfg.quality_gates.d6_d7_join_pass


# ------------------------------------------------------ real corpus, real ground truth
def test_recall_against_the_real_mock_corpus_clears_the_gate() -> None:
    """Matches the backlog's own documented figure (87.7% of 2,592).

    On *this* corpus every D7 `DRAFT_PREM` row's (crew, pairing) already
    corresponds to a D6 `SHORT_NOTICE_COVER` row, and initiator is only ever
    `IOC` or NULL (which always passes) -- so this number is fully
    determined by the D7 premium join alone, not by the short-notice or
    initiator logic. Those two are exercised by the synthetic-config tests
    above (C3/C4/C6/C7); this test only proves the premium join and the
    ground-truth wiring are correct end to end.
    """
    cfg = config.load()
    df = drafts.reconstruct_drafts(cfg)
    result = drafts.score_recall(cfg, df)
    assert result is not None
    assert result["gate_pass"], f"recall {result['recall']:.1%} below gate {result['gate']:.0%}"
    assert result["recall"] == pytest.approx(0.877, abs=0.01)


def test_draft_table_is_sorted_and_non_empty_on_the_real_corpus() -> None:
    cfg = config.load()
    df = drafts.reconstruct_drafts(cfg)
    assert df.height > 0
    assert df["timestamp"].is_sorted()
    dist = drafts.prior_status_distribution(df)
    assert "DAY_OFF" in dist

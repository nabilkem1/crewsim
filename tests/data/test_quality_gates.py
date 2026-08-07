"""Tests for data quality gates (S0-02)."""
from typing import Any

import polars as pl
from pytest import CaptureFixture, MonkeyPatch

from crewsim import config
from crewsim.data import quality


def test_quality_report(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    # We mock loaders.load_dataset to return a small set of controlled DataFrames
    
    def dummy_load_dataset(cfg: dict[str, Any], name: str) -> pl.DataFrame:
        if name == "d1_crew_master":
            return pl.DataFrame({"crew_id": ["C1", "C2"], "employment_status": ["ACTIVE", "TERMINATED"]})
        elif name == "d2_rosters":
            return pl.DataFrame({
                "crew_id": ["C1", "C2"], "pairing_id": ["P1", None],
                "block_type": ["PAIRING", "VACATION"], "reserve_call_type": ["SC", None]
            })
        elif name == "d3_pairings":
            return pl.DataFrame({"pairing_id": ["P1", "P2"]})
        elif name == "d4_absences":
            return pl.DataFrame({"crew_id": ["C1"], "affected_pairing_id": ["P1"]})
        elif name == "d5_reserve_callouts":
            return pl.DataFrame({"crew_id": ["C1"], "assigned_pairing_id": ["P1"]})
        elif name == "d6_schedule_changes":
            return pl.DataFrame({
                "crew_id": ["C1", "C1"], "new_pairing_id": ["P1", "P2"],
                "old_block_type": ["PAIRING", "DAY_OFF"], "new_block_type": ["DAY_OFF", "PAIRING"],
                "reason_code": ["SHORT_NOTICE_COVER", "OTHER"]
            })
        elif name == "d7_pay_register":
            return pl.DataFrame({
                "crew_id": ["C1"], "linked_pairing_id": ["P1"], "pay_code": ["DRAFT_PREM"]
            })
        elif name == "d9_station_days":
            return pl.DataFrame({"station": ["YUL", "YUL"], "date": ["2023-01-01", "2023-01-02"]})
        elif name == "d10_positioning_invoices":
            return pl.DataFrame({"crew_id": ["C1"], "pairing_id": ["P1"]})
        elif name == "d11_training_sessions":
            return pl.DataFrame({"crew_id": ["C1"]})
        raise FileNotFoundError(f"{name} not found")

    monkeypatch.setattr(quality.loaders, "load_dataset", dummy_load_dataset)
    
    res = quality.run_quality_report(config.load())
    assert res == 0, "Expected all tests to pass on valid data"


def test_quality_report_fails(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    def dummy_load_dataset_fail(cfg: dict[str, Any], name: str) -> pl.DataFrame:
        if name == "d1_crew_master":
            return pl.DataFrame({"crew_id": ["C1"], "employment_status": ["INVALID_STATUS"]})
        elif name == "d2_rosters":
            return pl.DataFrame({
                "crew_id": ["C_INVALID"], "pairing_id": ["P_INVALID"],
                "block_type": ["INVALID_BLOCK"], "reserve_call_type": ["INVALID_CALL"]
            })
        elif name == "d3_pairings":
            return pl.DataFrame({"pairing_id": ["P1"]})
        elif name == "d4_absences":
            # 0% link rate
            return pl.DataFrame({"crew_id": ["C1"], "affected_pairing_id": ["P_INVALID"]})
        elif name == "d5_reserve_callouts":
            return pl.DataFrame({"crew_id": ["C1"], "assigned_pairing_id": ["P1"]})
        elif name == "d6_schedule_changes":
            # 0% join recovery
            return pl.DataFrame({
                "crew_id": ["C1"], "new_pairing_id": ["P1"],
                "old_block_type": ["DAY_OFF"], "new_block_type": ["PAIRING"],
                "reason_code": ["SHORT_NOTICE_COVER"]
            })
        elif name == "d7_pay_register":
            return pl.DataFrame({
                "crew_id": ["C1"], "linked_pairing_id": ["P2"], "pay_code": ["DRAFT_PREM"]
            })
        elif name == "d9_station_days":
            return pl.DataFrame({"station": ["YUL"], "date": ["2023-01-01"]})
        elif name == "d10_positioning_invoices":
            return pl.DataFrame({"crew_id": ["C1"], "pairing_id": ["P1"]})
        elif name == "d11_training_sessions":
            return pl.DataFrame({"crew_id": ["C1"]})
        raise FileNotFoundError(f"{name} not found")
        
    monkeypatch.setattr(quality.loaders, "load_dataset", dummy_load_dataset_fail)
    
    res = quality.run_quality_report(config.load())
    assert res == 1, "Expected test to fail on invalid data"
    
    out, _err = capsys.readouterr()
    assert "D4 Linkage (Sick calls linked to a valid pairing): 0.0% [FAIL]" in out
    assert "D6/D7 Join Recovery (Draft events backed by payroll receipts): 0.0% [FAIL]" in out
    assert "D2 pairing_id orphans: 100.00% (1 rows) [FAIL]" in out
    assert "D2 crew_id orphans: 100.00% (1 rows) [FAIL]" in out
    assert "invalid values" in out

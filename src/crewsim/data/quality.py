"""Data quality gates (S0-02, Spec Sec 6.2)."""
from __future__ import annotations

import polars as pl

from .. import config
from . import loaders

# Domains from spec
VALID_BLOCK_TYPES = {
    "PAIRING", "RESERVE", "DAY_OFF", "VACATION", "TRAINING",
    "SIMULATOR", "REST", "DEADHEAD", "DRAFTED_DUTY", "OPEN"
}
VALID_EMPLOYMENT_STATUS = {
    "ACTIVE", "INACTIVE", "TERMINATED", "LONG_TERM_ABSENCE",
    "MANAGEMENT_OR_INSTRUCTOR", "INITIAL_TRAINING", "FLEET_TRANSITION"
}
VALID_RESERVE_CALL_TYPES = {"SC", "LC"}


def run_quality_report(cfg: config.BaseConfig) -> int:
    """Run all quality gates and print the report. Returns 0 if pass, 1 if fail."""
    print("Running Data Quality Gates (§6.2)...\n")
    gates = cfg.quality_gates

    # Load needed datasets
    try:
        d1 = loaders.load_dataset(cfg, "d1_crew_master")
        d2 = loaders.load_dataset(cfg, "d2_rosters")
        d3 = loaders.load_dataset(cfg, "d3_pairings")
        d4 = loaders.load_dataset(cfg, "d4_absences")
        d5 = loaders.load_dataset(cfg, "d5_reserve_callouts")
        d6 = loaders.load_dataset(cfg, "d6_schedule_changes")
        d7 = loaders.load_dataset(cfg, "d7_pay_register")
        d9 = loaders.load_dataset(cfg, "d9_station_days")
        d10 = loaders.load_dataset(cfg, "d10_positioning_invoices")
        d11 = loaders.load_dataset(cfg, "d11_training_sessions")
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"Failed to load datasets: {exc}")
        return 1

    fails = 0

    # 1. D4 Linkage (Gate: 95%)
    # Percentage of D4 rows with an affected_pairing_id that resolves to D3.
    d4_total = d4.height
    if d4_total == 0:
        d4_link_rate = 1.0
    else:
        d4_linked = d4.filter(pl.col("affected_pairing_id").is_not_null() & (pl.col("affected_pairing_id") != ""))
        d4_valid_links = d4_linked.join(d3, left_on="affected_pairing_id", right_on="pairing_id", how="inner").height
        d4_link_rate = d4_valid_links / d4_total

    if d4_link_rate >= gates.d4_link_pass:
        d4_status = "PASS"
    elif d4_link_rate >= gates.d4_link_marginal:
        d4_status = "MARGINAL"
    else:
        d4_status = "FAIL"

    if d4_status == "FAIL": fails += 1
    print(f"D4 Linkage (Sick calls linked to a valid pairing): {d4_link_rate:.1%} [{d4_status}] (Threshold: {gates.d4_link_pass:.0%})")

    # 2. D6/D7 Join Recovery (Gate: 80%)
    # How many D6 short-notice covers have a matching D7 draft premium?
    d6_drafts = d6.filter(pl.col("reason_code") == "SHORT_NOTICE_COVER")
    d6_drafts_total = d6_drafts.height
    if d6_drafts_total == 0:
        d6_d7_rate = 1.0
    else:
        d7_prem = d7.filter(pl.col("pay_code") == "DRAFT_PREM")
        joined = d6_drafts.join(
            d7_prem,
            left_on=["crew_id", "new_pairing_id"],
            right_on=["crew_id", "linked_pairing_id"],
            how="inner"
        )
        d6_d7_rate = joined.height / d6_drafts_total
    
    d6_d7_status = "PASS" if d6_d7_rate >= gates.d6_d7_join_pass else "FAIL"
    if d6_d7_status == "FAIL": fails += 1
    print(f"D6/D7 Join Recovery (Draft events backed by payroll receipts): {d6_d7_rate:.1%} [{d6_d7_status}] (Threshold: {gates.d6_d7_join_pass:.0%})")

    # 3. D9 Completeness (Gate: 98%)
    # unique dates * unique stations vs actual rows
    n_dates = d9["date"].n_unique()
    n_stations = d9["station"].n_unique()
    expected_d9 = n_dates * n_stations
    d9_rate = d9.height / expected_d9 if expected_d9 > 0 else 1.0
    
    d9_status = "PASS" if d9_rate >= gates.d9_completeness_pass else "FAIL"
    if d9_status == "FAIL": fails += 1
    print(f"D9 Completeness (Daily weather/IROPS logs per station): {d9_rate:.1%} [{d9_status}] (Threshold: {gates.d9_completeness_pass:.0%})")

    print("\n--- Referential Integrity ---")
    # pairing_id -> D3
    d3_pairings = set(d3["pairing_id"].to_list())
    for ds_name, df, col in [
        ("D2", d2, "pairing_id"), ("D4", d4, "affected_pairing_id"), 
        ("D5", d5, "assigned_pairing_id"), ("D6", d6, "new_pairing_id"), 
        ("D7", d7, "linked_pairing_id"), ("D10", d10, "pairing_id")
    ]:
        # filter out nulls/empties
        df_valid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != ""))
        if df_valid.height == 0:
            continue
        orphans = df_valid.filter(~pl.col(col).is_in(list(d3_pairings))).height
        orphan_rate = orphans / df_valid.height
        status = "PASS" if orphan_rate == 0 else "FAIL"
        if status == "FAIL": fails += 1
        print(f"{ds_name} pairing_id orphans: {orphan_rate:.2%} ({orphans} rows) [{status}]")

    # crew_id -> D1
    d1_crews = set(d1["crew_id"].to_list())
    for ds_name, df in [
        ("D2", d2), ("D4", d4), ("D5", d5), ("D6", d6), 
        ("D7", d7), ("D10", d10), ("D11", d11)
    ]:
        df_valid = df.filter(pl.col("crew_id").is_not_null() & (pl.col("crew_id") != ""))
        if df_valid.height == 0:
            continue
        orphans = df_valid.filter(~pl.col("crew_id").is_in(list(d1_crews))).height
        orphan_rate = orphans / df_valid.height
        status = "PASS" if orphan_rate == 0 else "FAIL"
        if status == "FAIL": fails += 1
        print(f"{ds_name} crew_id orphans: {orphan_rate:.2%} ({orphans} rows) [{status}]")

    print("\n--- Domain Validity ---")
    # block_type in D2, D6
    for ds_name, df, col in [("D2", d2, "block_type"), ("D6", d6, "old_block_type"), ("D6", d6, "new_block_type")]:
        invalid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != "") & ~pl.col(col).is_in(list(VALID_BLOCK_TYPES)))
        if invalid.height > 0:
            counts = invalid.group_by(col).len().to_dicts()
            print(f"{ds_name} {col} invalid values: {counts} [FAIL]")
            fails += 1
        else:
            print(f"{ds_name} {col}: 0 invalid values [PASS]")

    # employment_status in D1
    invalid_emp = d1.filter(pl.col("employment_status").is_not_null() & (pl.col("employment_status") != "") & ~pl.col("employment_status").is_in(list(VALID_EMPLOYMENT_STATUS)))
    if invalid_emp.height > 0:
        counts = invalid_emp.group_by("employment_status").len().to_dicts()
        print(f"D1 employment_status invalid values: {counts} [FAIL]")
        fails += 1
    else:
        print("D1 employment_status: 0 invalid values [PASS]")

    # reserve_call_type in D2
    invalid_res = d2.filter(pl.col("reserve_call_type").is_not_null() & (pl.col("reserve_call_type") != "") & ~pl.col("reserve_call_type").is_in(list(VALID_RESERVE_CALL_TYPES)))
    if invalid_res.height > 0:
        counts = invalid_res.group_by("reserve_call_type").len().to_dicts()
        print(f"D2 reserve_call_type invalid values: {counts} [FAIL]")
        fails += 1
    else:
        print("D2 reserve_call_type: 0 invalid values [PASS]")

    print(f"\nQuality report finished with {fails} failures.")
    return 1 if fails > 0 else 0

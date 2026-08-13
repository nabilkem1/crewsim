"""Data quality gates (S0-02, Spec Sec 6.2)."""
from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class QualityCheckResult:
    name: str
    status: str  # "PASS" | "MARGINAL" | "FAIL"
    details: str


def d9_completeness(d9: pl.DataFrame) -> float:
    """Observed station-days / expected station-days, in [0, 1].

    AUD-28b: expected days are counted per station as that station's OWN
    continuous first..last span, summed. Not the count of distinct observed
    dates -- that let a wholly missing date shrink the denominator and hide
    itself. And not the global span x every station -- that would charge a
    seasonal outstation for months it never operated, failing the gate on a
    corpus with no actual missing station-day (and since AUD-13 that gate
    failure is a non-zero exit, so the overcount would block the CLI).
    Interior gaps inside a station's own reporting period are what this
    catches.

    Stated limit, not solved here: a station absent from D9 entirely, or one
    missing its leading/trailing days, is still invisible -- only a network
    station roster carrying each station's expected operating period could
    see those.
    """
    if d9.height == 0:
        return 1.0
    per_station = (
        d9.with_columns(pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d").alias("_d"))
        .group_by("station")
        .agg(((pl.col("_d").max() - pl.col("_d").min()).dt.total_days() + 1).alias("span_days"))
    )
    expected = int(per_station["span_days"].sum() or 0)
    return d9.height / expected if expected > 0 else 1.0


def compute_quality_checks(cfg: config.BaseConfig) -> list[QualityCheckResult]:
    """Runs every Sec6.2 quality gate against the real corpus and returns the
    check results as data -- the one real computation shared by the CLI
    (run_quality_report, printing) and the API (routers/data.py, JSON), so a
    regression here fails both instead of one silently drifting from the
    other."""
    gates = cfg.quality_gates

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

    checks: list[QualityCheckResult] = []

    # 1. D4 Linkage (Gate: 95%)
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
    checks.append(QualityCheckResult(
        "D4 Linkage (sick calls linked to a valid pairing)", d4_status,
        f"{d4_link_rate:.1%} linked (threshold {gates.d4_link_pass:.0%})",
    ))

    # 2. D6/D7 Join Recovery (Gate: 80%)
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
    checks.append(QualityCheckResult(
        "D6/D7 Join Recovery (draft events backed by payroll receipts)", d6_d7_status,
        f"{d6_d7_rate:.1%} recovered (threshold {gates.d6_d7_join_pass:.0%})",
    ))

    # 3. D9 Completeness (Gate: 98%)
    d9_rate = d9_completeness(d9)
    d9_status = "PASS" if d9_rate >= gates.d9_completeness_pass else "FAIL"
    checks.append(QualityCheckResult(
        "D9 Completeness (daily weather/IROPS logs per station)", d9_status,
        f"{d9_rate:.1%} complete (threshold {gates.d9_completeness_pass:.0%})",
    ))

    # Referential integrity: pairing_id -> D3
    d3_pairings = set(d3["pairing_id"].to_list())
    for ds_name, df, col in [
        ("D2", d2, "pairing_id"), ("D4", d4, "affected_pairing_id"),
        ("D5", d5, "assigned_pairing_id"), ("D6", d6, "new_pairing_id"),
        ("D7", d7, "linked_pairing_id"), ("D10", d10, "pairing_id")
    ]:
        df_valid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != ""))
        if df_valid.height == 0:
            continue
        orphans = df_valid.filter(~pl.col(col).is_in(list(d3_pairings))).height
        orphan_rate = orphans / df_valid.height
        status = "PASS" if orphan_rate == 0 else "FAIL"
        checks.append(QualityCheckResult(
            f"{ds_name} pairing_id referential integrity", status,
            f"{orphan_rate:.2%} orphaned ({orphans} of {df_valid.height} rows)",
        ))

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
        checks.append(QualityCheckResult(
            f"{ds_name} crew_id referential integrity", status,
            f"{orphan_rate:.2%} orphaned ({orphans} of {df_valid.height} rows)",
        ))

    # Domain validity: block_type in D2, D6
    for ds_name, df, col in [("D2", d2, "block_type"), ("D6", d6, "old_block_type"), ("D6", d6, "new_block_type")]:
        invalid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != "") & ~pl.col(col).is_in(list(VALID_BLOCK_TYPES)))
        if invalid.height > 0:
            counts = invalid.group_by(col).len().to_dicts()
            checks.append(QualityCheckResult(f"{ds_name} {col} domain validity", "FAIL", f"invalid values: {counts}"))
        else:
            checks.append(QualityCheckResult(f"{ds_name} {col} domain validity", "PASS", "0 invalid values"))

    # employment_status in D1
    invalid_emp = d1.filter(pl.col("employment_status").is_not_null() & (pl.col("employment_status") != "") & ~pl.col("employment_status").is_in(list(VALID_EMPLOYMENT_STATUS)))
    if invalid_emp.height > 0:
        counts = invalid_emp.group_by("employment_status").len().to_dicts()
        checks.append(QualityCheckResult("D1 employment_status domain validity", "FAIL", f"invalid values: {counts}"))
    else:
        checks.append(QualityCheckResult("D1 employment_status domain validity", "PASS", "0 invalid values"))

    # reserve_call_type in D2
    invalid_res = d2.filter(pl.col("reserve_call_type").is_not_null() & (pl.col("reserve_call_type") != "") & ~pl.col("reserve_call_type").is_in(list(VALID_RESERVE_CALL_TYPES)))
    if invalid_res.height > 0:
        counts = invalid_res.group_by("reserve_call_type").len().to_dicts()
        checks.append(QualityCheckResult("D2 reserve_call_type domain validity", "FAIL", f"invalid values: {counts}"))
    else:
        checks.append(QualityCheckResult("D2 reserve_call_type domain validity", "PASS", "0 invalid values"))

    return checks


def quality_score(checks: list[QualityCheckResult]) -> float:
    """Overall score /100: the mean of each check's status weighted PASS=1,
    MARGINAL=0.5, FAIL=0 -- a presentation aggregate of the real per-check
    verdicts above, not a separate business figure."""
    if not checks:
        return 0.0
    weights = {"PASS": 1.0, "MARGINAL": 0.5, "FAIL": 0.0}
    return round(100 * sum(weights[c.status] for c in checks) / len(checks), 1)


def run_quality_report(cfg: config.BaseConfig, allow_marginal: bool = False) -> int:
    """CLI entry point (`crewsim data quality-report`): run all quality gates
    and print the report.

    AUD-13: a MARGINAL result on a spec-cited gate is BELOW that gate's §6.2
    "minimum passing grade" (the 90% marginal floor is an implementation
    judgment, flagged not-spec-cited in base.yaml), and §6.2 calls these
    blocking gates. Exit is therefore non-zero for MARGINAL too, unless the
    caller explicitly accepts it with `allow_marginal` -- an explicit,
    visible decision instead of a green light on a sub-threshold corpus.
    Returns 0 only when every gate PASSes (or marginals are explicitly
    allowed and nothing FAILs).
    """
    print("Running Data Quality Gates (Sec6.2)...\n")
    try:
        checks = compute_quality_checks(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"Failed to load datasets: {exc}")
        return 1

    fails = 0
    marginals = 0
    for check in checks:
        if check.status == "FAIL":
            fails += 1
        elif check.status == "MARGINAL":
            marginals += 1
        print(f"{check.name}: {check.details} [{check.status}]")

    print(f"\nOverall score: {quality_score(checks)}/100")
    print(f"Quality report finished with {fails} failure(s), {marginals} marginal.")
    if fails > 0:
        return 1
    if marginals > 0 and not allow_marginal:
        print("MARGINAL gates are below their Sec6.2 passing grade -- exiting non-zero. "
              "Pass --allow-marginal to accept them explicitly.")
        return 1
    return 0

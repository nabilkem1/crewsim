"""Data quality gates (S0-02, Spec Sec 6.2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from .. import config
from . import clean, ids, loaders

# Domains from spec
VALID_BLOCK_TYPES = {
    "PAIRING", "RESERVE", "DAY_OFF", "VACATION", "TRAINING",
    "SIMULATOR", "REST", "DEADHEAD", "DRAFTED_DUTY", "OPEN",
    # The engine's own BlockType for "unavailable, not duty" (engine/state.py).
    "ABSENCE",
}
VALID_EMPLOYMENT_STATUS = {
    "ACTIVE", "INACTIVE", "TERMINATED", "LONG_TERM_ABSENCE",
    "MANAGEMENT_OR_INSTRUCTOR", "INITIAL_TRAINING", "FLEET_TRANSITION"
}
VALID_RESERVE_CALL_TYPES = {"SC", "LC"}

#: D3's marker for a pairing whose fleet the source system could not name.
UNKNOWN_FLEET = "UNKNOWN"


def valid_block_types(cfg: config.BaseConfig) -> set[str]:
    """The spec's block types plus those `data.block_type_map` maps (IMP-521):
    a type the loader can place is a valid one; any other is a defect."""
    return VALID_BLOCK_TYPES | set(cfg.data.block_type_map)


@dataclass(frozen=True)
class QualityCheckResult:
    name: str
    status: str  # "PASS" | "MARGINAL" | "FAIL"
    details: str
    #: Context that does not change the verdict (the other direction of a join,
    #: what a resolved id rate would be, ...). Kept out of `details` so the
    #: one-line verdict stays stable.
    note: str = ""


def station_day_completeness(days: pl.DataFrame) -> float:
    """Observed station-days / expected station-days, in [0, 1].

    Takes any frame with `station` and `date` columns, one row per observed
    station-day. F-42: it used to be applied to D9; it is now applied to the
    days D8 records departures at each crew base -- the daily input the regime
    HMM needs (a missing day is uninformative to the HMM, a run of them blinds it).

    AUD-28b: expected days are counted per station as that station's OWN
    continuous first..last span, summed. Not the count of distinct observed
    dates -- that let a wholly missing date shrink the denominator and hide
    itself. And not the global span x every station -- that would charge a
    seasonal outstation for months it never operated, failing the gate on a
    corpus with no actual missing station-day (and since AUD-13 that gate
    failure is a non-zero exit, so the overcount would block the CLI).
    Interior gaps inside a station's own reporting period are what this
    catches.

    Stated limit, not solved here: a station absent from the data entirely, or one
    missing its leading/trailing days, is still invisible -- only a network
    station roster carrying each station's expected operating period could
    see those.
    """
    if days.height == 0:
        return 1.0
    per_station = (
        days.with_columns(pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d").alias("_d"))
        .group_by("station")
        .agg(((pl.col("_d").max() - pl.col("_d").min()).dt.total_days() + 1).alias("span_days"))
    )
    expected = int(per_station["span_days"].sum() or 0)
    return days.height / expected if expected > 0 else 1.0


def _try_load(cfg: config.BaseConfig, name: str) -> pl.DataFrame | None:
    """A dataset, or None when the corpus does not carry it (an optional input
    to a check, not a reason to abort the whole report)."""
    try:
        return loaders.load_dataset(cfg, name)
    except (FileNotFoundError, KeyError):
        return None


def _status(rate: float, passing: float, marginal: float | None = None) -> str:
    if rate >= passing:
        return "PASS"
    if marginal is not None and rate >= marginal:
        return "MARGINAL"
    return "FAIL"


# ------------------------------------------------------------ linkage helpers

def _day_expr(df: pl.DataFrame, column: str, *, timestamp: bool) -> pl.Expr | None:
    """The date to pair a bare pairing code with, or None if the frame lacks it."""
    if column not in df.columns:
        return None
    return pl.col(column).dt.date() if timestamp else pl.col(column)


def _linkage(
    cfg: config.BaseConfig, df: pl.DataFrame, id_col: str, day: pl.Expr | None, known: set[str]
) -> dict[str, Any]:
    return ids.linkage_rates(df, id_col, day, known, cfg.data.pairing_id_forms)


def _link_note(rates: dict[str, Any], accepted: bool) -> str:
    """Exact vs resolvable, said once; empty when resolving changes nothing."""
    if rates["resolvable"] == rates["exact"]:
        return ""
    basis = "ACCEPTED (data.allow_resolved_ids)" if accepted else "not accepted"
    return (
        f"exact {rates['exact']}/{rates['total']} ({rates['exact_rate']:.1%}); resolvable by "
        f"code + date {rates['resolvable']}/{rates['total']} ({rates['resolvable_rate']:.1%}), "
        f"{basis}"
    )


# --------------------------------------------------------- D6/D7 join recovery

def _pairs(df: pl.DataFrame, crew: str, pairing: str) -> pl.DataFrame:
    return df.select(pl.col(crew).alias("crew_id"), pl.col(pairing).alias("pairing_id")).unique()


def _draft_join(cfg: config.BaseConfig, d6: pl.DataFrame, d7: pl.DataFrame) -> dict[str, Any]:
    """Both directions of the D6 x D7 join (IMP-514), on the configured codes.

    precision (D6 -> D7): of the draft-looking D6 changes, how many have a premium receipt.
    recall    (D7 -> D6): of the premium receipts, how many have a D6 change.

    Without a notice rule most short-notice-coded D6 rows are ordinary roster
    changes, so precision is not a measure of anything: recall is the gate.
    With `draft_reconstruction.max_notice_hours` set, D6 is narrowed to changes
    made inside that notice and precision is what spec 6.2 describes.
    """
    params = cfg.draft_reconstruction
    d6_drafts = d6.filter(pl.col("reason_code").is_in(params.short_notice_reason_codes))
    notice_rule = params.max_notice_hours is not None
    if notice_rule:
        from . import drafts

        d6_drafts = (
            drafts.with_notice_lead(cfg, d6_drafts)
            .filter(pl.col("lead_hours") <= params.max_notice_hours)
            .drop("lead_hours")
        )
    d7_prem = d7.filter(pl.col("pay_code").is_in(params.premium_pay_codes))

    d6_pairs = _pairs(d6_drafts, "crew_id", "new_pairing_id")
    d7_pairs = _pairs(d7_prem, "crew_id", "linked_pairing_id")
    matched = d6_pairs.join(d7_pairs, on=["crew_id", "pairing_id"], how="inner").height

    # Precision keeps counting ROWS of D6 (a draft is a change event), as the gate always has.
    joined_rows = d6_drafts.join(
        d7_prem.select("crew_id", "linked_pairing_id").unique(),
        left_on=["crew_id", "new_pairing_id"], right_on=["crew_id", "linked_pairing_id"], how="inner",
    ).height
    precision = joined_rows / d6_drafts.height if d6_drafts.height else 1.0
    recall = matched / d7_pairs.height if d7_pairs.height else 1.0
    return {
        "precision": precision, "recall": recall, "d6_rows": d6_drafts.height,
        "d7_pairs": d7_pairs.height, "notice_rule": notice_rule,
        "rate": precision if notice_rule else recall,
    }


# --------------------------------------------------------------- generic defects

def _duplicate_rate(df: pl.DataFrame) -> tuple[int, float]:
    if df.height == 0:
        return 0, 0.0
    dups = df.height - df.unique().height
    return dups, dups / df.height


def _constant_columns(df: pl.DataFrame, min_rows: int) -> list[str]:
    """Columns holding a single value (all-null included) on a dataset big enough
    for that to mean something."""
    if df.height < min_rows:
        return []
    return [c for c in df.columns if df[c].n_unique() <= 1]


def _overlapping_blocks(d2: pl.DataFrame) -> int:
    """D2 blocks that start before an earlier block of the same crew has ended."""
    needed = {"crew_id", "start_utc", "end_utc"}
    if not needed <= set(d2.columns) or d2.height == 0:
        return 0
    ordered = d2.sort(["crew_id", "start_utc"]).with_columns(
        pl.col("end_utc").cum_max().shift(1).over("crew_id").alias("_prev_end")
    )
    return ordered.filter(pl.col("start_utc") < pl.col("_prev_end")).height


def _defect_checks(cfg: config.BaseConfig, tables: dict[str, pl.DataFrame]) -> list[QualityCheckResult]:
    """IMP-523 / IMP-524 / IMP-525: defects a real extract showed that no
    linkage gate sees -- repeated rows, constant columns, overlapping rosters,
    unusable D3 legs, unregistered pay codes, scheduled-only flights."""
    gates = cfg.quality_gates
    out: list[QualityCheckResult] = []

    # Exact duplicate rows, per dataset.
    for name, df in tables.items():
        if df.height == 0:
            continue
        dups, rate = _duplicate_rate(df)
        status = "PASS" if rate <= gates.duplicate_rate_max else "FAIL"
        out.append(QualityCheckResult(
            f"{name.split('_')[0].upper()} duplicate rows", status,
            f"{rate:.2%} exact duplicates ({dups} of {df.height} rows, "
            f"threshold {gates.duplicate_rate_max:.2%})",
        ))

    # Columns that hold one value everywhere: a field the extraction did not fill.
    constant = {
        name: cols for name, df in tables.items()
        if (cols := _constant_columns(df, gates.constant_column_min_rows))
    }
    out.append(QualityCheckResult(
        "Constant columns (one value on every row)",
        "MARGINAL" if constant else "PASS",
        "; ".join(f"{n.split('_')[0].upper()}.{c}" for n, cols in constant.items() for c in cols)
        if constant else "none",
        note="a constant column carries no information; do not calibrate on it" if constant else "",
    ))

    # D2 rosters that overlap themselves.
    d2 = tables.get("d2_rosters")
    if d2 is not None and {"crew_id", "start_utc", "end_utc"} <= set(d2.columns):
        overlapped = _overlapping_blocks(d2)
        rate = overlapped / d2.height if d2.height else 0.0
        out.append(QualityCheckResult(
            "D2 roster overlaps (blocks starting inside another block of the same crew)",
            "PASS" if rate <= gates.overlap_rate_max else "FAIL",
            f"{rate:.2%} overlapping ({overlapped} of {d2.height} blocks, "
            f"threshold {gates.overlap_rate_max:.2%})",
            note=f"data.overlap_policy={cfg.data.overlap_policy}: the roster loader "
                 f"{'reconciles' if cfg.data.overlap_policy == 'reconcile' else 'refuses'} them",
        ))

    # D3 legs usable for duty and flight-time arithmetic.
    legs = _try_load(cfg, "d3_pairing_legs")
    if legs is not None and {"block_hours", "dep_local", "arr_local"} <= set(legs.columns) and legs.height:
        # A deadhead leg (the pilot travels as a passenger) has no block time by
        # definition: it only needs its clock times. Without the column every leg
        # needs block time, as before.
        if "deadhead" in legs.columns:
            needs_block = pl.col("deadhead").fill_null(0) != 1
        else:
            needs_block = pl.lit(True)
        usable = legs.filter(
            ((pl.col("block_hours").fill_null(0) > 0) | ~needs_block)
            & pl.col("dep_local").is_not_null() & pl.col("arr_local").is_not_null()
        ).height
        rate = usable / legs.height
        out.append(QualityCheckResult(
            "D3 leg completeness (positive block time and both clock times)",
            _status(rate, gates.d3_leg_complete_pass),
            f"{rate:.1%} of legs complete (threshold {gates.d3_leg_complete_pass:.0%})",
        ))
    d3 = tables.get("d3_pairings")
    if d3 is not None and "fleet" in d3.columns and d3.height:
        known = d3.filter(pl.col("fleet") != UNKNOWN_FLEET).height
        rate = known / d3.height
        out.append(QualityCheckResult(
            "D3 pairing fleet known", _status(rate, gates.d3_known_fleet_pass),
            f"{rate:.1%} of pairings have a fleet (threshold {gates.d3_known_fleet_pass:.0%})",
        ))

    # D7 pay codes nobody has said the meaning of.
    d7 = tables.get("d7_pay_register")
    if d7 is not None and "pay_code" in d7.columns and d7.height:
        counts = d7.group_by("pay_code").len().to_dicts()
        unregistered = {r["pay_code"]: r["len"] for r in counts if r["pay_code"] not in cfg.data.pay_codes}
        negative = d7.filter(pl.col("amount_cad") < 0).height if "amount_cad" in d7.columns else 0
        out.append(QualityCheckResult(
            "D7 pay codes registered (data.pay_codes)",
            "MARGINAL" if unregistered else "PASS",
            f"unregistered: {unregistered}" if unregistered else "every pay code has a meaning",
            note=f"{negative} negative amount(s)" if negative else "",
        ))

    # D10 invoices V6 cannot attribute to a crew member.
    d10 = tables.get("d10_positioning_invoices")
    if d10 is not None and "crew_id" in d10.columns and d10.height:
        rate = d10["crew_id"].null_count() / d10.height
        out.append(QualityCheckResult(
            "D10 invoices with a crew_id", "PASS" if rate <= gates.null_key_rate_max else "FAIL",
            f"{rate:.1%} without a crew_id (threshold {gates.null_key_rate_max:.0%})",
        ))
    return out


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
    # IMP-517: the same absence counted twice is one absence.
    d4_raw = loaders.load_dataset(cfg, "d4_absences")
    d4 = clean.dedupe_absences(d4_raw)
    d5 = loaders.load_dataset(cfg, "d5_reserve_callouts")
    d6 = loaders.load_dataset(cfg, "d6_schedule_changes")
    d7 = loaders.load_dataset(cfg, "d7_pay_register")
    d8_raw = loaders.load_dataset(cfg, "d8_flight_movements")
    d10 = loaders.load_dataset(cfg, "d10_positioning_invoices")
    d11 = loaders.load_dataset(cfg, "d11_training_sessions")

    checks: list[QualityCheckResult] = []
    d3_pairings = set(d3["pairing_id"].to_list())
    accept_resolved = cfg.data.allow_resolved_ids

    # 1. D4 Linkage (Gate: 95%)
    d4_total = d4.height
    d4_rates = _linkage(cfg, d4, "affected_pairing_id", _day_expr(d4, "absence_start", timestamp=False),
                        d3_pairings)
    if d4_total == 0:
        d4_link_rate = 1.0
    else:
        linked = d4_rates["resolvable"] if accept_resolved else d4_rates["exact"]
        d4_link_rate = linked / d4_total

    d4_status = _status(d4_link_rate, gates.d4_link_pass, gates.d4_link_marginal)
    removed = d4_raw.height - d4.height
    d4_note = _link_note(d4_rates, accept_resolved)
    if removed:
        d4_note = "; ".join(filter(None, [d4_note, f"{removed} exact duplicate D4 row(s) removed first"]))
    checks.append(QualityCheckResult(
        "D4 Linkage (sick calls linked to a valid pairing)", d4_status,
        f"{d4_link_rate:.1%} linked (threshold {gates.d4_link_pass:.0%})", d4_note,
    ))

    # 2. D6/D7 Join Recovery (Gate: 80%)
    join = _draft_join(cfg, d6, d7)
    d6_d7_rate = join["rate"]
    direction = (
        f"D6->D7 precision on changes within {cfg.draft_reconstruction.max_notice_hours:g}h notice; "
        f"D7->D6 recall {join['recall']:.1%}"
        if join["notice_rule"] else
        f"gate is D7->D6 recall over {join['d7_pairs']} paid draft(s); D6->D7 precision "
        f"{join['precision']:.1%} over {join['d6_rows']} short-notice-coded D6 row(s) is information "
        f"only (no draft_reconstruction.max_notice_hours set, so planned changes are not excluded)"
    )
    d6_d7_status = "PASS" if d6_d7_rate >= gates.d6_d7_join_pass else "FAIL"
    checks.append(QualityCheckResult(
        "D6/D7 Join Recovery (draft events backed by payroll receipts)", d6_d7_status,
        f"{d6_d7_rate:.1%} recovered (threshold {gates.d6_d7_join_pass:.0%})", direction,
    ))

    # 3. D8 station-day coverage at crew bases (F-42: replaces D9 completeness).
    # The regime HMM reads one day of D8 departures per base; D9 is no longer
    # an input, so its completeness is no longer a gate. IMP-513: the bases are
    # the ones with ACTIVE pilots (not every base a terminated pilot ever had),
    # and a scheduled-only flight is not a day on which anything was recorded.
    bases = clean.active_pilot_bases(d1, cfg.scope.base)
    d8, d8_report = clean.operated_flights_report(cfg, d8_raw)
    base_days = (
        d8.filter(pl.col("origin").is_in(bases) & pl.col("date").is_not_null())
        .select(pl.col("origin").alias("station"), pl.col("date"))
        .unique()
    )
    cov_rate = station_day_completeness(base_days)
    cov_status = "PASS" if cov_rate >= gates.station_day_coverage_pass else "FAIL"
    checks.append(QualityCheckResult(
        "D8 Station-day coverage (daily departures at every crew base, regime HMM input)",
        cov_status,
        f"{cov_rate:.1%} of base-days covered (threshold {gates.station_day_coverage_pass:.0%})",
        f"bases with active pilots: {', '.join(bases)}",
    ))
    dropped = d8_report["scheduled_only"] + d8_report["after_cutoff"] + d8_report["duplicates"]
    checks.append(QualityCheckResult(
        "D8 flights that operated (movement recorded)",
        "MARGINAL" if dropped else "PASS",
        f"{d8_report['rows_out']} of {d8_report['rows_in']} rows used" if dropped
        else "every row is an operated or cancelled flight",
        note=(f"dropped: {d8_report['scheduled_only']} scheduled-only, {d8_report['after_cutoff']} "
              f"after cutoff {d8_report['cutoff']}, {d8_report['duplicates']} repeated flight rows")
        if dropped else "",
    ))

    # Referential integrity: pairing_id -> D3
    for ds_name, df, col, day in [
        ("D2", d2, "pairing_id", _day_expr(d2, "start_local", timestamp=True)),
        ("D4", d4, "affected_pairing_id", _day_expr(d4, "absence_start", timestamp=False)),
        ("D5", d5, "assigned_pairing_id", _day_expr(d5, "call_ts", timestamp=True)),
        ("D6", d6, "new_pairing_id", None),
        ("D7", d7, "linked_pairing_id", _day_expr(d7, "duty_date", timestamp=False)),
        ("D10", d10, "pairing_id", _day_expr(d10, "date", timestamp=False)),
    ]:
        df_valid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != ""))
        if df_valid.height == 0:
            continue
        rates = _linkage(cfg, df_valid, col, day, d3_pairings)
        orphans = rates["total"] - (rates["resolvable"] if accept_resolved else rates["exact"])
        orphan_rate = orphans / df_valid.height
        status = "PASS" if orphan_rate == 0 else "FAIL"
        checks.append(QualityCheckResult(
            f"{ds_name} pairing_id referential integrity", status,
            f"{orphan_rate:.2%} orphaned ({orphans} of {df_valid.height} rows)",
            _link_note(rates, accept_resolved),
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
    valid_blocks = valid_block_types(cfg)
    mapped = set(cfg.data.block_type_map)
    for ds_name, df, col in [("D2", d2, "block_type"), ("D6", d6, "old_block_type"), ("D6", d6, "new_block_type")]:
        invalid = df.filter(pl.col(col).is_not_null() & (pl.col(col) != "") & ~pl.col(col).is_in(list(valid_blocks)))
        if invalid.height > 0:
            counts = invalid.group_by(col).len().to_dicts()
            checks.append(QualityCheckResult(f"{ds_name} {col} domain validity", "FAIL", f"invalid values: {counts}"))
        else:
            in_use = sorted(set(df[col].drop_nulls().to_list()) & mapped)
            checks.append(QualityCheckResult(
                f"{ds_name} {col} domain validity", "PASS", "0 invalid values",
                note=f"types outside the spec handled by data.block_type_map: {in_use}" if in_use else "",
            ))

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

    # IMP-523 / 524 / 525: defects the linkage gates cannot see.
    tables: dict[str, pl.DataFrame] = {
        "d1_crew_master": d1, "d2_rosters": d2, "d3_pairings": d3, "d4_absences": d4_raw,
        "d5_reserve_callouts": d5, "d6_schedule_changes": d6, "d7_pay_register": d7,
        "d8_flight_movements": d8_raw, "d10_positioning_invoices": d10, "d11_training_sessions": d11,
    }
    checks.extend(_defect_checks(cfg, tables))
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
        if check.note:
            print(f"    note: {check.note}")

    print(f"\nOverall score: {quality_score(checks)}/100")
    print(f"Quality report finished with {fails} failure(s), {marginals} marginal.")
    if fails > 0:
        return 1
    if marginals > 0 and not allow_marginal:
        print("MARGINAL gates are below their Sec6.2 passing grade -- exiting non-zero. "
              "Pass --allow-marginal to accept them explicitly.")
        return 1
    return 0

"""S0-03 -- draft-event reconstruction from D6 x D7 (spec §6.3-1).

No `was_drafted` column exists anywhere in Air Transat's systems: a draft is
the hidden intersection of "D6 recorded an urgent-looking schedule change"
and "D7 paid a draft premium for it". Every part of that recipe --  which D7
pay codes count as a premium, which D6 reason codes count as urgent, which
D6 initiators are trusted -- is a `configs/base.yaml -> draft_reconstruction`
parameter, not a literal, because each one is an assumption about how Air
Transat's systems happen to be coded today (§4.4).
"""
from __future__ import annotations

import json
from typing import Any

import polars as pl

from .. import config
from . import ids, loaders

# Step 3 of §6.3-1's recipe: "the pilot was suddenly placed on a flight."
# Not a `draft_reconstruction` parameter -- it is part of what a draft *is*,
# not an assumption about how Air Transat's systems happen to be coded.
_PLACED_ON_A_PAIRING = "PAIRING"


def with_notice_lead(cfg: config.BaseConfig, d6: pl.DataFrame) -> pl.DataFrame:
    """`d6` plus `lead_hours` (IMP-514): hours from the schedule change to the
    start of the pairing it placed the crew member on.

    The pairing start is the first leg's report time when D3 has legs, else
    the pairing's start date at midnight. A change whose pairing cannot be
    found in D3 (even after resolving its spelling) has a null lead: with a
    notice rule on, that change cannot be shown to be short notice.
    """
    d3 = loaders.load_dataset(cfg, "d3_pairings")
    starts = d3.select(
        pl.col("pairing_id").alias("_pid"), pl.col("start_date").cast(pl.Datetime).alias("_start")
    )
    try:
        legs = loaders.load_dataset(cfg, "d3_pairing_legs")
    except FileNotFoundError:
        legs = None
    if legs is not None:
        first = legs.group_by("pairing_id").agg(pl.col("report_local").min().alias("_first"))
        starts = (
            starts.join(first.rename({"pairing_id": "_pid"}), on="_pid", how="left")
            .with_columns(pl.coalesce("_first", "_start").alias("_start"))
            .select("_pid", "_start")
        )
    resolved = ids.resolve_pairing_ids(
        d6["new_pairing_id"], None, d3["pairing_id"], cfg.data.pairing_id_forms
    )["resolved"]
    return (
        d6.with_columns(resolved.alias("_pid"))
        .join(starts, on="_pid", how="left")
        .with_columns(((pl.col("_start") - pl.col("change_ts")) / pl.duration(hours=1)).alias("lead_hours"))
        .drop("_pid", "_start")
    )


def reconstruct_drafts(cfg: config.BaseConfig, d6: pl.DataFrame | None = None) -> pl.DataFrame:
    """The draft-event table: one row per reconstructed historical draft.

    Join order: D7 first identifies which (crew, pairing) pairs were ever
    paid a configured premium code; D6 rows whose reason code is configured
    as "short notice", that actually placed the crew onto a pairing (§6.3-1
    step 3 -- a reason code alone does not imply that; see D6's
    `CASCADE_UNCOVERED` rows, which look urgent but *remove* coverage
    instead), are then kept only if they land on one of those pairs. A NULL
    `initiator` always survives the initiator filter -- older D6 records
    predate that field, and dropping them would silently undercount recall
    rather than reporting the gap (§6.3-1's 4th acceptance bullet).

    `d6` may be supplied already loaded, so a caller that also needs D6 for
    something else (S0-05's cascade scan) doesn't read it from disk twice.
    """
    params = cfg.draft_reconstruction
    if d6 is None:
        d6 = loaders.load_dataset(cfg, "d6_schedule_changes")
    d7 = loaders.load_dataset(cfg, "d7_pay_register")

    premium = (
        d7.filter(pl.col("pay_code").is_in(params.premium_pay_codes))
        .select("crew_id", "linked_pairing_id")
        .unique()  # a crew/pairing pair may be paid across more than one pay period
        .rename({"linked_pairing_id": "new_pairing_id"})
    )

    candidates = d6.filter(
        pl.col("reason_code").is_in(params.short_notice_reason_codes)
        & (pl.col("new_block_type") == _PLACED_ON_A_PAIRING)
        & (pl.col("initiator").is_null() | pl.col("initiator").is_in(params.initiator_filter))
    )
    if params.max_notice_hours is not None:
        # IMP-514: a change made weeks ahead is a roster change, not a draft,
        # however it is coded. Off (None) until Crew Planning states the window.
        candidates = (
            with_notice_lead(cfg, candidates)
            .filter(pl.col("lead_hours") <= params.max_notice_hours)
            .drop("lead_hours")
        )

    drafts = candidates.join(premium, on=["crew_id", "new_pairing_id"], how="inner")

    return drafts.select(
        pl.col("change_id"),
        pl.col("crew_id"),
        pl.col("change_ts").alias("timestamp"),
        pl.col("old_block_type").alias("prior_status"),
        pl.col("new_pairing_id").alias("covering_pairing_id"),
        pl.col("initiator"),
    ).sort("timestamp")


def prior_status_distribution(drafts: pl.DataFrame) -> dict[str, float]:
    """The tier-mix input: prior status -> share of reconstructed drafts."""
    if drafts.height == 0:
        return {}
    counts = drafts.group_by("prior_status").len()
    return {row["prior_status"]: row["len"] / drafts.height for row in counts.iter_rows(named=True)}


def score_recall(
    cfg: config.BaseConfig, drafts: pl.DataFrame, true_n: int | None = None
) -> dict[str, Any] | None:
    """Recall against `_ground_truth.json`, if the corpus ships one.

    Only the mock corpus does. Real data has no ground truth: recall must
    instead be measured against a week an IOC duty manager has labelled by
    hand (see the story's own manual-check note) -- returning `None` here
    rather than fabricating a number is what keeps that distinction honest.
    Reuses `quality_gates.d6_d7_join_pass`: spec §6.3-1 names it explicitly
    as the *same* 80% Reality Check gate defined in §6.2, not a second one.

    `true_n` overrides the manifest's corpus-wide denominator for a
    window-scoped reconstruction (AUD-04): a windowed numerator over the
    corpus-wide denominator would understate recall by exactly the window
    share. The manifest is still required -- on real data (no manifest) there
    is no denominator of either scope, and None is still the answer.
    """
    truth_path = cfg.paths.corpus_dir / "_ground_truth.json"
    if not truth_path.is_file():
        return None
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    true_n = truth["drafts_true"] if true_n is None else true_n
    gate = cfg.quality_gates.d6_d7_join_pass
    if not true_n:
        # No ground-truth drafts in scope: recall is undefined, not zero. A
        # window with nothing to find used to report recall 0.0 -- a hard FAIL
        # against the 80% gate -- condemning a vacuously perfect
        # reconstruction. `recall: None` says "no measurement", which every
        # consumer already has to handle (real data ships no ground truth at
        # all and gets None from the branch above).
        return {
            "recall": None,
            "found": drafts.height,
            "true_n": 0,
            "gate": gate,
            "gate_pass": True,
        }
    recall = drafts.height / true_n
    return {
        "recall": recall,
        "found": drafts.height,
        "true_n": true_n,
        "gate": gate,
        "gate_pass": recall >= gate,
    }

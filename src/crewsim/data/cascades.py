"""S0-05 -- cascade-table reconstruction from D6, a 7-day follow-on scan (spec §6.3-3).

For every draft S0-03 reconstructed, scan that same crew member's D6 history
for a follow-on break -- a change of the configured "cascade" kind, landing
strictly after the draft and within the configured window. §6.3-3: "did
drawing them cause a future flight to break?"

This is measured against S0-03's *reconstructed* drafts, not the full
ground-truth count -- so it inherits S0-03's recall limitation by
construction: a cascade following a draft S0-03 failed to recall is
invisible here, the same way it would be on real data with no ground truth
at all. `cascade_rate()` reports that limitation explicitly rather than
letting the number stand alone.
"""
from __future__ import annotations

from typing import Any

import polars as pl
from statsmodels.stats.proportion import proportion_confint

from .. import config
from . import drafts, loaders


def reconstruct_cascades(
    cfg: config.BaseConfig, reconstructed_drafts: pl.DataFrame, d6: pl.DataFrame | None = None
) -> pl.DataFrame:
    """One row per reconstructed draft, flagged with whether a same-crew D6

    change of a configured "cascade" kind landed in the follow-on window.
    `d6` may be supplied already loaded (S0-03's reconstruction needs it
    too), so `cascade_target()` doesn't read it from disk twice.
    """
    params = cfg.cascade_reconstruction
    if d6 is None:
        d6 = loaders.load_dataset(cfg, "d6_schedule_changes")

    cascade_events = d6.filter(pl.col("reason_code").is_in(params.cascade_reason_codes)).select(
        pl.col("crew_id"), pl.col("change_ts").alias("cascade_ts")
    )

    window = pl.duration(days=params.window_days)
    hits = (
        reconstructed_drafts.select("change_id", "crew_id", "timestamp")
        .join(cascade_events, on="crew_id", how="left")
        .with_columns(
            (
                pl.col("cascade_ts").is_not_null()
                & (pl.col("cascade_ts") > pl.col("timestamp"))
                & (pl.col("cascade_ts") <= pl.col("timestamp") + window)
            ).alias("_hit")
        )
        .group_by("change_id", maintain_order=True)
        .agg(pl.col("_hit").any().alias("cascaded"))
    )

    return reconstructed_drafts.select("change_id", "crew_id", "timestamp").join(
        hits, on="change_id", how="left"
    )


def cascade_rate(cfg: config.BaseConfig, cascades: pl.DataFrame, draft_recall: dict[str, Any] | None) -> dict[str, Any]:
    """Rate + Wilson-score CI, plus the S0-03 recall this rate is bounded by.

    A point estimate alone invites reading it as exact; the CI is what makes
    this a distribution-shaped target, per the story's own acceptance bullet.
    """
    n = cascades.height
    count = int(cascades["cascaded"].sum()) if n else 0
    rate = count / n if n else 0.0
    ci_low, ci_high = proportion_confint(
        count, n, alpha=1 - cfg.cascade_reconstruction.confidence_level, method="wilson"
    ) if n else (0.0, 0.0)
    return {
        "rate": rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "count": count,
        "n_drafts": n,
        "confidence_level": cfg.cascade_reconstruction.confidence_level,
        "draft_recall": draft_recall,
    }


def cascade_target(cfg: config.BaseConfig, window_name: str | None = None) -> dict[str, Any]:
    """Convenience entry point: reconstruct S0-03's drafts, then this story's cascades.

    Loads D6 once and shares it with both reconstructions.
    """
    d6 = loaders.load_dataset(cfg, "d6_schedule_changes")

    window_true_n: int | None = None
    if window_name:
        import datetime

        if cfg.windows is None:
            raise ValueError("cascade_target with a window requires cfg.windows to be configured")
        window_bounds = cfg.windows.get(window_name)
        # AUD-04: compare datetimes with datetimes. The previous filter
        # compared `change_ts` (datetime[us]) against `.timestamp()` floats
        # -- epoch SECONDS, which Polars reads on the column's microsecond
        # scale (~1970-01-01 00:29), so every post-1970 row failed the upper
        # bound and BOTH windows returned an empty D6. That is why gate V4
        # was permanently INCONCLUSIVE ("0 of 2,584 known drafts found"): the
        # holdout reconstruction never saw a single row. (.timestamp() was
        # also local-timezone-dependent, a machine-dependence of its own.)
        start_dt = datetime.datetime.combine(window_bounds.start, datetime.time.min)
        end_dt = datetime.datetime.combine(window_bounds.end, datetime.time.max)
        d6 = d6.filter((pl.col("change_ts") >= start_dt) & (pl.col("change_ts") <= end_dt))
        # Recall must be scored against the drafts that could possibly be
        # found in THIS window, not the manifest's corpus-wide total --
        # otherwise a 12-month window is condemned to ~1/3 recall by
        # arithmetic. For the mock corpus the short-notice reason codes ARE
        # the ground-truth draft markers (the manifest's corpus-wide
        # drafts_true equals their corpus-wide count), so the windowed count
        # of those rows is the windowed truth.
        window_true_n = d6.filter(
            pl.col("reason_code").is_in(cfg.draft_reconstruction.short_notice_reason_codes)
        ).height

    reconstructed = drafts.reconstruct_drafts(cfg, d6=d6)
    recall = drafts.score_recall(cfg, reconstructed, true_n=window_true_n)
    cascades = reconstruct_cascades(cfg, reconstructed, d6=d6)
    return cascade_rate(cfg, cascades, recall)

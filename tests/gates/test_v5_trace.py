import datetime

import polars as pl

from crewsim import config
from crewsim.data import loaders
from crewsim.engine import replay
from crewsim.engine.policy import load_policy
from crewsim.gates.v5_trace import MOCK_DATA_CAVEAT, format_timeline, run_v5_gate


def _scope_absences(cfg):
    d4 = loaders.load_dataset(cfg, "d4_absences")
    return d4.filter(
        (pl.col("base") == cfg.scope.base)
        & (pl.col("fleet") == cfg.scope.fleet)
        & (pl.col("position") == cfg.scope.position)
    )


def test_find_peak_disruption_week_matches_manual_count():
    """Cross-check replay.find_peak_disruption_week against an independent
    manual weekly aggregation over the same scope-filtered D4 rows."""
    cfg = config.load()
    d4 = _scope_absences(cfg)

    from collections import Counter
    counts: Counter[datetime.date] = Counter()
    for row in d4.iter_rows(named=True):
        day = row["absence_start"]
        monday = day - datetime.timedelta(days=day.weekday())
        counts[monday] += 1
    expected_max = max(counts.values())

    week = replay.find_peak_disruption_week(cfg)
    assert week.weekday() == 0, "must return a Monday"
    assert counts[week] == expected_max


def test_run_historical_week_uses_only_real_absences_not_synthetic():
    """Blocking check: the replay must NOT also run the synthetic
    NHPP-driven sick_call_source -- every disruption-arrival trace line
    must trace back to a real D4 absence_id for this exact week/scope, and
    the count of distinct real absences touched must be <= the real D4 row
    count for this window (some absences may find no calendar overlap and
    produce zero items, but none may be invented)."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    week_start = replay.find_peak_disruption_week(cfg)
    week_end = week_start + datetime.timedelta(days=7)
    real_ids = set(
        _scope_absences(cfg)
        .filter((pl.col("absence_start") >= week_start) & (pl.col("absence_start") < week_end))
        .get_column("absence_id")
    )
    assert real_ids, "the peak week must have at least one real absence for this scope"

    sim = replay.run_historical_week(cfg, costs, policy, week_start)

    seen_ids = set()
    for line in sim.trace:
        if "REAL ABSENCE" in line:
            absence_id = line.split("REAL ABSENCE ", 1)[1].split(" ", 1)[0]
            seen_ids.add(absence_id)
            assert absence_id in real_ids, f"trace referenced an absence_id not in this week's real D4 rows: {absence_id}"

    assert seen_ids, "a real disruption week must produce at least one real-absence trace line"
    assert seen_ids <= real_ids


def test_format_timeline_groups_by_hour_and_labels_mock_data():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    week_start = replay.find_peak_disruption_week(cfg)

    sim = replay.run_historical_week(cfg, costs, policy, week_start)
    timeline = format_timeline(sim, week_start)

    assert MOCK_DATA_CAVEAT in timeline
    assert "would you have actually done this" in timeline
    assert "-- Mon " in timeline or "-- Tue " in timeline or "-- Wed " in timeline, (
        "timeline must contain at least one hour-header line"
    )


def test_verbose_trace_shows_alternatives_considered_and_rejected():
    """S1e-06's own AC: each decision shows the alternatives considered and
    why they were rejected -- proven against the real replay, not a
    fixture: at least one real DRAFT decision shows tier sizes, and if any
    real RESERVE decision rejected an on-call candidate, the real legality
    fail_rule/reason must appear verbatim."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    week_start = replay.find_peak_disruption_week(cfg)

    sim = replay.run_historical_week(cfg, costs, policy, week_start)

    draft_alt_lines = [line_ for line_ in sim.trace if "DRAFT alternatives" in line_]
    assert draft_alt_lines, "a real disruption week must produce at least one draft decision"
    assert "tier1=" in draft_alt_lines[0]
    assert "chose" in draft_alt_lines[0]

    reserve_alt_lines = [line_ for line_ in sim.trace if "RESERVE alternatives" in line_]
    rejected_lines = [line_ for line_ in reserve_alt_lines if "rejected (on-call but illegal): " in line_
                       and not line_.endswith("none")]
    if rejected_lines:
        assert "ILLEGAL_" in rejected_lines[0]


def test_cancelled_items_always_show_why_no_alternative_existed():
    """Every real 'CANCELLED at deadline' line must be preceded by an
    explanation of why (either a logged decision that found nobody, at
    least once for that item) -- a cancellation with zero preceding
    reasoning was a real gap found while verifying this story's own AC:
    an item whose only overlapping pairing started before the replay
    window used to cancel in the SAME instant it was created, with no
    RESERVE/DRAFT alternatives line and no "0 eligible/0 legal" line
    either (fixed by excluding pre-window blocks in apply_named_absence,
    and by logging the zero-candidates case explicitly)."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    week_start = replay.find_peak_disruption_week(cfg)

    sim = replay.run_historical_week(cfg, costs, policy, week_start)

    import re
    for i, line in enumerate(sim.trace):
        m = re.match(r"\[t=\d+\] item (\d+) \([^)]*\) CANCELLED at deadline", line)
        if not m:
            continue
        uid = m.group(1)
        preceding = sim.trace[:i]
        has_reasoning = any(
            f"item {uid}" in earlier and ("alternatives" in earlier or "eligible reserves" in earlier)
            for earlier in preceding
        )
        assert has_reasoning, f"item {uid} cancelled with no preceding decision reasoning: {line}"


def test_run_v5_gate_default_week_is_the_peak_week():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    expected_week = replay.find_peak_disruption_week(cfg)
    _sim, week_used, timeline = run_v5_gate(cfg, costs, policy)
    assert week_used == expected_week
    assert week_used.isoformat() in timeline

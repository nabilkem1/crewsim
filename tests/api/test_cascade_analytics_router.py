"""api/routers/analytics.py -- the cascade endpoints read a completed grid job.

The router computes nothing, so what needs pinning is the reading: that it
refuses a job it cannot honestly answer from, and above all that a run
carrying NO cascade data is never rendered as a run in which no cascades
occurred. Those two look identical in a chart and mean opposite things -- this
router's whole predecessor was deleted for serving figures that looked real.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from crewsim.api.routers import analytics


def _job(job_id="job-1", status="completed", results=None):
    return MagicMock(
        id=job_id, status=status, results=results, created_at=datetime(2026, 8, 12, 9, 0, 0, tzinfo=UTC)
    )


def _db_returning(job):
    """A Session whose query chain answers `job` however it is filtered.

    `_latest_batch_job` chains `.filter(type)` then either `.filter(id)` or
    `.filter(status).order_by(...)`, so `filter` has to return the same chain
    object rather than a fresh child mock -- otherwise the second filter lands
    on a different mock and `.first()` yields a MagicMock instead of the job.
    """
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.first.return_value = job
    db = MagicMock()
    db.query.return_value = chain
    return db


def _analytics(**over):
    base = {
        "n_scenarios": 8, "drafts_total": 985, "cascading_drafts_total": 5,
        "cascade_rate_mean": 0.005, "cascade_rate_max": 0.041,
        "n_scenarios_with_drafts": 8, "n_scenarios_with_cascade": 1,
        "share_of_scenarios_with_cascade": 0.125, "per_scenario": [],
        "n_chains": 1234, "n_cascading_chains": 2,
        "mean_cost_simple_chain": 461.0, "mean_cost_cascading_chain": 3000.0,
        "amplification_ratio": 6.5, "cascading_chain_cost_total": 6000.0,
        "share_of_chain_cost_from_cascades": 0.01,
        "chain_size_histogram": {"1": 1232, "4": 1, "5": 1}, "max_chain_size": 5,
        "tier_mix": {"DRAFT_TIER1": 680, "DRAFT_TIER2": 5}, "n_uncovered_chains": 0,
        "reserve_loss_cascades": 0, "reserve_blocks_lost": 0, "reserve_loss_note": "n",
        "exemplar_chains": [], "depth_note": "d",
    }
    base.update(over)
    return base


def _results(rows):
    return {"scoreboard": rows, "season": "winter_sun", "num_scenarios": 8}


def test_missing_cascade_analytics_is_flagged_not_shown_as_zero_cascades():
    """The failure this router exists to avoid.

    A job that predates the feature has `cascade_analytics: None`. If that were
    rendered as zeros, a planner would read "this policy causes no cascades"
    from a run that never measured any.
    """
    job = _job(results=_results([{"policy": "R6", "cascade_analytics": None}]))
    out = analytics.get_cascade_summaries(job_id="job-1", db=_db_returning(job))

    assert out["stale_policies"] == ["R6"]
    assert out["notice"] is not None
    assert out["summaries"][0]["analytics"] is None, "must stay None, never coerced to zeros"


def test_no_notice_when_every_policy_carries_cascade_data():
    job = _job(results=_results([{"policy": "R6", "cascade_analytics": _analytics()}]))
    out = analytics.get_cascade_summaries(job_id="job-1", db=_db_returning(job))
    assert out["stale_policies"] == []
    assert out["notice"] is None
    assert out["summaries"][0]["analytics"]["amplification_ratio"] == 6.5


def test_incomplete_job_is_refused_rather_than_partially_reported():
    job = _job(status="running", results=None)
    with pytest.raises(HTTPException) as exc:
        analytics.get_cascade_summaries(job_id="job-1", db=_db_returning(job))
    assert exc.value.status_code == 400
    assert "not completed" in exc.value.detail


def test_unknown_job_id_is_404():
    with pytest.raises(HTTPException) as exc:
        analytics.get_cascade_summaries(job_id="nope", db=_db_returning(None))
    assert exc.value.status_code == 404


def test_no_completed_run_at_all_says_so_instead_of_returning_empty():
    """An empty dashboard and "you have not run the grid yet" are different
    problems with different fixes, so the second must not render as the first."""
    with pytest.raises(HTTPException) as exc:
        analytics.get_cascade_summaries(job_id=None, db=_db_returning(None))
    assert exc.value.status_code == 404
    assert "Launch one from Processing" in exc.value.detail


def test_drills_rank_chains_by_cost_across_policies():
    cheap = {"scenario_id": 1, "root_event_uid": 9, "n_items": 2, "cost": 900.0,
             "start_minute": 0.0, "end_minute": 1.0, "uncovered": False,
             "categories": [], "rows": []}
    dear = {**cheap, "root_event_uid": 4, "cost": 25800.0, "uncovered": True}
    job = _job(results=_results([
        {"policy": "R6", "cascade_analytics": _analytics(exemplar_chains=[cheap])},
        {"policy": "R10", "cascade_analytics": _analytics(exemplar_chains=[dear])},
    ]))
    out = analytics.get_exemplar_drills(job_id="job-1", db=_db_returning(job))

    assert [d["cost"] for d in out["drills"]] == [25800.0, 900.0]
    assert out["drills"][0]["policy"] == "R10", "each chain keeps the policy it came from"


def test_drills_skip_stale_policies_without_inventing_chains():
    job = _job(results=_results([
        {"policy": "R6", "cascade_analytics": None},
        {"policy": "R10", "cascade_analytics": _analytics(exemplar_chains=[])},
    ]))
    out = analytics.get_exemplar_drills(job_id="job-1", db=_db_returning(job))
    assert out["drills"] == []


def test_comparison_states_its_pairing_basis_rather_than_a_seed_warning():
    """WD-004 asks for a seed-mismatch warning. Every row here comes from one
    grid job under one master seed, so the warning could never fire -- the
    response states why the pairing holds instead of implying it via silence."""
    job = _job(results=_results([
        {"policy": "R6", "cascade_analytics": _analytics()},
        {"policy": "R10", "cascade_analytics": _analytics()},
    ]))
    out = analytics.compare_cascade_policies(job_id="job-1", db=_db_returning(job))

    assert out["paired"] is True
    assert "same CRN scenario set" in out["pairing_basis"]
    assert [c["policy"] for c in out["comparisons"]] == ["R6", "R10"]


def test_every_response_carries_the_run_it_came_from():
    """A cascade figure without its run is unattributable -- the provenance
    envelope is what lets a reader tell two runs' numbers apart."""
    job = _job(results=_results([{"policy": "R6", "cascade_analytics": _analytics()}]))
    db = _db_returning(job)
    for out in (
        analytics.get_cascade_summaries(job_id="job-1", db=db),
        analytics.get_exemplar_drills(job_id="job-1", db=db),
        analytics.compare_cascade_policies(job_id="job-1", db=db),
    ):
        assert out["job_id"] == "job-1"
        assert out["season"] == "winter_sun"
        assert out["num_scenarios"] == 8

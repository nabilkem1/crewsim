"""Cascade analytics, read from a completed batch job's stored results.

Every endpoint here once returned hardcoded figures -- a "Weekend Shortage
Recovery" cascade with a 0.92 success rate and a $12,500 cost impact, exemplar
drills with efficiency scores, policy comparisons with fatigue ratings. None of
it came from `crewsim.engine.cascade` or gate V4, and the front end rendered
all of it as measured output. Those numbers were deleted rather than labelled,
and this module was left as an explicit "not implemented" surface until a
response contract could be designed against the engine rather than
reverse-engineered from the placeholder shapes.

That contract now exists: `reporting/cascade_analytics.py` computes chain-level
cascade economics from real ledger rows, and `reporting/grid.py` runs it inside
`_run_one_policy` while the Simulation objects are still in memory. Its output
is stored on the batch job (`processing_batch`) alongside the scoreboard.

So these endpoints do no simulation of their own -- they read that job. Two
reasons, both load-bearing:

* **Provenance.** The cascade figures come from the *same* CRN scenario set as
  the E[C] shown next to them. An endpoint that ran its own scenarios would
  quote cascade numbers drawn from a different sample than the costs they are
  meant to explain.
* **Latency.** WD-001 asks for aggregate load under a second. A CRN run is
  seconds-to-minutes per policy; a dict read is not.

A job that predates this feature simply has no `cascade_analytics` key. That is
reported as such -- "this run was executed before cascade analytics existed,
re-run it" -- and never silently rendered as a run in which no cascades
occurred. The two look identical in a chart and mean opposite things.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from crewsim.api.db import Job, get_db

router = APIRouter(prefix="", tags=["Analytics"])

_BATCH_JOB_TYPE = "processing_batch"

# Each policy contributes up to `n_exemplars` chains, and each chain carries
# every ledger row in it -- so a wide grid multiplies. Capped at the response
# rather than at computation: the stored job keeps every policy's own
# exemplars (a per-policy view needs them), and only the cross-policy list a
# reader actually scrolls is truncated. `truncated` says so rather than the
# list silently ending.
_MAX_DRILLS = 25

STALE_JOB_NOTICE = (
    "This run completed before cascade analytics existed, so it carries no "
    "cascade chain data. Re-run the policy grid to populate it. (An empty "
    "result here is NOT the same as a run in which no cascades occurred.)"
)


def _latest_batch_job(db: Session, job_id: str | None) -> Job:
    """The requested batch job, or the most recent completed one.

    Defaulting to the latest completed run means the tab opens with something
    real in it rather than an id prompt, which is how the Results tab already
    behaves.
    """
    query = db.query(Job).filter(Job.type == _BATCH_JOB_TYPE)
    if job_id is not None:
        job = query.filter(Job.id == job_id).first()
        if job is None:
            raise HTTPException(status_code=404, detail=f"Batch job {job_id!r} not found")
    else:
        job = (
            query.filter(Job.status == "completed")
            .order_by(Job.created_at.desc())
            .first()
        )
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="No completed policy-grid run found. Launch one from Processing first.",
            )
    if job.status != "completed" or not job.results:
        raise HTTPException(
            status_code=400,
            detail=f"Batch job {job.id} has not completed (status: {job.status})",
        )
    return job


def _policy_rows(job: Job) -> list[dict[str, Any]]:
    return list(job.results.get("scoreboard") or [])


def _job_envelope(job: Job) -> dict[str, Any]:
    """Provenance every response carries, so a figure is never shown without
    the run it came from."""
    return {
        "job_id": job.id,
        "season": job.results.get("season"),
        "num_scenarios": job.results.get("num_scenarios"),
        "created_at": job.created_at.isoformat(),
    }


@router.get("/cascade-summaries")
def get_cascade_summaries(
    job_id: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Per-policy cascade summary for one grid run (WD-001)."""
    job = _latest_batch_job(db, job_id)
    rows = _policy_rows(job)
    summaries = [
        {
            "policy": r.get("policy"),
            "policy_id": r.get("policy_id"),
            "expected_cost": r.get("expected_cost"),
            "cvar95": r.get("cvar95"),
            "analytics": r.get("cascade_analytics"),
        }
        for r in rows
    ]
    stale = [s["policy"] for s in summaries if s["analytics"] is None]
    return {
        **_job_envelope(job),
        "summaries": summaries,
        "stale_policies": stale,
        "notice": STALE_JOB_NOTICE if stale else None,
    }


@router.get("/exemplar-drills")
def get_exemplar_drills(
    job_id: str | None = None, policy: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """The costliest real cascade chains, row by row (WD-002/WD-003).

    Each drill is an actual ledger chain: every row sharing one
    `root_event_uid`, in booking order. Nothing is synthesised -- if a run
    produced no multi-item chains, this is empty, which is a finding about the
    run rather than a gap in the endpoint.
    """
    job = _latest_batch_job(db, job_id)
    rows = _policy_rows(job)
    if policy is not None:
        rows = [r for r in rows if r.get("policy") == policy]
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"Policy {policy!r} is not in job {job.id}'s scoreboard"
            )
    drills = []
    for r in rows:
        analytics = r.get("cascade_analytics")
        if not analytics:
            continue
        for chain in analytics.get("exemplar_chains") or []:
            drills.append({"policy": r.get("policy"), **chain})
    drills.sort(key=lambda d: -(d.get("cost") or 0))
    total = len(drills)
    return {
        **_job_envelope(job),
        "drills": drills[:_MAX_DRILLS],
        "total_chains": total,
        "truncated": total > _MAX_DRILLS,
        "depth_note": next(
            (
                r["cascade_analytics"].get("depth_note")
                for r in rows
                if r.get("cascade_analytics")
            ),
            None,
        ),
    }


@router.get("/cascade-policy-comparisons")
def compare_cascade_policies(
    job_id: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Cascade behaviour across the policies in one grid run (WD-004).

    The seed-mismatch warning WD-004 asks for is structurally unnecessary
    here and deliberately not faked: every row comes from a single grid job,
    and `run_grid` passes one `master_seed` to every policy in it, so the
    comparison is CRN-paired by construction. The pairing basis is stated in
    the response instead, so a reader can see *why* it holds rather than
    trusting an absent warning.
    """
    job = _latest_batch_job(db, job_id)
    comparisons = [
        {
            "policy": r.get("policy"),
            "policy_id": r.get("policy_id"),
            "expected_cost": r.get("expected_cost"),
            "cvar95": r.get("cvar95"),
            "analytics": r.get("cascade_analytics"),
        }
        for r in _policy_rows(job)
    ]
    return {
        **_job_envelope(job),
        "comparisons": comparisons,
        "paired": True,
        "pairing_basis": (
            "All policies in this run were evaluated over the same CRN scenario "
            "set from one master seed, so differences are policy effects rather "
            "than sampling noise."
        ),
    }

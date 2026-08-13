"""Generic job records.

`simulate_job_execution` is a demo worker that counts to ten -- it models no
simulation and produces no results. It is kept only because the jobs table and
its lifecycle (cancel/retry) are exercised through it; the real work runs in
`routers/processing.py` and `routers/calibration.py`.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from crewsim.api.db import Job, SessionLocal, get_db

router = APIRouter(prefix="", tags=["jobs"])

_DEMO_STEPS = 10
_DEMO_STEP_SECONDS = 1
_PERCENT = 100
_CANCELLABLE = ("queued", "running")
_RETRYABLE = ("failed", "cancelled")


class JobCreate(BaseModel):
    type: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    season: str | None = None


def simulate_job_execution(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "running"
        db.commit()

        for step in range(1, _DEMO_STEPS + 1):
            time.sleep(_DEMO_STEP_SECONDS)
            db.refresh(job)
            if job.status == "cancelled":
                return
            job.progress = int(step / _DEMO_STEPS * _PERCENT)
            db.commit()

        job.status = "completed"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller via the job row
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()


def _get_job_or_404(job_id: str, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobResponse)
def create_job(
    job_in: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Job:
    job = Job(id=str(uuid.uuid4()), type=job_in.type, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(simulate_job_execution, job.id)
    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return db.query(Job).order_by(Job.created_at.desc()).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    return _get_job_or_404(job_id, db)


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = _get_job_or_404(job_id, db)
    if job.status not in _CANCELLABLE:
        raise HTTPException(status_code=400, detail="Cannot cancel job in current state")
    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(
    job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Job:
    job = _get_job_or_404(job_id, db)
    if job.status not in _RETRYABLE:
        raise HTTPException(
            status_code=400, detail="Only failed or cancelled jobs can be retried"
        )
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    db.commit()
    db.refresh(job)
    background_tasks.add_task(simulate_job_execution, job.id)
    return job


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """Same convention as api/routers/processing.py's own delete_job: not
    restricted to terminal states. Both run_calibration_job and
    run_processing_job re-fetch the row by id at every step and exit quietly
    if it is gone (`if not job: return`), so deleting one mid-run is safe --
    the background thread just stops updating a row nobody is looking at."""
    job = _get_job_or_404(job_id, db)
    db.delete(job)
    db.commit()
    return {"status": "success", "message": "Job deleted"}

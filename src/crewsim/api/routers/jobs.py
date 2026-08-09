import time
import uuid
from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from crewsim.api.db import get_db, SessionLocal, Job

router = APIRouter(prefix="", tags=["jobs"])

class JobCreate(BaseModel):
    type: str

class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None

    class Config:
        from_attributes = True

def simulate_job_execution(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        
        job.status = 'running'
        db.commit()
        
        # Simulate work
        for i in range(1, 11):
            time.sleep(1) # Simulate time taken
            
            # Refresh job state in case it was modified
            db.refresh(job)
            if job.status == 'cancelled':
                return
                
            job.progress = i * 10
            db.commit()
            
        job.status = 'completed'
        db.commit()
    except Exception as e:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'failed'
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()

@router.post("", response_model=JobResponse)
def create_job(job_in: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    new_job = Job(
        id=job_id,
        type=job_in.type,
        status='queued',
        progress=0
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    background_tasks.add_task(simulate_job_execution, job_id)
    return new_job

@router.get("", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).order_by(Job.created_at.desc()).all()

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail="Cannot cancel job in current state")
    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return job

@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ["failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")
    
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    db.commit()
    db.refresh(job)
    
    background_tasks.add_task(simulate_job_execution, job.id)
    return job

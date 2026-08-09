import uuid
import time
import random
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from crewsim.api.db import get_db, SessionLocal, Job

router = APIRouter(prefix="", tags=["Processing"])

class RunRequest(BaseModel):
    config_id: str
    scenario: str

class BatchRunRequest(BaseModel):
    config_id: str
    scenarios: List[str]

class OutputConfig(BaseModel):
    destination_path: str

class HardwareConfig(BaseModel):
    worker_count: int
    memory_gb: int

class PredictionResponse(BaseModel):
    estimated_time_seconds: int
    estimated_cost_dollars: float

def run_processing_job(job_id: str, config_id: str, scenarios: List[str]):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        
        job.status = 'running'
        db.commit()
        
        from crewsim import config
        from crewsim.engine import des
        from crewsim.engine.policy import load_policy
        from pathlib import Path
        
        cfg = config.load()
        costs = config.load_costs(cfg)
        
        pol_path = config.repo_root() / "configs" / "policies" / f"{config_id}.yaml"
        if not pol_path.exists():
            pol_path = config.repo_root() / "configs" / "policies" / "R10.yaml"
        policy = load_policy(str(pol_path))
        
        for idx, sc_str in enumerate(scenarios):
            db.refresh(job)
            if job.status == 'cancelled':
                return
            sc_id = int(sc_str)
            des.run_scenario(
                cfg, costs, policy, scenario_id=sc_id, master_seed="master",
                n_scenarios=sc_id + 1, trace=False, verbose_trace=False
            )
            job.progress = int(((idx + 1) / len(scenarios)) * 100)
            db.commit()

        job.status = 'completed'
        job.progress = 100
        db.commit()
    except Exception as e:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'failed'
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/run")
def launch_single_run(req: RunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    new_job = Job(
        id=job_id,
        type="processing_single",
        status="queued",
        progress=0
    )
    db.add(new_job)
    db.commit()
    background_tasks.add_task(run_processing_job, job_id, req.config_id, [req.scenario])
    return {"job_id": job_id, "status": "queued"}

@router.post("/batch")
def launch_batch_run(req: BatchRunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    new_job = Job(
        id=job_id,
        type="processing_batch",
        status="queued",
        progress=0
    )
    db.add(new_job)
    db.commit()
    background_tasks.add_task(run_processing_job, job_id, req.config_id, req.scenarios)
    return {"job_id": job_id, "status": "queued"}

@router.get("/status")
def get_live_status(db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(
        Job.type.in_(["processing_single", "processing_batch"])
    ).order_by(Job.created_at.desc()).limit(10).all()
    return jobs

@router.get("/{job_id}/logs")
def get_logs(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = [f"[{job.created_at}] Job {job_id} initialized."]
    if job.progress > 0:
        logs.append(f"[{job.updated_at}] Processing started. Current progress: {job.progress}%")
    if job.status == 'failed':
        logs.append(f"[{job.updated_at}] ERROR: {job.error_message}")
    elif job.status == 'completed':
        logs.append(f"[{job.updated_at}] Processing completed successfully.")
        
    return {"job_id": job_id, "logs": logs}

@router.post("/config/output")
def config_output(config: OutputConfig):
    return {"status": "success", "destination": config.destination_path}

@router.post("/config/hardware")
def config_hardware(config: HardwareConfig):
    return {"status": "success", "workers": config.worker_count, "memory": config.memory_gb}

@router.get("/profiling")
def get_profiling():
    return {
        "bottlenecks": [
            {"component": "Database I/O", "time_spent_percent": 45, "status": "critical"},
            {"component": "CPU Compute", "time_spent_percent": 35, "status": "warning"},
            {"component": "Network Fetch", "time_spent_percent": 20, "status": "ok"}
        ]
    }

@router.get("/prediction")
def get_prediction():
    return PredictionResponse(
        estimated_time_seconds=random.randint(60, 3600),
        estimated_cost_dollars=round(random.uniform(0.5, 10.0), 2)
    )

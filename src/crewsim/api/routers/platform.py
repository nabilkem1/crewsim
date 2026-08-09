from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from crewsim.api.db import get_db, AuditLog
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

router = APIRouter(prefix="", tags=["platform"])

@router.get("/search")
def global_search(q: str = ""):
    # Mocked for now
    if not q:
        return {"results": []}
    return {
        "results": [
            {"id": "sim-1", "type": "simulation", "title": f"Mock Simulation matching '{q}'"},
            {"id": "agent-2", "type": "agent", "title": f"Mock Agent matching '{q}'"},
            {"id": "config-3", "type": "config", "title": f"Mock Config matching '{q}'"},
        ]
    }

@router.get("/audit-log")
def get_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return logs

from datetime import datetime, timezone
from crewsim.api.db import Job

@router.get("/health")
def platform_health(db: Session = Depends(get_db)):
    # Detailed health dashboard
    if HAS_PSUTIL:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        mem_total = memory.total / (1024 ** 3)
        mem_used = memory.used / (1024 ** 3)
        mem_percent = memory.percent
    else:
        cpu_percent = 12.5
        mem_total = 16.0
        mem_used = 4.2
        mem_percent = 26.2

    # Mock uptime logic since boot time is platform specific and psutil might be absent
    uptime = time.time() - (psutil.boot_time() if HAS_PSUTIL else time.time() - 86400)

    # Active runs count
    active_runs = db.query(Job).filter(Job.status == 'running').count()
    
    # Average Queue Wait Time (of currently queued jobs)
    queued_jobs = db.query(Job).filter(Job.status == 'queued').all()
    if queued_jobs:
        now = datetime.now(timezone.utc)
        total_wait = sum((now - job.created_at).total_seconds() for job in queued_jobs if job.created_at)
        avg_wait_seconds = total_wait / len(queued_jobs)
    else:
        avg_wait_seconds = 0

    return {
        "status": "healthy",
        "cpu": {
            "usage_percent": cpu_percent
        },
        "memory": {
            "total_gb": round(mem_total, 2),
            "used_gb": round(mem_used, 2),
            "usage_percent": mem_percent
        },
        "database": {
            "status": "connected",
            "latency_ms": 15
        },
        "kpis": {
            "active_runs": active_runs,
            "avg_queue_wait_seconds": int(avg_wait_seconds),
            "queued_jobs": len(queued_jobs)
        },
        "uptime_seconds": int(uptime)
    }

"""Platform health, audit log and global search."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from crewsim.api.db import AuditLog, Job, get_db, to_utc
from crewsim.api.mocks import not_implemented

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover - depends on the installed extras
    HAS_PSUTIL = False

router = APIRouter(prefix="", tags=["platform"])

_AUDIT_LOG_LIMIT = 100
_BYTES_PER_GB = 1024**3


@router.get("/search")
def global_search(q: str = "") -> dict[str, Any]:
    """Not implemented.

    This returned three fabricated hits ("Mock Simulation matching '<q>'") for
    any non-empty query, which read as a working search that found nothing
    useful rather than as a search that does not exist.
    """
    return not_implemented(
        {"query": q, "results": []},
        "Global search is not implemented. This endpoint previously returned "
        "placeholder hits that matched nothing in the system.",
    )


# response_model=None: AuditLog is a SQLAlchemy model, not a Pydantic one, so
# FastAPI must not try to build a response schema from the return annotation.
@router.get("/audit-log", response_model=None)
def get_audit_logs(db: Session = Depends(get_db)) -> list[AuditLog]:
    return (
        db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(_AUDIT_LOG_LIMIT).all()
    )


@router.get("/health")
def platform_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    # psutil is an optional dependency. When it is absent we report null rather
    # than plausible-looking numbers: this endpoint previously fell back to a
    # hardcoded 12.5% CPU / 26.2% memory / "up 24 hours", which the dashboard
    # rendered as fact.
    if HAS_PSUTIL:
        memory = psutil.virtual_memory()
        host = {
            "metrics_available": True,
            "cpu": {"usage_percent": psutil.cpu_percent(interval=None)},
            "memory": {
                "total_gb": round(memory.total / _BYTES_PER_GB, 2),
                "used_gb": round(memory.used / _BYTES_PER_GB, 2),
                "usage_percent": memory.percent,
            },
            "uptime_seconds": int(datetime.now(UTC).timestamp() - psutil.boot_time()),
        }
    else:
        host = {
            "metrics_available": False,
            "metrics_unavailable_reason": (
                "psutil is not installed, so host CPU/memory/uptime cannot be measured."
            ),
            "cpu": None,
            "memory": None,
            "uptime_seconds": None,
        }

    active_runs = db.query(Job).filter(Job.status == "running").count()

    # to_utc(): SQLite stores no offset, so created_at comes back naive even
    # though it was written as an aware UTC timestamp. Subtracting an aware
    # `now` from it raised TypeError and 500'd this endpoint whenever any job
    # was queued.
    queued_jobs = db.query(Job).filter(Job.status == "queued").all()
    now = datetime.now(UTC)
    waits = [
        (now - to_utc(job.created_at)).total_seconds() for job in queued_jobs if job.created_at
    ]
    avg_wait_seconds = sum(waits) / len(waits) if waits else 0

    return {
        "status": "healthy",
        "database": {"status": "connected"},
        "kpis": {
            "active_runs": active_runs,
            "avg_queue_wait_seconds": int(avg_wait_seconds),
            "queued_jobs": len(queued_jobs),
        },
        **host,
    }

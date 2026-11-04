"""SQLite metadata store for the web API.

Timestamps: columns are written as timezone-aware UTC but SQLite's DATETIME
carries no offset, so every value reads back *naive*. Mixing the two raised
`TypeError: can't subtract offset-naive and offset-aware datetimes` and 500'd
the health endpoint. Anything doing arithmetic on a stored timestamp must put
it through `to_utc()` first.

Job execution: jobs run in FastAPI `BackgroundTasks`, i.e. inside the API
process. That is a deliberate MVP trade with real consequences -- a restart
loses in-flight work, and cancellation is only observed between progress
ticks. `reconcile_orphaned_jobs()` runs at startup so a job killed by a restart
is marked failed rather than sitting at "running" forever. Moving to a real
queue is the fix when that trade stops paying.
"""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from sqlalchemy import JSON as SAJSON
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    """Attach UTC to a timestamp read back from SQLite.

    Stored values are naive because the column has no offset; values that are
    already aware pass through unchanged.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Job(Base):
    """Async background jobs for long-running simulation/calibration tasks."""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    type = Column(String)  # 'processing_single', 'processing_batch', 'calibration'
    status = Column(String)  # 'queued', 'running', 'completed', 'failed', 'cancelled'
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    error_message = Column(String, nullable=True)
    # The RESOLVED season this job runs against, recorded when it is queued
    # rather than derived from `results` afterwards -- `results` is null until
    # a job completes, so a queued, running or failed job would otherwise have
    # no season to show at exactly the moments you most want to know which one
    # it was.
    season = Column(String, nullable=True)
    results = Column(SAJSON, nullable=True)
    diagnostics = Column(SAJSON, nullable=True)
    # Structured execution log: a list of step records the worker appends to as
    # it goes, streamed to the UI by /api/processing/{id}/stream.
    log = Column(SAJSON, nullable=True)


class Run(Base):
    """Historical simulation runs."""

    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)
    config_hash = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=_utc_now)
    results_url = Column(String, nullable=True)
    metrics = Column(SAJSON, nullable=True)


class AuditLog(Base):
    """System audit log for tracking actions."""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=_utc_now)
    actor = Column(String)
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    details = Column(SAJSON, nullable=True)


DATABASE_URL = "sqlite:///./crewsim_metadata.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ORPHANED_JOB_MESSAGE = (
    "Interrupted: the API process exited while this job was running. Background "
    "jobs do not survive a restart -- see db.py for why."
)


def reconcile_orphaned_jobs() -> int:
    """Fail any job left mid-flight by a previous process.

    Without this a killed job stays 'running' forever and the health endpoint
    counts it as an active run indefinitely.
    """
    db = SessionLocal()
    try:
        orphans = db.query(Job).filter(Job.status.in_(("running", "queued"))).all()
        for job in orphans:
            job.status = "failed"
            job.error_message = ORPHANED_JOB_MESSAGE
        db.commit()
        return len(orphans)
    finally:
        db.close()


def _add_missing_columns() -> None:
    """Add columns that exist on the model but not yet in the SQLite file.

    `create_all` creates missing *tables* and silently ignores existing ones,
    so a column added to a model after the database file exists never appears
    -- the next query then fails with "no such column" against a schema that
    looks correct in the source. This project has no migration tool and one
    local SQLite file, so the narrow fix is the honest one: ADD COLUMN for
    what is missing. It handles only additions, which is all that has been
    needed; a rename or a type change still requires a real migration.
    """
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
            with engine.begin() as conn:
                conn.execute(text(ddl))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    reconcile_orphaned_jobs()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_job_or_404(job_id: str, db: Session) -> Job:
    """The job row, or HTTP 404. IMP-612: shared by every router (there were three copies)."""
    from fastapi import HTTPException

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Job not found")
    return job


def record_job_failure(
    db: Session, job_id: str, exc: BaseException, total_steps: int | None = None,
    **extra_log_fields: Any,
) -> None:
    """Mark a job failed and, if `total_steps` is given, close its execution log.

    IMP-612: the worker failure path, shared by the processing and calibration
    routers (it was copied in each). The last "running" log entry is marked
    "failed" and an "error" entry is appended, so the live stream shows where
    the job stopped rather than just going quiet. `extra_log_fields` carries
    keys a router's log entries always have (calibration's progress/artifact
    columns), so every entry in one log has the same shape.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    job.status = "failed"
    job.error_message = str(exc)
    if total_steps is not None:
        entries = list(job.log or [])
        if entries and entries[-1].get("status") == "running":
            entries[-1] = {**entries[-1], "status": "failed"}
        entries.append({
            "step": None,
            "total": total_steps,
            "message": str(exc),
            "detail": None,
            "status": "error",
            "duration_ms": None,
            **extra_log_fields,
        })
        job.log = entries
    db.commit()

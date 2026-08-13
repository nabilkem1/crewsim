"""Server-sent events for a job's progress and execution log.

Shared by the processing and calibration routers so both stream on identical
terms -- and so a fix to the termination or session handling lands in one
place rather than in two copies that drift.

Honest about the mechanism: jobs run in FastAPI `BackgroundTasks` and write to
SQLite, so this *polls the job row* and emits an event whenever it changes.
Nothing is pushed from the worker. It is still a real improvement on a client
that blind-polls every job on a timer -- the browser holds one connection, sees
a change within `POLL_SECONDS` of it being committed, and receives the
structured step log rather than a status integer.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from .db import Job, SessionLocal

TERMINAL_STATUSES = ("completed", "failed", "cancelled")

# How often the job row is re-read. A poll interval, not a push latency.
POLL_SECONDS = 0.5
# A stream on a job that never reaches a terminal state must not run forever.
TIMEOUT_SECONDS = 3600


def job_event(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "log": job.log or [],
        "error_message": job.error_message,
    }


def _sse_raw(payload: str, event: str = "message") -> str:
    return f"event: {event}\ndata: {payload}\n\n"


def _sse(payload: dict[str, Any], event: str = "message") -> str:
    return _sse_raw(json.dumps(payload), event=event)


def stream_job(job_id: str) -> StreamingResponse:
    """SSE for one job, terminating on a terminal status, a missing job, or
    `TIMEOUT_SECONDS` -- never spinning forever."""

    async def event_stream() -> AsyncIterator[str]:
        last_payload: str | None = None
        deadline = time.monotonic() + TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            # A fresh session per poll, not a request-scoped `Depends(get_db)`
            # one: a session held open for the lifetime of a stream pins a
            # connection and serves increasingly stale reads from its own
            # transaction snapshot.
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job is None:
                    yield _sse({"error": "Job not found", "job_id": job_id}, event="error")
                    return
                payload = json.dumps(job_event(job))
                status = job.status
            finally:
                db.close()

            if payload != last_payload:
                last_payload = payload
                yield _sse_raw(payload)

            if status in TERMINAL_STATUSES:
                yield _sse({"job_id": job_id, "status": status}, event="end")
                return

            await asyncio.sleep(POLL_SECONDS)

        yield _sse({"job_id": job_id, "reason": "stream timeout"}, event="end")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Without this a proxy in front would buffer the stream and deliver
            # every event at once when the job ends.
            "X-Accel-Buffering": "no",
        },
    )

"""Run summaries and generated artifacts.

Scope note: this router used to carry `/metrics/comparison` and eight
`/charts/*` endpoints. Every one of them returned hardcoded literals describing
a different product entirely -- a hiring funnel under `/charts/gates`, CPU and
memory series under `/charts/timeseries`, "Alpha Node"/"Beta Node" under
`/charts/grid`. They were deleted rather than filled in: the real quantities
live in `crewsim.reporting` and `crewsim.gates`, and wiring fabricated response
shapes to real numbers would have baked in a contract nobody designed.

What is left is the part that was always real -- it reads the job table and the
configured output directories, and invents nothing.
"""

from __future__ import annotations

import csv
import html
import mimetypes
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from crewsim import config
from crewsim.api.db import Job, get_db

router = APIRouter(prefix="", tags=["results"])

# Structural, not simulation parameters: how many rows the dashboard asks for,
# and the byte arithmetic for a megabyte.
_SUMMARY_LIMIT = 20
_BYTES_PER_MB = 1024 * 1024


@router.get("/summaries")
def get_run_summaries(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    jobs = (
        db.query(Job)
        .filter(Job.type.like("processing%"))
        .order_by(Job.created_at.desc())
        .limit(_SUMMARY_LIMIT)
        .all()
    )
    return [
        {
            "id": j.id,
            "name": f"Processing Run ({j.type})",
            "type": j.type,
            "status": j.status,
            # Both timestamps come back from SQLite naive, so this subtraction is
            # well-defined -- see db.py's note on why they are stored that way.
            "duration": str(j.updated_at - j.created_at) if j.updated_at else None,
            "created_at": j.created_at.isoformat(),
            # True only for a completed 'processing_batch' job -- the one job
            # type that carries a policy-comparison scoreboard (see /{job_id}
            # below). A single-policy run or an incomplete/failed job has no
            # comparison to show.
            "has_comparison": j.type == "processing_batch" and j.status == "completed",
        }
        for j in jobs
    ]


@router.get("/artifacts")
def get_artifacts() -> list[dict[str, Any]]:
    cfg = config.load()
    artifacts = []
    for d in (cfg.paths.reports_dir, cfg.paths.params_dir):
        if not d.exists():
            continue
        for idx, f in enumerate(sorted(d.glob("*"))):
            if not f.is_file():
                continue
            artifacts.append(
                {
                    "id": f"art-{d.name}-{idx}",
                    "filename": f.name,
                    "type": f.suffix.lstrip("."),
                    "size_mb": round(os.path.getsize(f) / _BYTES_PER_MB, 2),
                    "url": f"/api/results/artifacts/download/{f.name}",
                }
            )
    return artifacts


def _render_csv(file_path) -> str:
    """CSV as an HTML table. Every cell is escaped: these files are generated
    from customer data extracts, and this response is served as text/html from
    the app's own origin."""
    rows = []
    with open(file_path, encoding="utf-8") as f:
        for i, row in enumerate(csv.reader(f)):
            tag = "th" if i == 0 else "td"
            cells = "".join(f"<{tag}>{html.escape(col)}</{tag}>" for col in row)
            rows.append(f"<tr>{cells}</tr>")
    style = (
        "table { border-collapse: collapse; width: 100%; font-family: sans-serif; } "
        "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; } "
        "th { background-color: #f2f2f2; }"
    )
    return f"<html><head><style>{style}</style></head><body><table>{''.join(rows)}</table></body></html>"


def _render_text(file_path) -> str:
    style = (
        "pre { background: #f4f4f4; padding: 16px; border-radius: 8px; "
        "overflow: auto; font-family: monospace; }"
    )
    content = html.escape(file_path.read_text(encoding="utf-8"))
    return f"<html><head><style>{style}</style></head><body><pre>{content}</pre></body></html>"


@router.get("/artifacts/download/{filename}")
def download_artifact(filename: str, raw: bool = False):
    """Serve a generated artifact.

    Two modes, because "look at this" and "give me the file" are different
    jobs and the rendered one cannot do the second. By default the response is
    a readable HTML view -- a CSV becomes a table, JSON/YAML is escaped into a
    <pre>. With `?raw=1` the original bytes are returned as an attachment, so
    saving `params_v0.1.0_winter_sun.json` yields the parameter store itself
    rather than an HTML page wrapped around a pretty-printed copy of it.
    """
    cfg = config.load()

    # Only ever the configured output directories, and only a direct child of
    # one: `filename` is a path parameter, so Starlette will not match a
    # separator, and resolve() below refuses anything that escapes anyway.
    file_path = None
    for d in (cfg.paths.reports_dir, cfg.paths.params_dir):
        candidate = (d / filename).resolve()
        if candidate.is_file() and candidate.parent == d.resolve():
            file_path = candidate
            break

    if file_path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Dispatch on media type rather than on a suffix literal: only config.py is
    # allowed to know how a dataset is stored on disk
    # (tests/test_project_structure.py::test_dataset_suffixes_have_one_authority).
    mime, _ = mimetypes.guess_type(file_path.name)

    if raw:
        return FileResponse(
            path=file_path,
            media_type=mime or "application/octet-stream",
            filename=file_path.name,
        )

    if mime == "text/html":
        return FileResponse(
            path=file_path, media_type="text/html", headers={"Content-Disposition": "inline"}
        )
    if mime == "text/csv":
        return HTMLResponse(content=_render_csv(file_path))
    return HTMLResponse(content=_render_text(file_path))


# Declared LAST and after every other /results/... route above: FastAPI
# matches path operations in declaration order, and this catch-all path
# parameter would otherwise swallow /summaries, /artifacts, etc. as a
# job_id of "summaries".
@router.get("/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """A processing job's full detail, including the real `results` payload
    (scoreboard, pairwise comparisons, gate V3 verdict, R* recommendation)
    `run_processing_job` computes and stores -- previously written to the
    database and never read back by any endpoint. `/summaries` stays a light
    list; this is what Results & Reports fetches once a job is selected.
    """
    job = db.query(Job).filter(Job.id == job_id, Job.type.like("processing%")).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "error_message": job.error_message,
        "results": job.results,
    }

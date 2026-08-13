"""CrewSim web API.

Router inventory note: `provenance.py`, `runs.py` and the chart half of
`results.py` used to be mounted here. All of it returned hardcoded literals
describing a different product -- `learning_rate`/`batch_size`/`s3://` under
provenance, a `MOCK_RUNS` list under runs, a hiring funnel under
`/results/charts/gates`. They were deleted rather than wired up, because the
response shapes were never designed against this system. See
`CODE_REVIEW_API_WEBUI.md`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .db import init_db
from .routers import analytics, calibration, config, data, jobs, platform, processing, results

# The Vite dev server. Its proxy forwards /api to this app, so the browser's
# origin is the dev server, not the API.
DEV_ORIGIN = "http://localhost:5173"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="CrewSim API",
    description="API for Air Transat Crew Reserve & Drafting Policy Optimization System",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(config.router, prefix="/api/config", tags=["Configuration"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(data.router, prefix="/api/data", tags=["Data Quality"])
app.include_router(platform.router, prefix="/api/platform", tags=["Platform"])
app.include_router(calibration.router, prefix="/api/calibration", tags=["Calibration"])
app.include_router(processing.router, prefix="/api/processing", tags=["Processing"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Cascade Analytics"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DEV_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {"status": "ok", "service": "CrewSim API"}


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

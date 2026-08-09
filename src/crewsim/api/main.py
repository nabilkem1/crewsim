from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from .db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

from .routers import config, jobs, data, platform, calibration, processing, results, runs, analytics, provenance

app = FastAPI(
    title="CrewSim API",
    description="API for Air Transat Crew Reserve & Drafting Policy Optimization System",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(config.router, prefix="/api/config", tags=["Configuration"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(data.router, prefix="/api/data", tags=["Data Quality"])
app.include_router(platform.router, prefix="/api/platform", tags=["Platform"])
app.include_router(calibration.router, prefix="/api/calibration", tags=["Calibration"])
app.include_router(processing.router, prefix="/api/processing", tags=["Processing"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(runs.router, prefix="/api/runs", tags=["Run Management"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Cascade Analytics"])
app.include_router(provenance.router, prefix="/api", tags=["Comparison & Provenance"])

# Allow CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "CrewSim API"}

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

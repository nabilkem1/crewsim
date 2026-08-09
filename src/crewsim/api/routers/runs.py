from fastapi import APIRouter, Query, Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

router = APIRouter(prefix="", tags=["runs"])

# Mock data store
MOCK_RUNS = [
    {
        "id": "run-123",
        "name": "Initial Simulation",
        "status": "COMPLETED",
        "created_at": "2026-08-01T10:00:00Z",
        "updated_at": "2026-08-01T10:30:00Z",
        "duration": 1800,
        "configuration": {"agents": 5, "environment": "dev"}
    },
    {
        "id": "run-124",
        "name": "Stress Test A",
        "status": "FAILED",
        "created_at": "2026-08-02T14:00:00Z",
        "updated_at": "2026-08-02T14:15:00Z",
        "duration": 900,
        "configuration": {"agents": 50, "environment": "prod-like"}
    },
    {
        "id": "run-125",
        "name": "Nightly Build Run",
        "status": "RUNNING",
        "created_at": "2026-08-08T19:00:00Z",
        "updated_at": "2026-08-08T19:45:00Z",
        "duration": None,
        "configuration": {"agents": 10, "environment": "test"}
    }
]

@router.get("/runs")
async def get_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    filtered_runs = MOCK_RUNS
    
    if status:
        filtered_runs = [r for r in filtered_runs if r["status"].lower() == status.lower()]
        
    if search:
        search_lower = search.lower()
        filtered_runs = [r for r in filtered_runs if search_lower in r["name"].lower() or search_lower in r["id"].lower()]
        
    total = len(filtered_runs)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "data": filtered_runs[start:end],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    }

@router.get("/runs/{run_id}")
async def get_run_details(run_id: str):
    run = next((r for r in MOCK_RUNS if r["id"] == run_id), None)
    if run:
        return run
    return {"error": "Run not found"}, 404

@router.get("/runs/{run_id}/status")
async def get_run_status(run_id: str):
    run = next((r for r in MOCK_RUNS if r["id"] == run_id), None)
    if run:
        return {"id": run["id"], "status": run["status"]}
    return {"error": "Run not found"}, 404

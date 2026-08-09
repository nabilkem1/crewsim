from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from crewsim.api.db import get_db, Job

router = APIRouter(prefix="", tags=["results"])

@router.get("/summaries")
def get_run_summaries(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    jobs = db.query(Job).filter(Job.type.like('processing%')).order_by(Job.created_at.desc()).limit(20).all()
    summaries = []
    for j in jobs:
        summaries.append({
            "id": j.id,
            "name": f"Processing Run ({j.type})",
            "status": j.status,
            "duration": str(j.updated_at - j.created_at) if j.updated_at else "0s",
            "total_events": 0, # Could be parsed from logs if needed
            "success_rate": 1.0 if j.status == 'completed' else 0.0,
            "created_at": j.created_at.isoformat()
        })
    return summaries

@router.get("/artifacts")
def get_artifacts() -> List[Dict[str, Any]]:
    from crewsim import config
    import os
    
    cfg = config.load()
    artifacts = []
    
    for d in [cfg.paths.reports_dir, cfg.paths.params_dir]:
        if not d.exists():
            continue
        for idx, f in enumerate(d.glob("*")):
            if f.is_file():
                artifacts.append({
                    "id": f"art-{d.name}-{idx}",
                    "run_id": "auto",
                    "filename": f.name,
                    "type": f.suffix.lstrip("."),
                    "size_mb": round(os.path.getsize(f) / (1024 * 1024), 2),
                    "url": f"/api/results/artifacts/download/{f.name}"
                })
                
    return artifacts

@router.get("/metrics/comparison")
def get_metric_comparisons() -> Dict[str, Any]:
    return {
        "metrics": ["throughput", "latency", "error_rate"],
        "runs": ["run-001", "run-002"],
        "data": {
            "throughput": {"run-001": 150.5, "run-002": 310.2},
            "latency": {"run-001": 45.2, "run-002": 120.8},
            "error_rate": {"run-001": 0.02, "run-002": 0.15}
        }
    }

@router.get("/charts/gantt")
def get_gantt_data() -> List[Dict[str, Any]]:
    return [
        {"task": "Initialization", "start": "2026-08-01T10:00:00Z", "end": "2026-08-01T10:05:00Z", "resource": "System"},
        {"task": "Data Processing", "start": "2026-08-01T10:05:00Z", "end": "2026-08-01T10:30:00Z", "resource": "Worker 1"},
        {"task": "Report Generation", "start": "2026-08-01T10:30:00Z", "end": "2026-08-01T10:45:00Z", "resource": "Worker 2"}
    ]

@router.get("/charts/waterfall")
def get_waterfall_data() -> List[Dict[str, Any]]:
    return [
        {"category": "Initial Capacity", "value": 1000, "type": "total"},
        {"category": "New Allocations", "value": 250, "type": "positive"},
        {"category": "Deallocations", "value": -150, "type": "negative"},
        {"category": "System Overhead", "value": -50, "type": "negative"},
        {"category": "Final Capacity", "value": 1050, "type": "total"}
    ]

@router.get("/charts/heatmap")
def get_heatmap_data() -> Dict[str, Any]:
    return {
        "x_labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "y_labels": ["Morning", "Afternoon", "Evening"],
        "values": [
            [10, 25, 15, 30, 45],
            [20, 35, 40, 50, 60],
            [5, 10, 15, 20, 25]
        ]
    }

@router.get("/charts/timeseries")
def get_timeseries_data() -> Dict[str, Any]:
    return {
        "timestamps": ["10:00", "10:10", "10:20", "10:30", "10:40", "10:50"],
        "series": [
            {"name": "CPU Usage", "data": [45, 50, 55, 80, 65, 40]},
            {"name": "Memory Usage", "data": [30, 32, 35, 40, 38, 35]}
        ]
    }

@router.get("/charts/eligibility")
def get_eligibility_data() -> Dict[str, Any]:
    return {
        "eligible": 8500,
        "ineligible": 1500,
        "reasons": [
            {"reason": "Missing Credentials", "count": 800},
            {"reason": "Expired License", "count": 500},
            {"reason": "Age Restriction", "count": 200}
        ]
    }

@router.get("/charts/grid")
def get_grid_explorer_data() -> List[Dict[str, Any]]:
    return [
        {"id": "G-01", "name": "Alpha Node", "status": "Active", "load": 45.2},
        {"id": "G-02", "name": "Beta Node", "status": "Inactive", "load": 0.0},
        {"id": "G-03", "name": "Gamma Node", "status": "Active", "load": 88.5},
        {"id": "G-04", "name": "Delta Node", "status": "Warning", "load": 95.0}
    ]

@router.get("/charts/gates")
def get_gates_dashboard_data() -> List[Dict[str, Any]]:
    return [
        {"gate": "Initial Screening", "passed": 10000, "failed": 500, "rate": 0.95},
        {"gate": "Background Check", "passed": 9200, "failed": 800, "rate": 0.92},
        {"gate": "Technical Interview", "passed": 4600, "failed": 4600, "rate": 0.50},
        {"gate": "Final Review", "passed": 4140, "failed": 460, "rate": 0.90}
    ]

@router.get("/charts/data-quality")
def get_data_quality_data() -> Dict[str, Any]:
    return {
        "dimensions": ["Completeness", "Validity", "Accuracy", "Consistency"],
        "scores": [98.5, 95.0, 92.3, 99.1]
    }

from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="", tags=["Provenance"])

@router.get("/provenance/{run_id}/lineage")
def get_provenance_lineage(run_id: str):
    return {
        "run_id": run_id,
        "lineage": [
            {"id": f"{run_id}-p1", "type": "calibration", "timestamp": "2026-08-01T10:00:00Z", "status": "completed"},
            {"id": f"{run_id}-p2", "type": "simulation", "timestamp": "2026-08-02T11:00:00Z", "status": "completed"},
            {"id": run_id, "type": "analysis", "timestamp": "2026-08-03T12:00:00Z", "status": "completed"}
        ]
    }

@router.get("/provenance/{run_id}/snapshot")
def get_effective_config_snapshot(run_id: str):
    return {
        "run_id": run_id,
        "effective_config": {
            "model_version": "v1.2.3",
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100
            },
            "data_source": "s3://bucket/data.csv",
            "random_seed": 42
        }
    }

@router.get("/provenance/{run_id}/reproducibility")
def get_reproducibility_details(run_id: str):
    return {
        "run_id": run_id,
        "reproducibility_score": 0.95,
        "docker_image": "crewsim:latest",
        "git_commit": "abcdef1234567890",
        "environment_variables": ["API_KEY=***", "DEBUG=True"]
    }

@router.get("/provenance/{run_id}/tracing")
def get_result_tracing(run_id: str):
    return {
        "run_id": run_id,
        "traces": [
            {"step": "data_loading", "duration_ms": 1500, "status": "success"},
            {"step": "preprocessing", "duration_ms": 3200, "status": "success"},
            {"step": "model_inference", "duration_ms": 45000, "status": "success"}
        ]
    }

@router.get("/provenance/{run_id}/explain")
def get_explain_commands(run_id: str):
    return {
        "run_id": run_id,
        "explanation": "This run was triggered by a scheduled job. It used the latest model weights from the registry.",
        "commands": [
            {"command": "crewsim run --config config.yaml", "description": "The main command used to start the run."},
            {"command": "crewsim analyze --run-id " + run_id, "description": "The command used to generate these results."}
        ]
    }

@router.get("/comparison/side-by-side")
def get_side_by_side_comparison(run_a: str, run_b: str):
    return {
        "run_a": run_a,
        "run_b": run_b,
        "comparison": {
            "metrics": [
                {"name": "accuracy", "run_a": 0.85, "run_b": 0.88, "difference": 0.03},
                {"name": "loss", "run_a": 0.45, "run_b": 0.35, "difference": -0.10}
            ]
        }
    }

@router.get("/comparison/diff")
def get_config_diff(run_a: str, run_b: str):
    return {
        "run_a": run_a,
        "run_b": run_b,
        "diff": [
            {"key": "learning_rate", "run_a": 0.001, "run_b": 0.005},
            {"key": "batch_size", "run_a": 32, "run_b": 64}
        ]
    }

@router.get("/comparison/t-test")
def get_statistical_t_test(run_a: str, run_b: str, metric: str = "accuracy"):
    return {
        "run_a": run_a,
        "run_b": run_b,
        "metric": metric,
        "t_statistic": -2.45,
        "p_value": 0.015,
        "significant": True
    }

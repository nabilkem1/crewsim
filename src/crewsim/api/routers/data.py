from fastapi import APIRouter

router = APIRouter(prefix="", tags=["Data Quality"])

@router.get("/quality-report")
def get_data_quality_report():
    """
    Wraps the CLI capability `crewsim data quality-report`.
    Returns a mocked report for now.
    """
    return {
        "status": "success",
        "report": {
            "overall_score": 95,
            "checks": [
                {
                    "name": "Missing Values",
                    "status": "passed",
                    "details": "No missing values found across critical tables."
                },
                {
                    "name": "Data Types",
                    "status": "passed",
                    "details": "All column data types match the defined schema."
                },
                {
                    "name": "Outliers",
                    "status": "warning",
                    "details": "Found potential outliers in simulation historical inputs."
                },
                {
                    "name": "Data Dependencies",
                    "status": "passed",
                    "details": "All dependent datasets for simulation are present and up-to-date."
                }
            ]
        }
    }

@router.get("/datasets")
def list_datasets():
    """List available datasets in the configured corpus directory."""
    from crewsim.config import load, DATASET_SUFFIXES
    cfg = load()
    corpus = cfg.paths.corpus_dir
    
    if not corpus.exists():
        return {"datasets": []}
        
    datasets = []
    for suffix in DATASET_SUFFIXES:
        datasets.extend([p.name for p in corpus.glob(f"*{suffix}")])
    
    return {"datasets": sorted(list(set(datasets)))}

from fastapi.responses import HTMLResponse

@router.get("/profile-report", response_class=HTMLResponse)
def get_data_profile_report():
    """Generate and return the S0-02b data profile HTML report."""
    from crewsim.config import load
    from crewsim.data.profile import compute_profiles
    from crewsim.data.profile_html import render
    cfg = load()
    profiles = compute_profiles(cfg)
    html = render(profiles, cfg.calibration.overdispersion_threshold)
    return html

import subprocess
import json
import os
import shutil
from pathlib import Path
from crewsim import config

def test_scenario_generation():
    """Verify scenario caching keyed by params content hash."""
    cfg = config.load()
    params_dir = config.resolve(cfg, "params_dir")
    scen_dir = params_dir / "scenarios"
    if scen_dir.exists():
        shutil.rmtree(scen_dir)
        
    # We must have parameters to generate scenarios.
    # We'll just invoke calibration on winter_sun first if not present, but 
    # since we want this test to be robust, let's just use the CLI.
    
    # 1. Run calibration to generate params
    subprocess.run(["uv", "run", "crewsim", "calibrate", "winter_sun"], capture_output=True)
    
    # 2. Generate scenarios
    res1 = subprocess.run(
        ["uv", "run", "crewsim", "scenarios", "generate", "--scenarios", "10", "--master-seed", "testseed1", "--season", "winter_sun"],
        capture_output=True, text=True
    )
    assert res1.returncode == 0
    assert "Generated scenarios successfully" in res1.stdout
    
    # 3. Generate again with exact same params and seed -> cache hit
    res2 = subprocess.run(
        ["uv", "run", "crewsim", "scenarios", "generate", "--scenarios", "10", "--master-seed", "testseed1", "--season", "winter_sun"],
        capture_output=True, text=True
    )
    assert res2.returncode == 0
    assert "Cache hit" in res2.stdout

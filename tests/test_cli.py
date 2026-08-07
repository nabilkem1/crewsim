import subprocess

def test_cli_compare():
    """Test that the compare command works and calculates paired statistics."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "compare", "--policies", "R6", "R10", "--scenarios", "100"],
        capture_output=True, text=True
    )
    
    assert result.returncode == 0
    assert "Comparing R6 vs R10 over 100 scenarios (CRN):" in result.stdout
    assert "Mean Difference" in result.stdout
    assert "95% CI" in result.stdout
    assert "t-statistic" in result.stdout

def test_cli_explain_cost():
    """Test that explain-cost command works."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "explain-cost", "--policy", "R6", "--category", "RESERVE_STAFFING", "--summary"],
        capture_output=True, text=True
    )
    
    assert result.returncode == 0
    assert "measured-window total" in result.stdout

def test_cli_explain_draft():
    """Test that explain-draft command works."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "explain-draft"],
        capture_output=True, text=True
    )
    
    assert result.returncode == 0
    assert "Selected:" in result.stdout

import pytest
import subprocess

def test_calibrate_refuses_holdout():
    """Verify that the calibrator refuses to run on the holdout window."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "crewsim.cli", "calibrate", "--window", "holdout", "--emit"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "Refusing to calibrate on the holdout window" in result.stdout

def test_gate_refuses_fitting_without_flag():
    """Verify that validation gate refuses fitting window without explicit --i-know."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "crewsim.cli", "gate", "--window", "fitting"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "Refusing to run validation on the fitting window" in result.stdout
    assert "Use --i-know" in result.stdout

def test_gate_allows_fitting_with_flag():
    """Verify that validation gate allows fitting window when --i-know is passed."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "crewsim.cli", "gate", "--window", "fitting", "--i-know"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Gate validation passed" in result.stdout

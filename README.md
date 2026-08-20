# CrewSim

CrewSim is a Python command-line simulation project for crew reserve and drafting policy analysis.

This repository currently runs as a CLI application.
There is no separate backend API service and no separate frontend web app in this codebase today.

## 1) Prerequisites

- Windows PowerShell
- Python 3.11 or newer (project currently runs on 3.12 in this workspace)

## 2) Setup

From the project root:

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -e .
    .\.venv\Scripts\python.exe -m pip install pytest hypothesis ruff mypy types-PyYAML

Optional activation in PowerShell:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
    .\.venv\Scripts\Activate.ps1

Note:
If your venv folder is named .venv, activate with:

    .\.venv\Scripts\Activate.ps1

## 3) Start the app

Main app entry point:

    .\.venv\Scripts\crewsim.exe doctor

Alternative module form:

    .\.venv\Scripts\python.exe -m crewsim doctor

If everything is healthy, you should see all modules and datasets reported as passed.

## 4) Common commands

Health and config:

    .\.venv\Scripts\crewsim.exe doctor
    .\.venv\Scripts\crewsim.exe config show

Data checks:

    .\.venv\Scripts\crewsim.exe data head --dataset d2_rosters --rows 5
    .\.venv\Scripts\crewsim.exe data quality-report
    .\.venv\Scripts\crewsim.exe data profile --dataset d2_rosters

Calibration and scenarios:

    .\.venv\Scripts\crewsim.exe calibrate regime --season winter_sun --show-matrix
    .\.venv\Scripts\crewsim.exe scenarios generate --scenarios 100 --master-seed demo_seed --season winter_sun

Tests:

    .\.venv\Scripts\pytest.exe

## 5) Project layout (high level)

- src/crewsim: application package and CLI
- configs: base and policy configuration
- tests: automated test suite
- backlog: implementation stories and verification helpers

## 6) If you want backend API + frontend

That architecture is not scaffolded yet in this repo.
If you want, the next step can be:

- add a backend API (for example FastAPI)
- add a frontend app (for example React or Vue)
- connect the frontend to backend endpoints that trigger CrewSim runs and fetch reports

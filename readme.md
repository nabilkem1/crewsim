Backend (from the repo root):
PYTHONPATH=src uv run uvicorn crewsim.api.main:app --reload
Runs on http://localhost:8000 by default (add --port N to change it).

Frontend (from web_ui/):
npm run dev
Runs on http://localhost:5173 (Vite's default) and proxies /api to http://localhost:8000 per web_ui/vite.config.ts — so start the backend first, or on port 8000, or the frontend's API calls will fail.

Open http://localhost:5173 once both are up.
Real extract (Pierre's delivery, src/crewsim/data/corpus/real_datav2/v3):
$env:CREWSIM_CONFIG = "configs/real.yaml"      # PowerShell; applies to the CLI and to the API server
uv run crewsim data readiness                   # windows, scope, quality gates, and the "Limitations" of this load
uv run crewsim calibrate --season winter_sun --emit --window fitting
Output goes to output/real/, never over the mock's. Unset CREWSIM_CONFIG to go back to the mock corpus (the tests expect it).

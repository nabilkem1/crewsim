# CrewSim Web UI

This folder contains the React + Vite frontend for CrewSim.

The frontend expects a local FastAPI backend running on port 8000.

## Run locally

Open two terminals from the repo root.

1. Start backend API (Terminal 1)

```powershell
.\.venv\Scripts\uvicorn.exe crewsim.api.main:app --host 127.0.0.1 --port 8000
```

2. Start frontend website (Terminal 2)

```powershell
npm --prefix web_ui install
npm --prefix web_ui run dev -- --host 127.0.0.1 --port 5173
```

3. Open the app

- Web UI: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- API health: http://127.0.0.1:8000/api/health

## Why this works

- The API app is defined in [src/crewsim/api/main.py](../src/crewsim/api/main.py).
- Vite proxies /api to the backend in [web_ui/vite.config.ts](vite.config.ts).
- Some frontend calls target port 8000 directly in [web_ui/src/App.tsx](src/App.tsx).

## Build

```powershell
npm --prefix web_ui run build
```

## Troubleshooting

- If port 8000 is in use, stop the other process and restart API.
- If port 5173 is in use, pass a different port to Vite and update API URLs that are hard-coded.
- If API import errors appear, install backend deps into .venv:

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn sqlalchemy
```

# CrewSim web UI

React 19 + TypeScript + Vite front end for the CrewSim reserve-sizing simulator.
It is a thin client: every number it shows comes from the FastAPI backend in
`src/crewsim/api/`, which runs the same engine as the `crewsim` CLI.

## Run it locally

1. Start the API on port 8000 (from the repository root):

   ```
   uv run uvicorn crewsim.api.main:app --reload
   ```

2. Start the dev server (from `web_ui/`):

   ```
   npm ci
   npm run dev
   ```

   Open http://localhost:5173. Vite proxies every `/api/...` request to
   `http://localhost:8000` (`vite.config.ts`), so the backend must be up first.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload on :5173 |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/`. Run by CI. |
| `npm run lint` | `oxlint`. Run by CI. |
| `npm run preview` | Serve the built `dist/` locally |

## Talking to the API

- All requests go through `src/api/client.ts` (`apiFetch`). It takes a path
  below `/api`, uses relative URLs (so the Vite proxy and a same-origin deploy
  both work), and throws on any non-2xx response. A component must render an
  error state; it must never substitute placeholder data.
- Endpoints that exist but are not implemented return `implemented: false`
  with a `notice` and empty collections (`src/crewsim/api/mocks.py`). Check
  them with `isNotImplemented()` and show the notice, not an empty result.
- Long-running jobs (calibration, processing) stream progress over
  server-sent events from `/api/<area>/<job_id>/stream`.

## Layout

- `src/App.tsx`: shell, navigation and per-page help.
- `src/features/<area>/`: one folder per page (config, data, calibration,
  processing, results, analytics, jobs, platform).
- `src/components/`: shared UI pieces (status panels, execution log, ...).

## Tests

There is no unit-test runner here yet. Manual-only Playwright specs live in
`backlog/mvp/web/playwright-test-web-features/` (not run in CI).

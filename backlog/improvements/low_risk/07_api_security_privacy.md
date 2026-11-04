# IMP-E3 — API Security & Data Privacy

**6 stories** · **Low risk while the API runs on localhost only.** All six become must-fix before
the API is exposed to anyone else. IMP-301 is cheap and worth doing anyway.
Gate: a security test suite (`tests/api/test_security.py`) passes.
The must-fix IMP-303 (real data out of git and the wheel) is in [../03_api_security_privacy.md](../03_api_security_privacy.md).

The API is currently safe only because it runs on a developer laptop. Any deployment beyond
localhost exposes unauthenticated, CPU-heavy job creation, an arbitrary file read, and filesystem
layout leaks. Real personal data sits one `git add .` away from the repository.

---

## [TODO] IMP-301 — Policy names are restricted to the policies directory
**Size:** `S` | **Depends on:** — | **Source:** `reporting/grid.py:27-31`, `api/routers/processing.py:182,401,546,659-661,722`, `cli.py:293-303`

**As a** platform owner **I want** a policy reference to resolve only to `configs/policies/*.yaml`
**so that** an API client cannot make the server open arbitrary files.

### Acceptance Criteria
- [ ] One resolver, `resolve_policy(name) -> Path`, used by the CLI, the API and reporting. It replaces `_policy_path`, `_resolve_policy_path` and every inline `repo_root()/"configs"/"policies"/...`.
- [ ] API: the name must match `^[A-Za-z0-9_-]+$` and exist in the policies directory. Otherwise 422 with a generic message (no exception text, no path).
- [ ] The CLI may still accept an explicit file path (local user), behind an explicit check that it is used only from the CLI
- [ ] Tests reject `../x`, absolute Windows and POSIX paths, `%2e%2e`, and names with a `.yaml` suffix

### Verification
*   **Automated:** `pytest tests/api/test_security.py -k policy_path`
*   **Manual:** `curl -X POST localhost:8000/api/processing/batch -H "content-type: application/json" -d "{\"config_ids\":[\"../../pyproject\"]}"`
    *   **Expect:** HTTP 422, "unknown policy", with no file path or parser error in the body
    *   **Fails if:** the response mentions TOML/YAML or any filesystem path

---

## [TODO] IMP-302 — The API requires authentication
**Size:** `M` | **Depends on:** platform decision | **Source:** `api/main.py:43-58`, `.gitignore` (`api.key`)

**As a** platform owner **I want** every non-health endpoint to require a credential
**so that** only authorised users can start, cancel or delete jobs and read data.

### Acceptance Criteria
- [ ] Global FastAPI dependency enforcing the chosen scheme (API key header or Entra ID bearer token). Only `/api/health` is exempt.
- [ ] The credential comes from an environment variable or secret store. It is never committed or logged.
- [ ] State-changing requests require a custom header (e.g. `Authorization` or `X-API-Key`), which also closes the CSRF hole for body-less POSTs (`/cancel`, `/retry`, `/drilldown`)
- [ ] The web UI sends the credential, and a 401 shows a clear message
- [ ] CORS origins come from config, not a literal

### Verification
*   **Automated:** `pytest tests/api/test_security.py -k auth`
*   **Manual:** `curl -i localhost:8000/api/jobs`
    *   **Expect:** `401 Unauthorized`; the same call with the header returns 200
    *   **Fails if:** a 200 without the header

---

## [TODO] IMP-304 — Job requests have bounded inputs
**Size:** `S` | **Depends on:** — | **Source:** `api/routers/processing.py:176-185`, `api/routers/jobs.py:31,96-98`

**As a** platform owner **I want** request sizes capped
**so that** one request cannot occupy the server for hours or use every core.

### Acceptance Criteria
- [ ] `num_scenarios`: `ge=1, le=<config max>`
- [ ] `config_ids`: 1 ≤ length ≤ config max
- [ ] `jobs`: `ge=1, le=<config max>` (no `-1`)
- [ ] `POST /api/jobs` `type` is a `Literal` of real job types
- [ ] `GET /api/jobs` is paginated (`offset`, `limit ≤ 200`)
- [ ] The limits live in `configs/base.yaml` under `api.limits`

### Verification
*   **Automated:** `pytest tests/api/test_processing_guards.py -k limits`
*   **Manual:** POST a batch with `num_scenarios: 1000000`
    *   **Expect:** 422 naming the limit
    *   **Fails if:** the job is queued

---

## [TODO] IMP-305 — Responses don't leak filesystem paths or raw exceptions
**Size:** `S` | **Depends on:** — | **Source:** `api/routers/config.py:60,79`, `config.py:63`, `api/routers/processing.py:477,661`, `api/routers/calibration.py:185`

**As a** platform owner **I want** config and error responses free of absolute paths and stack details
**so that** the server's layout and internals are not disclosed.

### Acceptance Criteria
- [ ] `GET /api/config/` and `/search` return `paths.*` relative to the repo root and omit `config_path`
- [ ] Job errors are stored in full server-side (log), while the API returns an error code plus a safe message
- [ ] A test scans every API response in the test suite for the repo's absolute path or a home directory

### Verification
*   **Automated:** `pytest tests/api/test_security.py -k no_path_leak`
*   **Manual:** `curl localhost:8000/api/config/` (with auth)
    *   **Expect:** no `C:\` or `/home/` in the body
    *   **Fails if:** any absolute path appears

---

## [TODO] IMP-306 — Generated HTML is escaped and served safely
**Size:** `S` | **Depends on:** — | **Source:** `data/profile_html.py:90-94,492-494,518`, `reporting/report.py:294,365`, `api/routers/results.py:154-157`, `api/routers/data.py:197-206`

**As a** platform owner **I want** every interpolated value in generated HTML escaped
**so that** data-derived labels can never become stored XSS on the API origin.

### Acceptance Criteria
- [ ] `profile_html.py` escapes every interpolated string with `html.escape`
- [ ] `report.py` escapes attribute values (`quote=True`) in `href` and `id`
- [ ] HTML served by the API carries `Content-Security-Policy` (scripts limited to inline plotly, no external sources) and `X-Content-Type-Options: nosniff`
- [ ] Test: a window or label named `<script>alert(1)</script>` renders as text

### Verification
*   **Automated:** `pytest tests/reporting/test_html.py -k escape`
*   **Manual:** `curl -I localhost:8000/api/data/profile-report`
    *   **Expect:** a `Content-Security-Policy` header present
    *   **Fails if:** it is missing

---

## [TODO] IMP-307 — Dataset names are validated before any filesystem access
**Size:** `S` | **Depends on:** — | **Source:** `api/routers/data.py:39,54-56`, `data/loaders.py:283`

**As a** platform owner **I want** the dataset name checked against the registry first
**so that** path-like input never reaches `stat()`.

### Acceptance Criteria
- [ ] `{name}` is validated against `DATASET_SCHEMAS` (404 otherwise) before `_corpus_fingerprint`/`dataset_path`
- [ ] Test with `..%5Cpyproject`, `..%2F..` and an absolute path, each returning 404 without touching the filesystem (patch `Path.stat` to assert it isn't called)

### Verification
*   **Automated:** `pytest tests/api/test_security.py -k dataset_name`
*   **Manual:** `curl -i "localhost:8000/api/data/datasets/..%5Cpyproject/rows"`
    *   **Expect:** 404 "unknown dataset"
    *   **Fails if:** any other status or message

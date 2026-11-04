# IMP-E4 — Jobs, Concurrency & Robustness

**10 stories** · **Low risk for single-user use.** They become must-fix with several users or
several jobs at once. IMP-401 (Retry runs the demo worker) affects a single user too.
The must-fix IMP-410 (UTF-8 file I/O) is in [../04_jobs_concurrency_robustness.md](../04_jobs_concurrency_robustness.md) · Gate: a concurrency test suite
(`tests/api/test_jobs_concurrency.py`) runs two batch jobs, a cancel and a delete in parallel with no
corrupt files and no job left in `running`.

Jobs run as FastAPI background tasks: threads inside the API process, writing to SQLite. Several
paths assume single-threaded, single-process use, and break once two users (or two browser tabs)
are active at the same time.

---

## [TODO] IMP-401 — The demo worker is removed from production routes
**Size:** `S` | **Depends on:** — | **Source:** `api/routers/jobs.py:47-74,84-94,117-132`

**As a** planner **I want** "retry" to re-run the real job
**so that** a failed batch is never marked "completed" with no results.

### Acceptance Criteria
- [ ] `simulate_job_execution` is deleted, or moved to a test fixture
- [ ] `POST /api/jobs/{id}/retry` dispatches by `job.type` to the real worker (processing, calibration, drill-down), and returns 409 for a job that is still stopping or running
- [ ] `POST /api/jobs` either creates real typed jobs or is removed (typed endpoints already exist)
- [ ] The `/api/platform/search` stub and the unused `Run`/`AuditLog` tables are removed, or tracked in a story to implement them

### Verification
*   **Automated:** `pytest tests/api -k retry_real_worker`
*   **Manual:** in the UI, fail a batch (e.g. an invalid season), then click Retry
    *   **Expect:** the job fails again with the same real error
    *   **Fails if:** it shows "completed" after about 10 seconds

---

## [TODO] IMP-402 — A cancel can't be overwritten
**Size:** `M` | **Depends on:** IMP-401 | **Source:** `api/routers/processing.py:201,279-293,443,578`, `api/routers/calibration.py:78,179`, `reporting/grid.py:194`, `reporting/gate_status.py:24,37`

**As a** planner **I want** a job I cancelled to stay cancelled
**so that** I'm not billed in CPU time or confused by a "completed" status after cancelling.

### Acceptance Criteria
- [ ] Status transitions go through one helper using a conditional update (`UPDATE … WHERE status IN (...)`). `running → completed` cannot overwrite `cancelled`, and `queued → running` cannot overwrite `cancelled`.
- [ ] Calibration and drill-down workers check for cancellation between phases
- [ ] Under joblib (`jobs > 1`), cancellation is checked between batches of policies (chunked dispatch), so the delay to cancel is bounded by one batch
- [ ] Cancel endpoints are unified: 409 for a non-cancellable state on both, and type-scoped
- [ ] Concurrency test: cancel issued at each stage (queued, scenarios, scoreboard, gates) ends in `cancelled`

### Verification
*   **Automated:** `pytest tests/api/test_jobs_concurrency.py -k cancel`
*   **Manual:** start a 200-scenario batch, cancel it while the progress bar is in "building scoreboard"
    *   **Expect:** status `cancelled` within one policy's run time, and it stays cancelled
    *   **Fails if:** it later shows `completed`

---

## [TODO] IMP-403 — Scenario and parameter files are written atomically with unique temp names
**Size:** `S` | **Depends on:** — | **Source:** `scenarios/generator.py:246-261`, `calibration/pipeline.py:124-127`, `calibration/regime.py:178`, `calibration/nhpp.py:138-140`, `calibration/delays.py:159`

**As a** planner **I want** concurrent jobs never to corrupt a cached file
**so that** results don't depend on which job wrote last.

### Acceptance Criteria
- [ ] One `atomic_write(path, writer)` helper: the temp file goes in the same directory with a name including pid, thread id and a uuid, followed by `os.replace` with retry on Windows `PermissionError`
- [ ] Used for the scenario parquet, the parameter store and every calibration side file
- [ ] Concurrent generation of the same scenario set is serialised by a lock (file lock or a per-key in-process lock), so the second job reuses the first job's output
- [ ] Concurrency test: 4 threads generating the same set produce one valid parquet and no exceptions

### Verification
*   **Automated:** `pytest tests/engine/test_scenario_gen.py -k concurrent`
*   **Manual:** start two identical batches within a second of each other in the UI
    *   **Expect:** both complete with identical costs
    *   **Fails if:** either fails with `FileNotFoundError`/`PermissionError`, or the costs differ

---

## [TODO] IMP-404 — Job error handlers are themselves safe and consistent
**Size:** `S` | **Depends on:** — | **Source:** `api/routers/processing.py:447,474,483-491,581-586`, `api/routers/calibration.py:82,182,192`, `api/routers/jobs.py:68`, `api/runlog.py:124`

**As a** platform owner **I want** a failing job always to end in `failed`, with a structured log entry
**so that** no job is stranded in `running` until the next restart.

### Acceptance Criteria
- [ ] Every worker `except` block calls `db.rollback()` before querying
- [ ] Failure entries are written only through `RunLog.fail()`, so every failure has the same shape (including `progress_done`, `progress_total` and `artifact`)
- [ ] `calibration.py` no longer refers to `pipeline` inside the handler when the import may have failed (the phase total is moved to module scope)
- [ ] The drill-down failure path writes a log entry
- [ ] Tests: an injected DB error and an injected import error both end in `failed`, with a log entry

### Verification
*   **Automated:** `pytest tests/api -k failure_path`
*   **Manual:** start a calibration with a corrupted params directory (read-only)
    *   **Expect:** status `failed`, with a log line naming the file
    *   **Fails if:** the status stays `running`

---

## [TODO] IMP-405 — The SSE stream does not block the event loop
**Size:** `S` | **Depends on:** — | **Source:** `api/streaming.py:61-85`

**As a** user **I want** the API to stay responsive while progress streams are open
**so that** several open browser tabs don't freeze other requests.

### Acceptance Criteria
- [ ] DB polling inside the async generator runs via `run_in_threadpool` (or uses an async driver)
- [ ] The stream closes when the client disconnects (`request.is_disconnected()`)
- [ ] Test: 20 open streams; `/api/health` p95 latency below a configured bound

### Verification
*   **Automated:** `pytest tests/api -k sse_nonblocking`
*   **Manual:** open 5 job pages, then `curl -w "%{time_total}" localhost:8000/api/health`
    *   **Expect:** < 0.1 s
    *   **Fails if:** > 1 s

---

## [TODO] IMP-406 — Job execution has a concurrency limit
**Size:** `M` | **Depends on:** IMP-402 | **Source:** `api/db.py:9-14`, `api/routers/*` (`BackgroundTasks`)

**As a** platform owner **I want** a bounded number of simultaneous simulation jobs
**so that** heavy jobs can't starve the request threadpool or run the machine out of CPU.

### Acceptance Criteria
- [ ] Jobs are submitted to a dedicated executor with `max_workers` set in config (default 1–2), not the Starlette threadpool
- [ ] Jobs beyond the limit stay `queued`, and their queue position is visible in the API
- [ ] SQLite runs in WAL mode with a busy timeout set in config. Progress commits are throttled (as `RunLog` already does).

### Verification
*   **Automated:** `pytest tests/api/test_jobs_concurrency.py -k limit`
*   **Manual:** queue 4 batches with `max_workers: 1`
    *   **Expect:** one `running`, three `queued` with positions 1–3
    *   **Fails if:** all four run at once

---

## [TODO] IMP-407 — The event-tape cache is invalidated by recalibration
**Size:** `S` | **Depends on:** IMP-201 | **Source:** `api/routers/processing.py:777-799`

**As a** planner **I want** a scenario tape that always matches the current parameters
**so that** the drill-down never contradicts a fresh run.

### Acceptance Criteria
- [ ] The cache key includes the parameter-store `content_hash` and the config fingerprint
- [ ] Alternatively the tape is keyed to the job's stored provenance (preferred), so a tape is always rebuilt from that job's inputs

### Verification
*   **Automated:** `pytest tests/reporting/test_tape.py -k cache_key`
*   **Manual:** view a tape, recalibrate with changed data, view the same tape again
    *   **Expect:** a recomputed tape (or a notice that the job's params are stale)
    *   **Fails if:** the old tape is served silently

---

## [TODO] IMP-408 — Deleting a running job cancels it first
**Size:** `S` | **Depends on:** IMP-402 | **Source:** `api/routers/processing.py:1029-1034`, `api/routers/jobs.py:135-145`

**As a** user **I want** delete to stop the work as well as remove the row
**so that** deleted jobs don't keep consuming CPU or crash on their next commit.

### Acceptance Criteria
- [ ] Delete of a `running`/`queued` job means cancel, wait for acknowledgement (bounded timeout), then delete. Alternatively return 409 "cancel first".
- [ ] One delete endpoint, scoped by type (the duplicate is removed)
- [ ] The docstring matches the behaviour

### Verification
*   **Automated:** `pytest tests/api/test_jobs_concurrency.py -k delete_running`
*   **Manual:** delete a running batch, then watch CPU in Task Manager
    *   **Expect:** CPU drops within one policy run
    *   **Fails if:** CPU stays high until the batch would have finished

---

## [TODO] IMP-409 — GET endpoints are cheap, side-effect-free and truthful
**Size:** `M` | **Depends on:** — | **Source:** `api/routers/data.py:39,59-72,197-206`, `api/routers/processing.py:874-999`, `api/routers/platform.py:94-95`, `api/db.py:94`, `config.py:390-412`

**As a** user **I want** read endpoints to be fast and never change server state
**so that** browsing the UI doesn't trigger heavy computation or report false health.

### Acceptance Criteria
- [ ] Quality and profile reports are cached, keyed by corpus fingerprint and config hash
- [ ] `GET /{job_id}/scenarios` never generates. It returns 404/409 if the scenario set is missing, and generation happens only within jobs.
- [ ] `config.load()` is cached per process, keyed on file mtimes. `[NOTICE]` output goes through logging, once.
- [ ] `/api/platform/health` really checks the DB (`SELECT 1`) and reports `degraded` on failure
- [ ] The SQLite path comes from config or an environment variable and is absolute, so it no longer depends on the working directory
- [ ] `psutil` is declared in `pyproject.toml`, or the health endpoint degrades gracefully without it
- [ ] Timestamps are serialised as UTC ISO-8601 with `Z`

### Verification
*   **Automated:** `pytest tests/api -k "cached_reports or health_db or no_side_effect"`
*   **Manual:** `curl -w "%{time_total}" localhost:8000/api/data/profile-report -o NUL`, twice
    *   **Expect:** the second call is at least 10× faster
    *   **Fails if:** both calls take the same time

---

## [TODO] IMP-411 — The CLI reports errors instead of tracebacks, and validates arguments
**Size:** `M` | **Depends on:** — | **Source:** `cli.py:224,281,891,1148,1275-1282,1424-1434,1563-1654`

**As a** planner **I want** a one-line error and a non-zero exit code when something is wrong
**so that** I can fix my command without reading a stack trace.

### Acceptance Criteria
- [ ] A top-level handler maps `FileNotFoundError`, `ValidationError`, `CalibrationError` and `SchemaError` to `error: <message>` with exit code 2 (full traceback only with `--debug`)
- [ ] `--scenarios` and `--rows` are validated as `>= 1` by a shared argparse type
- [ ] `gate v9` with no `sensitivity` section gives a clear message
- [ ] `doctor` handles configured paths outside the repo (prints them absolute)
- [ ] `explain-cascade` with no mode prints usage and exits 2
- [ ] `run --kpis --assert-invariants` runs the invariants, and the V3 verdict and provenance always print, so no early return skips them

### Verification
*   **Automated:** `pytest tests/test_cli.py -k "errors or arg_validation"`
*   **Manual:** `crewsim run --policy DOES_NOT_EXIST` and `crewsim run --policy R6 --scenarios 0`
    *   **Expect:** one-line errors with exit code 2
    *   **Fails if:** a traceback or `ZeroDivisionError`

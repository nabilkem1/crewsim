# Code review — `src/crewsim/api/` and `web_ui/`

**Date:** 2026-08-09 · **Branch:** `slice-1a-1b-hardening` (working tree, uncommitted)

> **Status: all findings below have been implemented.** See
> [§ Resolution](#resolution--what-was-done) at the end for what changed, what was
> deleted rather than fixed, and the verification output. The findings are kept in
> their original form — the record of what was wrong is the point.

## Scope — and why I triaged this way

You asked me to analyse `src/crewsim` (64 files) and `web_ui` (36 files). I ran every check across
both, then concentrated the review on **`src/crewsim/api/` (7 files) and `web_ui`** — the two trees
that no automated check covers.

That was a deliberate triage, not a shortcut. The other 57 Python files are ruff-clean, mypy-strict
clean, covered by 339 passing tests, and already carry three rounds of documented review in
`CODE_REVIEW_S1a/S1b/S1c.md`. Re-auditing them would mostly re-tread those documents. The API and
front-end trees have had none of that, and the triage paid: **four P0s, all reproduced against a
running server or a real build.**

What this means for you: the simulation core's *correctness* was not re-reviewed here. Green tooling
is not the same as a correct engine — that is the "test suite is not evidence" lesson from S1a, and
I am not claiming to have relitigated it. I did spot-check the in-flight `config.py` change (adds
`PositioningConfig`, removes the two `positioning.*` entries from `DECLARED_NOT_YET_CONSUMED`); the
removal is justified — `engine/events.py:48` now builds a real DEADHEAD block and `engine/des.py:130`
refuses to dispatch a cross-base reserve when `positioning` is unconfigured.

---

## Read this first: the defect class the last three reviews chased has moved house

`CODE_REVIEW_S1a/S1b/S1c.md` are three rounds of one fight — *code that looks implemented and
isn't*. "Replace fabricated verification with real gates." "Make REDUCED mode real enough to
refuse." The core tree won that fight, and I can show it:

```
uv run ruff check src tests      → All checks passed!
uv run mypy src/crewsim/engine   → Success: no issues found in 17 source files
```

The gates are now scrupulous about their own limits — `v5_trace.py:26` and `v6_backtest.py:30`
carry runtime labels saying the corpus is `tools/generate_mock_corpus.py` output, not Air Transat
payroll. `v9_sensitivity.py:95` *refuses to run* rather than invent a sweep axis. That is the
standard this repo set for itself.

**`src/crewsim/api/` does not meet it, and the reason is structural: almost nothing checks that
tree.** `pyproject.toml` excludes it from ruff. `tests/test_config.py` exempts it via
`EXCLUDED_TREES`. mypy `--strict` covers `crewsim.engine.*` only. `web_ui/` has no test framework
at all, and `.github/workflows/ci.yml` never invokes Node — it lints, type-checks and tests Python,
then stops.

So the exact thing the three reviews were built to catch is sitting, uncaught, in the layer Crew
Planning will actually look at. Everything below follows from that.

---

## Verdicts

| Area | Verdict | Note |
|---|---|---|
| `engine/`, `gates/`, `reporting/` — **hygiene only** | ✅ | ruff + mypy strict clean; gates label their own mock data. **Correctness not re-reviewed this pass** — see Scope |
| Test suite | ❌ | **1 failed**, 339 passed — the failure is in the uncommitted tree |
| `web_ui` build | ❌ | `npm run build` exits 2; 8 TypeScript errors |
| API ↔ UI contract | ❌ | 6 endpoints 404 at runtime; one tab hides it with browser-side mock data |
| `api/routers/platform.py` | ❌ | hard 500 crash, reproduced |
| `api/routers/results.py` | ❌ | 9 of 12 endpoints fabricated; not even domain-shaped |
| `api/routers/provenance.py` | ❌ | entirely fabricated — in a repo built on provenance |
| `api/routers/runs.py` | ❌ | `MOCK_RUNS` module constant; unreachable from the UI |
| `api/routers/calibration.py` | ❌ | runs the real pipeline, then decorates it with invented statistics |
| `api/routers/processing.py` | ⚠️ | the real `run_grid` path is genuine; the rest is filler |
| `api/routers/data.py`, `config.py` | ✅/⚠️ | `profile-report` and `datasets` are real; `quality-report` is mocked and says so |

---

## P0 — things that are broken right now

### 1. The test suite fails on the current working tree

```
FAILED tests/test_project_structure.py::test_dataset_suffixes_have_one_authority
1 failed, 339 passed, 1 warning in 282.74s
```

`src/crewsim/api/routers/results.py:77` — `if ext == '.csv':` — trips
`test_dataset_suffixes_have_one_authority`, which asserts that only `config.py` may know a dataset's
on-disk suffix. It arrived with the uncommitted change (`git diff` shows `+    if ext == '.csv':`).

Worth saying plainly: **this is a false positive in spirit.** Line 77 is content-type dispatch for a
download response, not a corpus path. But the guard is repo law, it scans `SRC.rglob("*.py")` with
no `api/` exemption, and CI will go red on push. Either the file avoids the literal or the guard
grows a documented carve-out — that is a decision for whoever owns the rule, not something to
paper over.

Note the asymmetry this exposes: `api/` is exempt from ruff and from `test_config.py`, but *not*
from `test_project_structure.py`. The exemptions are inconsistent, which is why an unpoliced tree
still managed to break CI.

### 2. `web_ui` does not build

```
$ npm run build     → BUILD_EXIT=2
src/features/data/DataQualityDashboard.tsx(17,17): error TS6133: 'setError' is declared but never read.
src/features/jobs/ErrorBoundary.tsx(1,8):  error TS6133: 'React' is declared but never read.
src/features/jobs/ErrorBoundary.tsx(1,28): error TS1484: 'ErrorInfo' must be a type-only import.
src/features/jobs/ErrorBoundary.tsx(1,39): error TS1484: 'ReactNode' must be a type-only import.
src/features/jobs/NotificationContext.tsx(1,54): error TS1484: 'ReactNode' must be a type-only import.
src/features/results/Charts.tsx(1,8):      error TS6133: 'React' is declared but never read.
src/features/results/index.tsx(1,1):       error TS6133: 'React' is declared but never read.
src/features/results/Summaries.tsx(1,8):   error TS6133: 'React' is declared but never read.
```

All eight are trivial (`verbatimModuleSyntax` + unused imports). The finding is not the errors —
it is that **nothing would ever have told you.** `vite dev` transpiles without type-checking, so the
app runs fine locally while `tsc -b` has been failing. CI does not run Node. This is the front-end
equivalent of the "the test suite is not evidence" headline in `CODE_REVIEW_S1a.md`.

### 3. `GET /api/platform/health` returns 500 whenever a job is queued

Reproduced. Insert one `queued` job, then call the endpoint:

```
HTTP: 500
  File "src/crewsim/api/routers/platform.py", line 60, in platform_health
    total_wait = sum((now - job.created_at).total_seconds() for job in queued_jobs if job.created_at)
TypeError: can't subtract offset-naive and offset-aware datetimes
```

`db.py:12` defaults `created_at` to `datetime.now(timezone.utc)` — aware. SQLite's `DateTime`
column stores no offset, so it reads back **naive** (verified: `tzinfo= None`).
`platform.py:58` then builds an aware `now` and subtracts.

This is precisely what ruff's `DTZ` rule exists to catch, and `pyproject.toml` enables `DTZ` with
the comment *"naive datetimes: this project is strict about them"* — but `api/` is excluded, so the
rule never looked. The bug is latent rather than constant only because the window between a job
being queued and picked up is short; under any real queue depth the dashboard is down.

The same naive/aware mismatch is waiting in `results.py:16` (`j.updated_at - j.created_at`) — that
one happens to be safe today because both sides come back naive from SQLite.

### 4. Six endpoints the UI calls do not exist

Probed against a live server:

| UI call | HTTP | Actual route |
|---|---|---|
| `cascade-summaries` (`analytics/index.tsx:11`) | **404** | `/api/analytics/cascade-summaries` |
| `cascade-policy-comparisons` (`analytics/index.tsx:23`) | **404** | `/api/analytics/cascade-policy-comparisons` |
| `exemplar-drills` (`analytics/index.tsx:35`) | **404** | `/api/analytics/exemplar-drills` |
| `/platform/health` (`HealthDashboard.tsx:16`) | **404** | `/api/platform/health` |
| `/platform/audit-log` (`AuditLogViewer.tsx:18`) | **404** | `/api/platform/audit-log` |
| `/platform/search` (`GlobalSearch.tsx:20`) | **404** | `/api/platform/search` |

The routers mount under `/api/...` in `main.py:22-31`; these six callers were written against the
routers' own `prefix=""` and never picked up the mount point.

**The Cascade Analytics tab does something worse than fail.** All three of its calls 404, and
`analytics/index.tsx:13,26,37` catches each one and substitutes **hardcoded mock data defined inline
in the component**:

```js
.catch(e => {
    console.error("Failed to fetch cascade summaries, using mock data", e);
    setSummaries([
        { id: 'casc_mock_1', name: 'Mock Recovery', status: 'completed', total_drills: 10, success_rate: 0.9, cost_impact: 10000 },
        ...
```

So the tab renders a complete, confident dashboard — success rates, cost impacts, policy
comparisons — with numbers invented in the browser, and the only signal that anything went wrong is
a `console.error` nobody has open. The 404s are the trigger; **the client-side fallback is the
defect.** Fixing the URLs would swap browser-invented numbers for server-invented ones (§7), so
these two findings must be fixed together or the tab stays fictional either way.

The three `platform/*` components are not mounted anywhere at all (nothing imports
`features/platform`), so they are dead code that is also broken.

Two secondary problems in the same area:

- **Base-URL inconsistency.** Some calls hard-code `http://localhost:8000`, others use relative
  paths that depend on `vite.config.ts`'s `/api` proxy. The `/platform/*` calls are relative *and*
  outside the proxied prefix, so in dev they hit Vite, get `index.html` back with a 200, and die in
  `res.json()` — a confusing failure mode. The hard-coded `localhost:8000` calls simply will not
  work in any deployed build.
- `DiagnosticsView.tsx:13` and others check `res.ok`, but several callers (`results/api.ts`, all 11
  lines) call `.then(res => res.json())` with no status check, so a 404 surfaces as a JSON parse
  error rather than an error state.

---

## P1 — fabricated data presented as results

This is the substantive finding, and it is worse than "stub data" because of *how it is presented*.

### 5. The calibration diagnostics chart is invented, and the UI teaches the user to trust it

`calibration.py:78` — the comment is candid:

```python
# Generate fake convergence diagnostics since pipeline doesn't return history yet
iterations = []
current_ll = -2500.0
for i in range(1, 21):
    iterations.append({"iteration": i, "log_likelihood": round(current_ll, 2),
                       "aic": round(-2 * current_ll + 2 * 5, 2)})
    current_ll += (abs(current_ll) * 0.05 * (21 - i) / 20)
```

That is a closed-form arithmetic curve with no input from the fit. It is served from
`/api/calibration/{job_id}/diagnostics` and rendered by `DiagnosticsView.tsx` as a bar chart titled
**"Log-Likelihood Convergence"**, complete with a "?" panel that explains:

> *"**Convergence** means the optimization algorithm has found the best possible parameters. A healthy
> calibration curve starts low (negative) and rapidly climbs before plateauing near the top."*

The generator produces exactly that shape by construction. A user is being handed a picture of a
healthy fit, plus instructions for reading it as evidence of a healthy fit, for a fit that was never
measured. The `aic` term hard-codes `k = 5` parameters regardless of what was fitted.

`calibration.py:61` does the same in scalar form — `"final_log_likelihood": -1204.45,  # ... mock
it` — and unlike the gates, nothing in the response tells the UI it is mock.

The frustrating part is that **the job around it is real**: `run_calibration_job` genuinely calls
`pipeline.run_pipeline` and genuinely reports the fitted transition matrix, intensity multipliers
and mixture components. The invented statistics are decoration on real work, which makes them
harder to spot, not easier.

**Contrast with the standard the repo already meets:** `v9_sensitivity.py:95` raises rather than
invent a sweep axis; `v5_trace.py:26` stamps its output as mock corpus data. Either behaviour would
be fine here. Silence is not.

### 6. `/api/calibration/compare` returns random numbers

`calibration.py:171-173`:

```python
"transition_matrix_norm": round(random.uniform(0.9, 1.1), 3),
"nhpp_alpha":             round(random.uniform(0.1, 0.5), 3),
"log_likelihood":         round(random.uniform(-1500.0, -800.0), 2),
```

The comparison view will show different numbers on every refresh, for the same two job ids. In a
codebase whose spine is reproducibility — CRN streams, gate V7 comparing ledger hashes across
joblib workers, hash-pinned policy provenance — a comparison endpoint seeded by
`random` is the sharpest single contradiction in the tree.

`processing.py:175-176` has the same shape: `/api/processing/prediction` returns
`random.randint(60, 3600)` seconds and `random.uniform(0.5, 10.0)` dollars as a cost estimate.

### 7. `results.py` and `provenance.py` are placeholders from a different product

Nine of `results.py`'s twelve endpoints return literals — `/metrics/comparison` plus all eight
`/charts/*`. (The other three are real: `/summaries` queries the DB, `/artifacts` globs the
filesystem, `/artifacts/download/{filename}` serves actual files.) The literals are not crew
scheduling:

- `/charts/gates` → `"Initial Screening"`, `"Background Check"`, `"Technical Interview"`,
  `"Final Review"`. This repo's gates are **V1 degeneracy, V2 Erlang-B, V3 eligibility, V4 cascade,
  V5 trace, V6 backtest, V7 reproducibility, V9 sensitivity** — all implemented in `src/crewsim/gates/`.
  The endpoint returns a hiring funnel.
- `/charts/eligibility` → reasons `"Missing Credentials"`, `"Expired License"`, `"Age Restriction"`.
  The real eligibility engine (`engine/eligibility.py`, gate V3) produces L0–L8 legality reasons.
- `/charts/timeseries` → `"CPU Usage"`, `"Memory Usage"`. `/charts/grid` → `"Alpha Node"`,
  `"Beta Node"`. `/metrics/comparison` → `throughput`, `latency`, `error_rate`.

`provenance.py` is fabricated end to end, and its invented vocabulary is ML-training, not
simulation: `learning_rate`, `batch_size`, `epochs`, `s3://bucket/data.csv`, `docker_image`,
`"reproducibility_score": 0.95`. The `/comparison/t-test` endpoint returns a fixed
`p_value: 0.015, significant: True`. `runs.py` serves a module-level `MOCK_RUNS` list
(`agents: 5, environment: "dev"`).

The cost of this is not the fake numbers themselves — it is that **the real computed values already
exist and are not wired up**. `reporting/kpis.py`, `reporting/grid.py`, `reporting/counterfactual.py`
and `gates/*` all produce exactly the quantities these endpoints pretend to serve, and
`processing.py:69` proves the wiring is possible — it calls `run_grid` for real and returns a
genuine scoreboard.

Two endpoints are honest and should be the model: `data.py:58` `/profile-report` actually runs
`compute_profiles` + `render`; `data.py:40` `/datasets` actually globs the corpus. `data.py:5`
`/quality-report` is mocked but its docstring says *"Returns a mocked report for now"* — the right
instinct, one layer short of telling the UI.

### 7b. The front end has its own mock-fallback layer, so a dead backend still renders a full dashboard

Beyond the analytics tab (P0 #4), `DataQualityDashboard.tsx:31` does the same thing — on any
non-`ok` response it swallows the error and renders a hardcoded report with
`overall_score: 95` and four passing checks:

```js
console.warn('API fetch failed, using mock data:', err);
// Fallback mock data in case the API is not yet running
setReport({ overall_score: 95, checks: [ ... 'No missing values found across critical tables.' ...
```

This is the most dangerous single pattern in the front end, because **it is indistinguishable from
success at the UI layer.** Stop the API, open the app, and you get a data-quality score of 95 and a
green cascade dashboard. The error path and the happy path render identically; only a `console.warn`
separates them.

It also makes the whole system untestable by inspection: you cannot tell by looking at the UI
whether any given number came from the engine, from a hardcoded router literal (§7), or from the
browser. Three independent layers can each invent the same figure.

`DataQualityDashboard` is not currently mounted in `App.tsx`, which limits today's blast radius to
the analytics tab — but it also means the pattern is spreading in components nobody is looking at.
The rule worth adopting: **a failed fetch renders an error state, never data.**

### 8. The calibration launcher's inputs are silently discarded

`CalibrationLauncher.tsx` collects a run name, a dataset, and five selectable models
(`transition_matrix`, `intensity_multipliers`, `nhpp_covariates`, `mixture_dist`, `lognormal_dist`)
and POSTs them. `calibration.py:106` validates them into `CalibrationJobCreate` — and then calls
`run_calibration_job(job_id)`, which takes **only the job id**. Name, dataset and model selection
are never read. Every run fits everything against `cfg.scope.season`.

Same pattern in `processing.py:51`: `calibration_file` is handled by substring-sniffing
(`if "W26" in calibration_file`), so any file name not containing `W26`/`S26` silently falls through
to whatever season the config already had. And `/config/output` and `/config/hardware`
(`processing.py:155,159`) echo `{"status": "success"}` while persisting nothing — a UI that reports
a saved setting that was not saved.

---

## P2 — correctness-adjacent

### 9. Unescaped file content interpolated into served HTML

`results.py:84,93,99` build HTML by f-string from artifact file contents:

```python
html += f'<th>{col}</th>' if i == 0 else f'<td>{col}</td>'
...
html = f'<html>...<pre>{content}</pre></body></html>'
```

No escaping. A `<` in any CSV cell corrupts the table; a `<script>` in any artifact executes in the
app's origin. `.html` artifacts are served inline with `Content-Disposition: inline`. Severity is
bounded — this is a local tool and the inputs are the tool's own outputs — but `html.escape()` on
three lines closes it, and artifacts are partly derived from customer data files.

Path traversal on `/artifacts/download/{filename}` I probed (`..%2F`, `....//`, double-encoded) and
**could not break** — Starlette's path converter refuses the separator. It holds today by virtue of
the router, not by a check in the handler; a future switch to `{filename:path}` would open it.

### 10. Job execution is coupled to the API process lifetime

`jobs.py`, `calibration.py` and `processing.py` all run work via FastAPI `BackgroundTasks` in the
API worker. `run_grid` with real scenario counts is minutes of CPU; `jobs.py:29` `simulate_job_execution`
sleeps 10 seconds in a thread. Consequences: jobs die silently on reload/restart and are never
reconciled (a killed job stays `running` forever); cancellation is polled by re-reading the row
(`processing.py:45`), so a cancel between progress ticks is not honoured; and `sqlite` with
`check_same_thread=False` (`db.py:47`) plus multiple threads committing to the same file will
contend under any concurrency. For an MVP this may be an accepted trade — but it is undocumented,
unlike every other trade-off in this repo.

### 11. `psutil` is an undeclared dependency with a silent fallback

`platform.py:6-10` wraps `import psutil` in `try/except ImportError` and falls back to
**hard-coded plausible numbers** — `cpu_percent = 12.5`, `mem_total = 16.0`, `mem_used = 4.2`.
`psutil` is not in `pyproject.toml` and is not installed (`uv run python -c "import psutil"` →
`ModuleNotFoundError`), so the fallback is not a fallback — **it is the only path that ever runs**,
and the health dashboard reports a fictional 26.2% memory usage as fact. The uptime line is worse: when `psutil` is absent it
computes `time.time() - (time.time() - 86400)`, i.e. hard-codes "up 24 hours."

### 12. `api/` code style is off the house standard

Imports mid-file (`results.py:47-51`, `platform.py:31-32`, `data.py:56`), function-local imports
throughout, unused imports (`uuid`, `time`, `Optional`, `BaseModel` in several routers), bare
`except Exception` swallowing job failures into a string, `typing.List`/`Dict` rather than the PEP
585 builtins that `UP` enforces elsewhere. None of this matters on its own; all of it is what the
ruff exclusion is buying.

---

## P3 — inventory

- **`src/crewsim/optimize/` is an empty `__init__.py`.** Whatever it was for is unstoried here.
- **Root-directory cruft**: `crewsim_skeleton.py`, `detail_impls.py`, `enrich_epics.py`,
  `find_missing.py`, `fix_md.py`, `fix_stories.py`, `format_backlog.py`, `inject_narratives.py`,
  and `test_l5_fix.py` (a test outside `testpaths`, so it never runs). Five `image*.png` screenshots
  are untracked or deleted in the working tree. `crewsim_skeleton.py` is still cited as the
  reference implementation in `COVERAGE_AUDIT.md` §0, so it has a reason to exist — the rest look
  like one-shot scripts.
- **`cli.py` is 1818 lines**, 2.3× the next-largest file. I checked what is in it: 125
  `add_argument`/`add_parser` calls and 233 `print(` calls, so it is argparse wiring and output
  formatting rather than business logic — long, not wrong. The one real smell is that those 1818
  lines hold only 18 function definitions, so the individual handlers are very large.
- **`web_ui` has no tests and no test tooling** — no runner in `package.json`; `test-results/`
  holds a stray Playwright `.last-run.json` and nothing else. `oxlint` reports 3 warnings, all
  cosmetic.
- **`App.tsx` inlines every style as a `style={{}}` object** across 282 lines while also using CSS
  custom properties (`var(--color-primary-600)`). One or the other.

---

## Prioritized fix list

### P0 — broken now
1. `results.py:77` — resolve the `'.csv'` literal against `test_dataset_suffixes_have_one_authority`; the suite is red.
2. Fix the 8 `tsc -b` errors, then **add a `web_ui` job to `ci.yml`** (`npm ci && npm run build && npx oxlint`). The errors are the symptom; the missing CI job is the finding.
3. `platform.py:58-60` — compare like with like (store UTC-aware or normalise on read). Reproduced 500.
4. Repoint the 6 wrong URLs at `/api/...`; put the base URL in one module and use the Vite proxy consistently. **And delete the inline mock fallbacks in `analytics/index.tsx` in the same change** — repointing alone just moves the fabrication from the browser to the server.

### P1 — fabricated results
5. `calibration.py:78` — delete the synthetic convergence curve, or have `run_pipeline` return real history. Do not ship a chart the UI explains as evidence of convergence.
6. `calibration.py:61` — real log-likelihood or omit the key.
7. `calibration.py:171` / `processing.py:175` — remove `random.*` from every response.
8. Wire `results.py` to `reporting/kpis.py`, `reporting/grid.py` and `gates/*`. Until an endpoint is wired, follow `v5_trace.py:26`: return a machine-readable `mock: true` the UI must render as a banner.
9. Delete every client-side mock fallback (`analytics/index.tsx:15,27,39`, `DataQualityDashboard.tsx:31`) and render error states instead. A failed fetch must never render data.
10. `calibration.py:106` — either honour `dataset` / `models_to_fit` or reject them; `processing.py:51` — parse the calibration file properly instead of substring-sniffing; `processing.py:155,159` — stop reporting success for a no-op.

### P2
11. `html.escape()` at `results.py:84,93,99`.
12. Declare `psutil`, or make the fallback report "unavailable" rather than 12.5%.
13. Document the `BackgroundTasks` trade-off and reconcile orphaned `running` jobs on startup.

### P3
14. **Delete `EXCLUDED_TREES` and the ruff `exclude` for `api/`.** Both carry comments promising they are temporary; `test_config.py:440` explicitly says it "must be deleted rather than left as scaffolding that silently exempts a whole tree forever." Every P0 and P1 above is in the exempted tree. That is the finding behind the findings.
15. Move the root-level one-shot scripts into `tools/`; `test_l5_fix.py` into `tests/` or out.

---

## One question for the spec owner, not a defect

`results.py`, `provenance.py` and `runs.py` describe a system with model training, Docker images,
S3 data sources, agents and node grids. None of that is in the spec or the engine. I could not
determine whether these routers were scaffolded against a generic template and never revised, or
whether they encode a real intent I cannot see. **If it is the former, the honest fix is to delete
them rather than fill them in** — deleting a fabricated endpoint is cheaper than wiring a real one
to a shape nobody asked for, and the current shapes have already propagated into the UI components
that consume them. Per the standing rule on not inventing modelling parameters, I have not guessed
at what these should return.

---

# Resolution — what was done

Implemented 2026-08-09. Every item in the fix list above is closed. The findings
are left in their original wording deliberately: this document's value is the
record of what was wrong, not a changelog.

## The scope decision

The open question at the end of this review — wire the fabricated routers up, or
delete them — was answered: **delete.** With one refinement, confirmed before
cutting: `results.py` was not uniformly fabricated. Nine of its twelve endpoints
were, but `/summaries`, `/artifacts` and `/artifacts/download/{filename}` are
real and drive the Results tab. So:

| File | Action |
|---|---|
| `api/routers/provenance.py` | **deleted** — fabricated end to end |
| `api/routers/runs.py` | **deleted** — `MOCK_RUNS` module constant |
| `api/routers/results.py` | **stripped** to its 3 real endpoints; 9 chart/metric endpoints deleted |
| `web_ui/features/provenance/` | **deleted** (4 components + nav tab) |
| `web_ui/features/results/Charts.tsx` | **deleted** |
| `web_ui/features/calibration/DiagnosticsView.tsx` | **deleted** — its endpoint served the invented convergence curve |
| `web_ui/features/calibration/ComparisonView.tsx` | **deleted** — its endpoint returned `random.uniform()` |

## Placeholder data: a stricter rule than this review proposed

Fix #8 originally recommended labelling unwired endpoints with `mock: true` and
having the UI render a banner. Implementing P3 #14 showed that was not enough.

Once `src/crewsim/api/` came under `test_no_numeric_constant_outside_configs`,
the guard immediately flagged `analytics.py`'s `cost_impact: 12500` and
`success_rate: 0.92`, and `data.py`'s `overall_score: 95`. It was right to: those
are invented business figures living in `src/`, which is exactly what it exists
to catch. A `mock: true` flag next to a fabricated dollar amount still leaves the
dollar amount on screen for anyone who misses the banner.

So the rule implemented is stronger: **an endpoint with nothing real to report
returns nothing.** `api/mocks.py::not_implemented()` tags a payload
`implemented: false` with a notice, and the payload carries empty collections —
no sample values at all. The UI renders `NotImplementedPanel`, which says so in
words and shows no figures. This covers cascade analytics, the data-quality
report, and global search.

## The carve-out is gone

`tests/workstreams.py` is deleted, along with `EXCLUDED_TREES`,
`test_api_exclusion_is_still_necessary`, and the `exclude` in `pyproject.toml`'s
`[tool.ruff]`. `src/crewsim/api/` is now covered by ruff, by the numeric-constant
guard, and by the hard-coded-path guard, like every other tree.

Getting there took 143 → 0 ruff errors. The 16 `B008` findings on
`db: Session = Depends(get_db)` were resolved with
`[tool.ruff.lint.flake8-bugbear] extend-immutable-calls`, which is ruff's
documented setting for FastAPI's dependency-injection syntax — it teaches B008
which calls are safe in a default rather than disabling the rule. 19 structural
literals (HTTP status codes, percent, pagination limits, byte arithmetic) got
audited `ALLOWLIST` entries in the style of the existing ones.

## Verification

Run at the end, in full, on the working tree:

```
uv run ruff check src tests      → All checks passed!
uv run mypy src/crewsim/engine   → Success: no issues found in 17 source files
uv run pytest -q                 → 355 passed, 2 warnings in 395.04s
cd web_ui && npm run build       → ✓ built in 213ms   (was: exit 2, 8 TS errors)
cd web_ui && npx oxlint          → exit 0
```

Behaviour checked against a live server rather than inferred:

- `/api/platform/health` with a queued job present → **HTTP 200** (was 500;
  `metrics_available: false` now, instead of a fictional 26.2% memory).
- All 12 endpoints the UI calls → **200**. The six that used to 404 are among them.
- All 8 deleted endpoints → **404/405**.
- A CSV artifact containing `<script>alert(1)</script>` → served as
  `&lt;script&gt;…`, zero unescaped tags.
- `reconcile_orphaned_jobs()` → a job left `running` becomes `failed` with an
  explanatory message, rather than counting as active forever.

POST paths were exercised with the exact bodies the UI sends, not just GETs:

- `POST /api/calibration/jobs` with all five models → **200**; with a subset →
  **400** with an explanatory message (the endpoint used to accept and discard it).
- `POST /api/processing/run` → **200**, and the job ran to `completed` at 100%
  through the real `run_grid`.
- `POST /api/processing/run` with `season: "W26"` — the value the old dropdown
  actually sent — → **400 Unknown season 'W26'. Known seasons: shoulder,
  summer_atlantic, winter_sun**.
- The same request with `season: "summer_atlantic"` was accepted and failed *in
  the engine* with `Missing parameter store for summer_atlantic. Run calibration
  first.` — which is the correct domain refusal, and proves the season override
  now reaches the simulation instead of being silently dropped.

**Four bugs were introduced during this work and caught by running things**, none
of which any static check would have found:

1. Annotating the audit-log and job-status routes `-> list[AuditLog]` /
   `-> list[Job]` made FastAPI try to build a Pydantic response model from a
   SQLAlchemy class, crashing the app at import. Both now carry
   `response_model=None`. Found by starting the server.
2. `ResultsInspector.tsx` still rendered the *old* calibration shape
   (`final_log_likelihood`, `detailed_results.*`) after the backend moved to
   `{season, fitted, goodness_of_fit}`. Because `results` is typed `any`,
   `tsc -b` passed while the panel would have rendered blanks — the exact
   failure-looks-like-success pattern this review is about. Rewritten against
   the real payload, which was then fetched and checked key by key.
3. `cfg.scope.season = season` cannot work: the config models are
   `frozen=True`. The *original* code did this too, so passing a calibration
   filename containing "W26" was the one way to break that endpoint — the bare
   `except` turned it into a failed job with a pydantic error attached. Now a
   `model_copy`.
4. The season dropdown offered `W26`/`S26`, which are calibration *parameter
   filenames* — neither has ever been a valid `scope.season`. The real values
   (`winter_sun`, `summer_atlantic`, `shoulder`) live in `configs/seasons.yaml`.
   Added `GET /api/config/seasons`, served through the same `load_seasons()`
   every other caller uses, and the form is driven from it.

## Two things deliberately left alone

- **`tests/engine/test_positioning.py`** is untracked in-flight work from the
  positioning/S1c-07 stream (the same stream as the `PositioningConfig` addition
  in `config.py`). It had two lint findings mid-session and was fixed externally;
  either way it was not this change's to touch.
- **`crewsim_skeleton.py` stays at the repository root.** P3 #15 moved the seven
  unreferenced one-shot backlog scripts to `tools/backlog_scripts/`, but the
  skeleton is cited by 12 files including `src/crewsim/engine/des.py` and
  `COVERAGE_AUDIT.md` §0. `test_l5_fix.py` was deleted rather than moved: it was
  a `print()` with no assertion, and L5 already has 7 real tests in
  `tests/engine/test_legality.py` — collecting it would have been fake coverage.

## Still open

- **`/api/results/artifacts` has no UI consumer.** The endpoint is real and
  works; `Artifacts.tsx` was deleted in the in-flight refactor that preceded this
  review. Either a component comes back or the endpoint should go — flagging
  rather than deciding, since that refactor is yours.
- **Cascade analytics, the data-quality report and global search are declared but
  unimplemented.** They now say so. Wiring them needs a response contract designed
  against `engine/cascade.py` and `crewsim.data.quality`; that is a spec decision,
  and this review deliberately did not infer one from the placeholder shapes.
- **`analytics/index.tsx` has no branch for real data.** It renders the
  not-implemented panel and nothing else, which is correct today but will
  silently render blank the moment those endpoints start returning summaries.
  Whoever wires the cascade engine needs to add the success branch.
- **Jobs still run in `BackgroundTasks`.** Documented in `api/db.py` with its
  consequences, and orphans are now reconciled at startup, but a restart still
  loses in-flight work. A real queue is the fix when that trade stops paying.

---

# Follow-up — the processing page's execution log and scoreboard

Added 2026-08-09, after the review above.

## What the page shows now

A four-step execution log, streamed while the job runs, and the policy
scoreboard with the paired CRN difference and gate V3's verdict:

```
[1/4] loading parameter store ................................... 7 ms
      -> params_v0.1.0 (blake2b:87de6f4a...) season=winter_sun
[2/4] generating 4 scenarios from master seed 'master' .......... 0 ms
      -> 4 CRN-paired scenario(s); arrivals keyed on (master_seed, scenario_id)
[3/4] evaluating 2 policies x 4 scenarios ....................... 13.9 s
      -> 2 policies evaluated (sequential, jobs=1)
[4/4] building scoreboard ....................................... 764 ms
      -> 2 row(s), 1 paired comparison(s)
  ⚠  eligibility rate 0.03 is outside the validation band [0.01, 0.01] - see V3.
```

**Every value is read back from the thing that produced it.** The version and
hash come from `params_provenance()`, the durations are measured wall clock,
the counts are the real policy and scenario counts. `MISSING` is a real,
reported state -- it is what a season with no calibrated parameter store shows,
and the run then fails on it visibly rather than silently proceeding.

## Transport: SSE over a polled row

`GET /api/processing/{job_id}/stream` emits server-sent events. The docstring is
explicit that the worker does not push: jobs run in `BackgroundTasks` writing to
SQLite, so the endpoint polls that row every 0.5s and emits on change. That is
still a real improvement on the previous blind 2-second `setInterval` refetch of
every job -- one held connection, sub-second latency, and the structured step
log instead of a status integer. The generator terminates on a terminal status,
on a missing job, or at a hard timeout, and takes a fresh session per poll
rather than holding a request-scoped one open.

## One computation, two surfaces

The `E[C] / CVaR95 / elig / casc / uncovered` columns are `compute_kpis`
output. The difference line is `reporting/paired.py`, **extracted from `cli.py`'s
`compare` branch rather than reimplemented** -- the CLI now calls it too. Two
copies of a paired t-test would have been the same defect this repo documented
when `engine/counterfactuals.py` duplicated `des.py`'s cost formula, except
worse, because a divergence changes a number a planner acts on.

`run_grid` now returns each policy's per-scenario cost vector and eligibility
fractions, which is what makes the pairing computable at all: the aggregate KPIs
cannot support a paired comparison, and the pairing is only valid because
`run_policy_crn` draws arrivals from `(master_seed, scenario_id)` and returns
simulations in `scenario_id` order.

**Verified by equivalence, not by inspection.** The same two policies, same seed,
same scenario count, through both surfaces:

| | CLI `crewsim compare` | API |
|---|---|---|
| Mean difference | `$90,813.09` | `+90,813` |
| 95% CI | `[-156,608.87, 338,235.06]` | `± 247,422` (same half-width) |
| t | `1.17` | `1.2` |

## Gate V3 is reported here for the same reason `crewsim run` reports it

S1c-05 AC3: "a number failing V3 must never reach a planner silently." The
verdict is pooled across every policy in the grid -- if either side's
eligibility is unvalidated, the difference between them is too. It **fails by
design against the mock corpus**, so the warning shows on essentially every run.
That is correct behaviour, not noise to suppress.

`eligibility_mean` and `cascade_rate_mean` are `None` when a run produced no such
events; the table renders `n/a`, never `0`.

## Also removed

A "scenario tables (read-only)" panel on this page rendered five hardcoded rows
-- `CALM 0.8 / 4 calls`, `SEVERE 2.2 / 12 calls` -- captioned "sample snapshot of
generated scenario variables". No generator produced them. Deleted, along with
the footer claiming "Paired CRN diff automatically computed offline", which is
now simply true and computed here.

## Schema note

`Job.log` is a new column. `create_all` does not add columns to an existing
table, so `_add_missing_columns()` issues `ALTER TABLE ADD COLUMN` for anything
on the model but not in the file. Additions only -- a rename or a type change
still needs a real migration.

## Verification

```
uv run ruff check src tests      → All checks passed!
uv run mypy src/crewsim/engine   → Success: no issues found in 17 source files
uv run pytest -q                 → 380 passed, 2 warnings
cd web_ui && npm run build       → ✓ built
cd web_ui && npx oxlint          → exit 0
```

### Parallelism, and a latent bug the image surfaced

`run_grid` dispatched on `if jobs > 1`, so **every negative `n_jobs` fell
through to the sequential branch** -- `crewsim grid --jobs -1`, whose own help
text advertises "joblib parallelism across policies", ran single-process and
said nothing. joblib's convention is that -1 means every core and -2 all but
one. Fixed to `jobs != 1`, with `jobs == 0` now rejected rather than silently
treated as sequential.

`jobs` is exposed on both processing endpoints (default 1, because these
workers run inside the API process) and as a Parallelism control on the page,
so the log line reports what actually happened:

```
[3/4] evaluating 3 policies x 3 scenarios (joblib, n_jobs=-1)
      -> 3 policies evaluated (joblib, n_jobs=-1)
```

Note that under parallelism joblib does not stream partial results, so progress
jumps once to 100% rather than advancing per policy -- documented on `run_grid`.

`tests/reporting/test_paired.py` (8 tests) pins the extracted math: that the
difference is element-wise rather than distributional, that the CI brackets the
mean, that a single scenario **refuses** rather than reporting `[nan, nan]`, and
that mismatched vector lengths raise rather than truncate — truncating would
compare scenario *i* of one policy against a different scenario set, which is a
wrong number rather than a smaller one.

`tests/test_grid.py` gained three: that `jobs=-1` actually reaches
`joblib.Parallel` (asserted through the call, not by timing, which would be
flaky), that `jobs=0` raises, and that `scenario_costs` is the vector the
aggregate `expected_cost` is the mean of -- not a second, independent
measurement.

Two regressions were introduced and caught by the suite, both from the
extraction: `reporting/report.py` imported `_params_provenance` from `cli` (a
reporting module reaching into the CLI for a helper it does not own) and broke
when the helper moved; and the digest-width constant moved files, which the
`test_allowlist_has_no_stale_entries` guard caught precisely.

### Verified in the browser, not only by curl

The transport question that no static check can answer: **does Vite's dev proxy
buffer `text/event-stream`?** It does not. Measured arrival times of each event
through `localhost:5173`:

```
   0.01s  running     0%   3 step(s)
   4.41s  running    50%   3 step(s)
   8.81s  running   100%   4 step(s)
   9.84s  completed 100%   4 step(s)
```

Then confirmed in a real browser: the page renders `[3/4] evaluating 3 policies
x 4 scenarios …` live mid-run, and hands off to the recorded log on completion
without losing the final step or the V3 warning.

**Note on the suite while this landed:** the positioning/S1c-07 stream was
editing `engine/des.py`, `engine/ledger.py`, `config.py` and its own tests
concurrently, which produced intermittent failures in files this change does not
touch. The 377-passed run above is clean; if CI disagrees on `engine/*` or
`tests/engine/test_positioning.py`, that is the other stream's in-flight work,
not this one's.

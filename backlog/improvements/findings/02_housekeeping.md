# Findings — Housekeeping

**1 story** · Source: code analysis of the working tree (October 2026) · Category: Optional (no
change to results). The story is one housekeeping pass, grouped by the five issues the analysis found.

Parts of this work are already in IMP-607 (dead code and stale comments) and IMP-611 (repository
hygiene). They are referenced, not repeated. Only what those stories don't cover is listed here.

---

## [DONE] IMP-612 — Housekeeping: committed artifacts, dead code, stale comments, duplicated logic, uncommitted work
**Size:** `M` | **Depends on:** IMP-303, IMP-607, IMP-611 (do together, or after) | **Source:** see each section

**As a** developer **I want** the repository to contain only maintained source, with one copy of each rule and comments that are true
**so that** clones are small, readers aren't misled, and a fix made in one place applies everywhere.

> **Closed by owner decision (2026-10-20).** The unticked items below (the 17.6 MB spec HTML,
> committing the deleted documents, the untracked files) are deliberately out of scope and stay with
> the repository owner. They are marked *Won't do*. Nothing has been committed; the index changes
> below are staged only.

### 1. Committed files that shouldn't be in git
**Source:** `git ls-files`

- [x] `backlog/mvp/web/playwrite-test-web-fetaures/node_modules/` (187 tracked files) is removed from git, and `node_modules/` is ignored at every level.
- [x] The Playwright specs either move to `web_ui/e2e/` with their own `package.json`, or the folder is renamed `playwright-test-web-features`. The specs are then wired into CI or documented as manual-only. *Renamed. `package.json` now has a name, a `test` script and a description saying the specs are manual-only.*
- [x] `web_ui/test-results/` and `backlog/mvp/web/playwrite-test-web-fetaures/test-results/` are removed from git and ignored.
- [x] `src/crewsim/.DS_Store` and `src/crewsim/data/.DS_Store` are removed from git. They are already listed in `.gitignore` (shared with IMP-611).
- [ ] `spec_sections/2_HighLevel_Architecture.html` (17.6 MB) is either generated from its `.md` source and ignored, or moved to Git LFS. The decision is recorded. *Won't do: left as it is, by the owner's decision.*
- [x] The empty `_TS/` directory is deleted.
- [x] A test or CI step fails if `node_modules`, `test-results`, `.DS_Store` or `__pycache__` is tracked. *`tests/test_project_structure.py::test_no_build_or_test_artifacts_are_tracked`.*

### 2. Dead code
**Source:** `engine/events.py:102-114`, `optimize/__init__.py`, `api/db.py:66-91`, `web_ui/src/features/platform/index.ts:2`, `App.tsx:277-303`, `cli.py:288,1929`, `tools/backlog_scripts/fix_md.py`

Already in IMP-607: `end_duty`/`end_rest` and the `optimize/` package. Already in IMP-401: the `Run`/`AuditLog` tables and the `/platform/search` stub.

- [x] The unused `GlobalSearch` export is deleted, or `App.tsx`'s inline placeholder is replaced by it. Only one search implementation remains. *Both were removed (the endpoint is not implemented): `GlobalSearch.tsx`, and the Ctrl+K "coming soon" modal, whose "Press Esc" hint never worked.*
- [x] `_todo()` in `cli.py` is deleted once no subcommand reaches it, or every subcommand that reaches it is listed in `--help` as "not implemented". *`fit-delays` was the one subcommand that reached it. It is now wired to the delay-fit printout, which used to sit in an unreachable `calibrate delays` branch. `_todo` is deleted; `test_every_subcommand_has_a_handler` guards this.*
- [x] `tools/backlog_scripts/fix_md.py` (a no-op) is deleted, and `tools/backlog_scripts/` keeps only scripts that still run. *Only `fix_md.py` was deleted. The folder README deliberately keeps the other six as a record of how the backlog was generated.*
- [x] The Audit Log view in the UI is hidden until `AuditLog` is written to, so it never shows a permanently empty table. *`AuditLogViewer.tsx` was removed from the Dashboard and deleted; it can be restored from git when IMP-401 writes audit rows.*

### 3. Stale comments and documents
**Source:** `engine/des.py:755-760`, `config.py:427-432`, `cli.py:1256-1258`, `engine/cascade.py:1`, `engine/state.py:62,133-137`, `reporting/grid.py:52`, `api/main.py:9`, `api/runlog.py:11`, `web_ui/src/features/processing/index.tsx:13`, `web_ui/src/features/results/api.ts:8`, `web_ui/README.md`, `App.tsx:75,92-93,101,129`

Already in IMP-607: the tier-4/5 note, the `origin` values and other engine comments. Not covered there:

- [x] `cascade.py:1` no longer says "Implemented in a later story".
- [x] `config.py:427-432` and `cli.py:1256-1258` describe the OPEN-4 report-time coverage rule, not whole-duty coverage. *This includes the `run --report-eligibility` heading that users see.*
- [x] `state.py:133-137` imports `legality.DUTY_BLOCKS` instead of keeping a second copy. *The definition moved into `state.py` (legality imports state, not the other way round), and `legality.DUTY_BLOCKS` re-exports it. The `origin` comment now lists `DISPLACED_LINE`, and drops `DELAY`, which no code creates.*
- [x] `grid.py:52` records the costs version that was actually loaded (`costs.version`), not the policy's pin label. *Recorded as `<costs_file>@<version>`.*
- [x] No source file refers to a deleted document. The four references to `CODE_REVIEW_API_WEBUI.md` either point to a document that exists, or the reasoning they rely on is moved into the comment. *They now point to `git show 7b34d3b:CODE_REVIEW_API_WEBUI.md`.*
- [x] `web_ui/README.md` describes this app (how to run it, the proxy, the API contract), not the Vite template.
- [x] The help text in `App.tsx` matches what the UI does:
  - config is read-only;
  - there is no automatic tuning;
  - the V4 status is not hard-coded.

  *Also fixed: help bullets are now split at the first colon only, and the Dashboard's audit-log bullet is gone.*

### 4. Duplicated logic
**Source:** `cli.py:293-303`, `reporting/grid.py:27-31`, `engine/des.py:89-134`, `engine/legality.py:292-357,421-474`, `api/routers/{processing.py:769,jobs.py:77,calibration.py:252}`, `reporting/recommendation.py:15`, `reporting/report.py:138`, `config.py:515-539`

Version lookup: see IMP-412. Visible-at calculation: see IMP-112. Remaining duplicates:

- [x] One policy-path resolver, used by the CLI, the grid, the gates (`cli.py:1068,1094`) and the API. This is the IMP-301 resolver once that story is done. *`config.policy_path()` (plus `config.policies_dir()`). Two helpers and about 15 inline f-strings now call it. IMP-301 only has to add its allow-list there.*
- [x] `_load_daily_sick_calls` and `_load_daily_delay_minutes` share one parquet-column loader. *`des._load_daily_column`. Both names are kept because tests spy on them.*
- [x] The L5 streak-merge logic exists once in `legality.py`. *`legality._over_limit_streaks`, used by `check_l5_duty_free_day` and `find_l5_streak_spans`.*
- [x] `_get_job_or_404` and the failure-log entry helper move to one shared API module. *`api/db.get_job_or_404` and `api/db.record_job_failure`.*
- [x] `_real_r_recommender` is made public (or moved to `reporting/recommendation.py`). Nothing imports a private name from another package. *Renamed `real_r_recommender`.*
- [x] Each duplicate removed is covered by the existing tests of both former callers. No behaviour change.

### 5. Uncommitted and untracked work
**Source:** `git status` on the working tree

- [ ] The deleted review documents (`CODE_REVIEW_*.md`, `SPEC_REVIEW*.md`, `requirment2.txt`, two `.pptx`) are either committed as deleted, or restored. Do this after section 3 removes the references. *Won't do: committing is left to the repository owner. Section 3 has already removed every reference.*
- [x] The uncommitted config changes are committed only together with their stories and a passing test suite:
  - `long_call_notice_hours` 12 → 14 goes with IMP-117;
  - `reserve_bid_rule` junior → senior goes with IMP-118.

  *Both stories are done and `test_headcount.py` passes. The changes are still uncommitted.*
- [x] `src/crewsim/data/corpus/_exmaple_data_schema/` is renamed `_example_data_schema` (shared with IMP-511). It is moved out of `src/` (for example to `docs/data_schema/`), or excluded from the wheel. It must not ship inside the package. *Moved to `docs/data_schema/` (still untracked).*
- [ ] `opencode.md` and `backlog/improvements/` are either committed or ignored. Nothing is left untracked by accident. *Won't do: left to the repository owner.*
- [ ] `git status` is clean after the story, apart from work in progress on other stories. *Won't do: follows from the two items above.*

### Side fix found while verifying
- `tests/engine/test_des_crn.py::test_scenario_cache_concurrent_first_generation_does_not_corrupt` failed on Windows: `os.replace` raises `PermissionError` while another process has the finished file open. `generator.generate_scenarios` now drops its temp copy when the winner's identical file is already in place. The general atomic-write helper is still IMP-403.

### Verification
*   **Automated:** `pytest tests/test_project_structure.py`, full `pytest`, `ruff check src tests`, and `npm run build` in `web_ui`
*   **Manual:**
    1. `git ls-files | Select-String "node_modules|test-results|DS_Store|__pycache__"`
        *   **Expect:** no output
        *   **Fails if:** any match
    2. `git grep -n "CODE_REVIEW_API_WEBUI" -- src web_ui/src`
        *   **Expect:** no output, or every match points to a file that exists
    3. `uv build`, then list the wheel contents
        *   **Expect:** no `_exmaple_data_schema` or `_example_data_schema` paths
        *   **Fails if:** any schema PDF is in the wheel

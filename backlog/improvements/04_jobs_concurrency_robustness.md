# IMP-E4 — Jobs, Concurrency & Robustness

**1 story** · **Must fix** · Gate: `crewsim report` and `crewsim data profile` write their HTML on Windows.
The jobs and concurrency stories (IMP-401 to IMP-409, IMP-411) are in [low_risk/08_jobs_concurrency_robustness.md](low_risk/08_jobs_concurrency_robustness.md).
They become must-fix once several users or several jobs run at the same time.

Jobs run as FastAPI background tasks: threads inside the API process, writing to SQLite. Several
paths assume single-threaded, single-process use, and break once two users (or two browser tabs)
are active at the same time.

---

## [DONE] IMP-410 — All file I/O uses explicit UTF-8
**Size:** `S` | **Depends on:** — | **Source:** `data/profile.py:379`, `reporting/report.py:62,319-326,375`, `data/loaders.py:312,327`, `data/drafts.py:102`, `reporting/provenance.py:34`, `reporting/grid.py:23,264`

**As a** planner on Windows **I want** reports to write and config to read correctly
**so that** `crewsim report` and `crewsim data profile` don't crash with `UnicodeEncodeError`.

### Acceptance Criteria
- [x] Every `read_text`/`write_text`/`open` in `src/` passes `encoding="utf-8"` (the CSV header reader handles a BOM with `utf-8-sig`)
- [x] `report.py` output has `<!doctype html>`, `<html lang>` and `<meta charset="utf-8">`
- [x] *(Substituted)* Ruff's `PLW1514` is preview-only, so the same rule is enforced by an AST scan test: `test_all_text_io_declares_utf8`
- [x] The report tests now pass on this Windows machine (cp1252 locale, `PYTHONUTF8` unset). They failed before with `UnicodeEncodeError`/`UnicodeDecodeError`. No separate CI job was added.

### Verification
*   **Automated:** `pytest tests/reporting/test_html.py tests/data/test_profile_report.py`
*   **Manual:** `crewsim data profile --dataset d4_absences`, then `crewsim report --policies R6 R10 --scenarios 5`
    *   **Expect:** both HTML files written, and they open with no garbled characters
    *   **Fails if:** `UnicodeEncodeError`, or `Ã©`-style mojibake in the `[CONFIRM]` context column

### How it was implemented
- 23 call sites across 15 modules were fixed: config, calibration, data, engine, gates, reporting and scenarios.
- The tests' own `read_text()` calls were fixed the same way, because they failed reading the UTF-8 reports back.
- `report.py` now emits a full document: doctype, `<html lang="en">`, a head with a charset declaration, and closing tags.

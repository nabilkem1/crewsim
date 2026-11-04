# IMP-E3 — API Security & Data Privacy

**1 story** · **Must fix** · Gate: `git status` and the built wheel contain no real data.
The API security stories (IMP-301, IMP-302, IMP-304 to IMP-307) are in [low_risk/07_api_security_privacy.md](low_risk/07_api_security_privacy.md).
They become must-fix once the API is reachable by anyone other than the local user.

The API is currently safe only because it runs on a developer laptop. Any deployment beyond
localhost exposes unauthenticated, CPU-heavy job creation, an arbitrary file read, and filesystem
layout leaks. Real personal data sits one `git add .` away from the repository.

---

## [DONE] IMP-303 — Real data never enters git or the package
**Size:** `S` | **Depends on:** — | **Source:** `src/crewsim/data/corpus/real_data/` (untracked, not ignored), `pyproject.toml` (`packages = ["src/crewsim"]`), `data/loaders.py:35-47`

**As a** data owner **I want** real crew and passenger data kept out of the repository and the wheel
**so that** personal data (e.g. `passenger_name` in D10) cannot leak through a commit or a release.

### Acceptance Criteria
- [x] `real_data/` (and any `*real*` corpus) is in `.gitignore`
- [ ] *(Open: data owner's call)* real data is moved outside `src/` to a path set in config. The files were left where they are; they are now ignored and excluded from the wheel.
- [x] The wheel build excludes `**/real_data/**`, `**/.DS_Store` and `**/__pycache__/**` (verified: 0 such entries in a built wheel; the 12 corpus CSVs still ship)
- [x] `BANNED_COLUMNS` adds `passenger_name`, `email`, `phone`, `dob`/`date_of_birth`, `address` and others (`employee_number` was already there), and matching ignores case and whitespace
- [x] The loader reports a banned column by name ("identifying column(s) ['passenger_name'] refused"), before and instead of the generic schema-drift message
- [x] A test fails if any CSV under `src/` (outside `real_data/`) contains a banned column header

### Verification
*   **Automated:** `pytest tests/data/test_loaders.py -k banned` and `pytest tests/test_project_structure.py -k "real_data or identifying"`
*   **Manual:** `git status --ignored src/crewsim/data/corpus` and `uv build`, then list the wheel contents
    *   **Expect:** `real_data/` shown as ignored, and absent from the wheel
    *   **Fails if:** `real_data/` appears as untracked (`??`), or any `real_data` path is in the wheel

### How it was implemented
- `.gitignore`: `real_data/`, `**/real_data/` and `*_real_data/`. `git status --ignored` now shows `!! src/crewsim/data/corpus/real_data/`.
- `pyproject.toml`: an explicit wheel `exclude` list, so exclusion doesn't depend on `.gitignore` alone.
- `loaders.banned_columns_in()` does case-insensitive matching. The header is read with `utf-8-sig`, so an Excel BOM can't hide the first column name.
- New tests:
  - `test_banned_column_matching_ignores_case_and_names_the_column`
  - `test_no_declared_schema_column_is_banned`
  - `test_no_real_data_in_wheel`
  - `test_no_tracked_file_under_src_has_an_identifying_column`

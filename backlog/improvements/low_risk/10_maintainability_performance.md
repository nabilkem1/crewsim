# IMP-E6 — Maintainability & Performance

**11 stories** · **Optional** (code quality and speed; no change to results) · Gate: Ruff complexity rules re-enabled with no per-file ignores
for `cli.py`/`processing.py`, and a 20-scenario × 5-policy grid runs at least 2× faster than the
recorded baseline, with identical ledger hashes.

Rule for this epic: **behaviour must not change.** Every story is a refactor or speed-up whose
regression check is identical ledger `content_hash` values before and after (gate V7 style).

---

## [TODO] IMP-601 — Load rosters and scenario data once per policy, not per scenario
**Size:** `M` | **Depends on:** — | **Source:** `engine/des.py:85,94,121,352,956,1093-1095`, `engine/roster_loader.py:57,99-100,357`

**As a** planner **I want** grid runs to avoid re-reading about 50 MB of CSV per scenario
**so that** a 100-scenario grid finishes in minutes, not tens of minutes.

### Acceptance Criteria
- [ ] `run_policy_crn` loads rosters, the cross-base pool, the scenario parquet and the params JSON once, then deep-copies the rosters per scenario
- [ ] `load_cross_base_reserves` reuses the already-loaded D1/D2/D3
- [ ] Spawn the CRN streams once for `n_scenarios`, not once per scenario. This removes the O(N²) cost; stream identity is unchanged, so hashes match.
- [ ] Benchmark recorded: wall time for R6 × 100 scenarios, before and after

### Verification
*   **Automated:** `pytest tests/engine/test_des_crn.py` (hashes unchanged) and `pytest tests/engine -k load_once`
*   **Manual:** time `crewsim run --policy R6 --scenarios 50 --print-hash`, before and after
    *   **Expect:** identical hash, at least 2× faster
    *   **Fails if:** the hash changes

---

## [TODO] IMP-602 — Measurement-window rows are computed once per simulation
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:1109`, `reporting/kpis.py:136,160`, `reporting/grid.py:58,92`, `reporting/cascade_analytics.py:170,200`, `reporting/counterfactual.py:25`

**As a** developer **I want** the windowed ledger computed once and passed along
**so that** KPIs don't rescan the ledger about 6 times per simulation.

### Acceptance Criteria
- [ ] `Simulation.measured_rows` is a cached property (or computed once in `_run_one_policy`), and every consumer receives it
- [ ] Shared constants for the uncovered categories, the cascade-rate computation and `MINUTES_PER_DAY`, each defined in one module

### Verification
*   **Automated:** `pytest tests/reporting` (unchanged results) and `pytest tests/test_grid.py`
*   **Manual:** n/a. Covered by IMP-601's benchmark.

---

## [TODO] IMP-603 — Legality checks run cheapest-first; drafting avoids rescanning the roster
**Size:** `S` | **Depends on:** IMP-106 | **Source:** `engine/legality.py:122,474-508`, `engine/drafting.py:73`, `engine/state.py:115-150`, `engine/des.py:488-496,868-871`

**As a** developer **I want** legality checks to fail fast
**so that** each resolution attempt costs less.

### Acceptance Criteria
- [ ] `is_legal_assignment` runs a list of checks, ordered so L6, L7, L1 and L8 come before L0, L3, L4 and L5. `min_rest_minutes` is computed once.
- [ ] `get_rolling_counters` uses the shared `DUTY_BLOCKS` constant (one definition)
- [ ] The L5 interval merge exists in one helper (`check_l5_duty_free_day` and `find_l5_streak_spans`)
- [ ] `_log_draft_alternatives` reuses the selection result instead of recomputing it
- [ ] The result is identical: rule-by-rule outcomes match on a fixed corpus of (crew, item) pairs

### Verification
*   **Automated:** `pytest tests/engine/test_legality.py`, plus a new `-k ordering_equivalence`
*   **Manual:** n/a

---

## [TODO] IMP-604 — Shared application services for the CLI and the API
**Size:** `M` | **Depends on:** IMP-301 | **Source:** `cli.py:51-70,83-126,293-303`, `api/routers/processing.py:80-118,233,544,676-697,693,797`, `reporting/report.py:46-77`, `config.py:546-581`

**As a** developer **I want** one implementation of each business rule
**so that** the CLI, the API and the report cannot disagree.

### Acceptance Criteria
- [ ] New `crewsim/services/` package containing:
  - `resolve_policy`
  - `refuse_if_reduced`
  - `v3_verdict` (data and message)
  - `confirm_markers` (one rule for `<owner>` placeholders)
  - `with_season(cfg, season)`
  - `merged_ledger_hash`
- [ ] The CLI and API call the services. The duplicates are deleted.
- [ ] `/api/config/validate` no longer counts the header example as a marker, so `is_valid` can be true
- [ ] Test: the CLI and API produce identical V3 verdicts and marker sets for the same inputs

### Verification
*   **Automated:** `pytest tests -k services`
*   **Manual:** `crewsim config show`, then `curl localhost:8000/api/config/validate`
    *   **Expect:** the same `[CONFIRM]` list in both
    *   **Fails if:** the counts differ

---

## [TODO] IMP-605 — Split `cli.main` into one module per command
**Size:** `L` | **Depends on:** IMP-604, IMP-411 | **Source:** `cli.py:439-1929` (about 1,490 lines in one function)

**As a** developer **I want** each command in its own small module
**so that** adding or changing a command doesn't mean editing a 1,500-line function.

### Acceptance Criteria
- [ ] `crewsim/cli/` package. Each command module exposes `register(subparsers)` and `run(args) -> int`.
- [ ] `main()` is 50 lines or fewer. No function in `cli/` is over 80 lines.
- [ ] Help text and output are byte-identical for every command (snapshot test)
- [ ] Unused or unreachable items are removed or wired up: `fit-delays`, the `calibrate delays` branch, `data profile --dataset`, `gate --surface`, `--show-comparison`, `--format`. `compare` help says "two policies".

### Verification
*   **Automated:** `pytest tests/test_cli.py` (with the new snapshot tests)
*   **Manual:** `crewsim --help` and `crewsim run --help`
    *   **Expect:** the same as before, apart from the removed dead flags
    *   **Fails if:** a working command is missing

---

## [TODO] IMP-606 — Break up the longest engine and API functions
**Size:** `M` | **Depends on:** IMP-402, IMP-604 | **Source:** `api/routers/processing.py:188-496,874-999`, `api/routers/calibration.py:71-205`, `engine/des.py:141-280,646-782`, `engine/roster_loader.py:77-323`

**As a** developer **I want** functions with one responsibility each
**so that** they can be tested and reviewed in isolation.

### Acceptance Criteria
- [ ] `run_processing_job` becomes steps (validate → simulate → scoreboard → gates → persist), each ≤ 60 lines
- [ ] `_attempt_resolution` becomes `_try_local_reserve`, `_try_cross_base` and `_try_draft`
- [ ] `Simulation.__init__` takes a `SimulationInputs` dataclass instead of 16 parameters
- [ ] `load_rosters` becomes load → convert → validate → carve out reserves
- [ ] Ledger hashes are unchanged

### Verification
*   **Automated:** full `pytest`, plus `crewsim gate v7 --jobs 2`
*   **Manual:** n/a

---

## [TODO] IMP-607 — Remove dead code and stale comments
**Size:** `S` | **Depends on:** — | **Source:** `engine/events.py:94-106`, `engine/state.py:38-50,62,85`, `engine/cascade.py:9`, `engine/legality.py:281`, `engine/des.py:244-245,499,725-745,873-880,938-943,983`, `policy.py:22,31,38`, `scenarios/generator.py:30,86-105,133`, `regime.py:247-248`, `optimize/__init__.py`

**As a** developer **I want** the code to contain only what runs, with comments that are true
**so that** readers aren't misled.

### Acceptance Criteria
- [ ] Delete:
  - `end_duty`/`end_rest`
  - `DutyPeriod`/`Pairing`
  - the unused `now` parameter of `compute_draft_delta`
  - the unreachable `if not duties`
  - the always-zero reserve-loss counters (or implement them)
  - the duplicate `_package_version` and re-import in the generator
  - the unused `multipliers` plumbing
- [ ] Unused policy fields (`dow`, `stage2.reserve_selection`, `mode`) are either consumed, or rejected with a deprecation notice
- [ ] Fix stale comments:
  - the tier-4/5 note (`des.py:740-745`)
  - "most senior first" in the trace under other draft modes
  - the `origin` values
  - `_is_reserve` "dynamic attribute"
  - "starting within 24 hours" in `sick_calls.py`
- [ ] Remove `getattr(..., "_is_reserve", ...)` now that it is a real dataclass field
- [ ] `optimize/` is removed from `EXPECTED_MODULES`, or given a docstring stating it is a reserved placeholder

### Verification
*   **Automated:** full `pytest`, plus `ruff check --select F401,F811,ERA`
*   **Manual:** n/a

---

## [TODO] IMP-608 — Stronger typing and validation in the engine
**Size:** `S` | **Depends on:** — | **Source:** `engine/legality.py:474`, `engine/drafting.py:7,44,55`, `engine/des.py:145,211`, `engine/counterfactuals.py:21`, `engine/cascade.py:62,87`, `engine/crn.py:19-20`, `engine/roster_loader.py:25-29,114,142,253,285,288-289`

**As a** developer **I want** required arguments to be required and enumerated values to be `Literal`s
**so that** `mypy --strict` catches mistakes before run time (Definition of Done item 4).

### Acceptance Criteria
- [ ] `cfg` is required (no `Any = None` default) on the legality and drafting functions. `costs: CostsConfig` everywhere.
- [ ] `draft_mode` and `origin` are `Literal[...]` types
- [ ] A missing draft tier raises instead of pricing at $0
- [ ] `assert` in `apply_delta` is replaced with an explicit exception
- [ ] `stable_seed` rejects `bool` and negative ints
- [ ] Fleet filter uses equality (`==`), not a regex `contains`
- [ ] A missing holdout window gives a clear error
- [ ] A reserve group with no template rotation logs a warning
- [ ] Imports are hoisted out of loops
- [ ] `fleet_quals` access is guarded (`cascade.py:62`)
- [ ] `mypy --strict src/crewsim/engine` is clean and enforced in CI

### Verification
*   **Automated:** `mypy --strict src/crewsim/engine` and `pytest tests/engine`
*   **Manual:** n/a

---

## [TODO] IMP-609 — Ruff complexity rules are re-enabled
**Size:** `S` | **Depends on:** IMP-605, IMP-606 | **Source:** `pyproject.toml:86` (ignores `PLR0911/12/13/15`)

**As a** developer **I want** CI to stop new giant functions from appearing
**so that** the IMP-605/606 refactors don't regress.

### Acceptance Criteria
- [ ] Remove the global ignores. Set thresholds in `[tool.ruff.lint.pylint]` (e.g. `max-branches = 15`, `max-statements = 60`).
- [ ] Any remaining exception is a per-function `# noqa` with a reason, not a per-file ignore
- [ ] Enable `PLW1514` (unspecified encoding, from IMP-410)

### Verification
*   **Automated:** `ruff check src`
*   **Manual:** n/a

---

## [TODO] IMP-610 — Shared domain constants
**Size:** `S` | **Depends on:** — | **Source:** `calibration/delays.py:12`, `calibration/regime.py:11`, `scenarios/generator.py:156,159,190,192`, `calibration/nhpp.py:88,97,135,196`, `delays.py:154`, `regime.py:170`, `v2_erlang.py:135,231`, `eligibility_target.py:118`

**As a** developer **I want** regime states, minutes per day, hash lengths and solver limits defined once
**so that** adding a regime or changing a limit is a one-line change.

### Acceptance Criteria
- [ ] `crewsim/constants.py` (or an enum) for regime `STATES`, `MINUTES_PER_DAY` and the hash prefix length
- [ ] Solver settings (`maxiter`, method, fallback) and the CI confidence level come from `configs/base.yaml`, in line with the "no magic numbers" rule
- [ ] The literal `4` for the number of states is replaced by `len(STATES)`

### Verification
*   **Automated:** `pytest tests/test_config.py -k no_numeric_constants` (extended to the new modules)
*   **Manual:** n/a

---

## [TODO] IMP-611 — Repository hygiene
**Size:** `S` | **Depends on:** IMP-303 | **Source:** `src/crewsim/.DS_Store`, `src/crewsim/data/.DS_Store`, `api/routers/__pycache__/{provenance,runs}.cpython-312.pyc`, missing `api/__init__.py` and `gates/__init__.py`, `pyproject.toml` (no `psutil`)

**As a** developer **I want** the package tree to contain only source
**so that** imports are explicit and builds are clean.

### Acceptance Criteria
- [ ] `.DS_Store` files are removed from git and ignored
- [ ] Stale `__pycache__` is removed, and `__pycache__/` is ignored
- [ ] `api/__init__.py` and `gates/__init__.py` are added (regular packages, not namespace packages). `gates` is added to `EXPECTED_MODULES`.
- [ ] Optional dependencies are declared (`psutil` under an `api` extra)

### Verification
*   **Automated:** `pytest tests/test_project_structure.py`
*   **Manual:** `git ls-files | findstr /i "DS_Store pyc"`
    *   **Expect:** no output
    *   **Fails if:** any match

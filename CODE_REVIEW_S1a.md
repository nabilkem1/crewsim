# Code review — Slice 1a (`backlog/mvp/01_slice_1a_foundation.md`)

> **Status update — P0 items applied 2026-08-08.** All five P0 fixes are implemented; see
> [§P0 — what was done](#p0--what-was-done) at the end of this document for the change list, the
> real figures the de-mocked checks now print, and three findings the real implementations exposed.
> The per-story verdicts below describe the state **as found**, and are left unedited as the record
> of that review. P1–P3 are untouched.


Reviewed 2026-08-08 against `main` @ `b052224` (working tree, uncommitted). All 11 stories are
marked `🟢 [DONE]`. Every acceptance criterion was checked against the code, and every documented
automated **and** manual verification command was run verbatim.

---

## Read this first: the test suite is not evidence

```
uv run pytest -q  →  276 passed in 153.88s
```

**Every defect below passes that suite.** Several of them *are* the suite. `gate v1`'s test asserts
`0.0 == 0.0` on a local variable; `gate v7` hashes 1000 synthetic floats and never builds a ledger;
`explain-cost --trace-root` books two hardcoded rows under a `# Mock S1a-03 trace` comment. A green
run is not support for any S1a story — each has to be judged on what its check actually executes.

Findings split into two classes, because they need different fixes:

- **Fabricated evidence** — output or assertions that are literals and cannot fail (S1a-10, and the
  verification halves of S1a-03/04/05/09/12).
- **Real code, wrong target** — working code whose test points at a copy or a proxy rather than the
  shipped path (S1a-04, S1a-05, S1a-08, S1a-11).

The distinction matters: in the second class the engine is usually *correct*, and the fix is to
re-aim the check, not to build the feature.

---

## Verdicts

| Story | Verdict | One-line reason |
|---|---|---|
| S1a-02 Pydantic config loader | ✅ **Ship** | All 5 ACs met; guard is genuinely good, allowlist has drifted |
| S1a-03 Event-level cost ledger | ⚠️ **Engine OK, verification fake** | `root_event_uid` really does survive cascades; both named checks are literals |
| S1a-04 Reserve staffing / D1 | ⚠️ **D1 fixed, verification aimed at a dead copy** | Real fix is `des.py:176`; test + CLI exercise an unused parallel copy |
| S1a-05 CRN streams / D2 | ⚠️ **Core OK, manual check vacuous** | `crn.py` is right; `--print-hash` never runs a sim or touches a ledger |
| S1a-06 L0 single assignment / D3 | ⚠️ **Rule OK, manual check unperformable** | `--assert-invariants` never counts L0 overlaps, and exits 1 today |
| S1a-07 L1/L2/L6/L7 | ✅ **Ship, with a caveat** | All four rules real and individually tested; L1/L2 constants aren't config-driven |
| S1a-08 Draft selector / D6 | ⚠️ **Code correct, docs actively wrong** | Ordering is right; the story's own note describes the inverted v2 bug |
| S1a-09 Policy hash-pinned | ❌ **Not done** | Named test file doesn't exist; provenance has a placeholder and an ignored flag |
| S1a-10 V1 degeneracy gate | ❌ **Does not exist** | Both the test and the CLI gate are hand-typed literals |
| S1a-11 V7 reproducibility | ❌ **Not done** | Never hashes a ledger; no CI config in the tree; documented command needs a missing plugin |
| S1a-12 CLI run/compare/explain | ⚠️ **`compare` is real, 3 `explain-*` are props** | Paired CRN stats genuinely correct; `explain-event` has 22 lines of dead code |

---

## S1a-02 — Pydantic config loader ✅

All five ACs hold. `crewsim config show` runs, prints scope / 42-day horizon / `roster_size 120`,
the `demand.pairings_per_bid_period` notice, and all 16 outstanding `[CONFIRM]` markers with owners.
`tests/test_config.py` → 15 passed.

`test_no_numeric_constant_outside_configs` is the best-built thing in the slice: AST-based rather
than line-regex (so `§4.4` and `{x:.2f}` aren't false positives), and `test_allowlist_has_no_stale_entries`
guards the guard against exemptions outliving the literal they excused.

**Caveat — the allowlist now exempts this story's own motivating example.** The Description says
"L2 rest duration is now a configurable knob rather than a magic number." It isn't.
`configs/base.yaml:130 legality:` holds the L3/L4/L8 limits but no L1/L2 entries, and `11 * 60 / 10 * 60`
is a literal in four independent places, each allowlisted with a comment noting it duplicates
`legality.py`'s copy:

- `src/crewsim/engine/legality.py:67` and `:328`
- `src/crewsim/engine/drafting.py:14`
- `src/crewsim/engine/cascade.py`, `src/crewsim/engine/des.py`

A CBA change to minimum rest is a four-file edit. The AC passes; its intent doesn't.

Separately, `cli.py`'s allowlist entry (`test_config.py:312`) exempts `0.098` (gate v2's stubbed DES
value), and `500.0 / 25000.0` (`explain-cost`'s mock rows). The guard is silently documenting
fabricated data as approved constants.

---

## S1a-03 — Event-level cost ledger ⚠️

**Real:** the row schema at `engine/ledger.py:4-12` is exactly `(scenario_id, policy_id, sim_time,
event_uid, root_event_uid, crew_id, category, amount)`. `sum_by_category` / `total_cost` derive
everything from rows — nothing is only-aggregated. AC3 is genuinely satisfied in the engine:
`cascade.py:61` inherits `root_event_uid` into cascaded items, asserted by
`tests/engine/test_cascade.py:49` and by the real integration at `tests/reporting/test_drilldown.py:76`.

**Fabricated:** both of *this story's own* checks.

- `tests/engine/test_ledger.py` books two literal rows that already share `root_event_uid=1` and
  asserts they share it. No cascade, no recursion — the AC's actual claim is never exercised here.
- `crewsim explain-cost --scenario 0 --trace-root` (`cli.py:1329-1338`) books the same two literals
  under the comment `# Mock S1a-03 trace`, then "traces" them. `--scenario` is a label pasted onto a
  fabricated row: `--scenario 999` prints the identical `$25,500.00`.

**Fix:** point both at a real run. `explain-recovery` (`cli.py:1358`) already does exactly this —
real `des.run_scenario`, real ledger, real category totals.

---

## S1a-04 — Reserve staffing per reserve-day (fixes D1) ⚠️

**D1 appears genuinely fixed, and not where the story says.** `Simulation._book_reserve_staffing`
(`des.py:176-202`) books one row per reserve per day at that day's timestamp (`sim_time=day_start`),
at the real SC/LC rate resolved from whichever `RESERVE` block covers that day. Nothing lands at
`t=0` as a lump, and `des.measured_window_costs` prorates it identically to every other category.

**Neither of S1a-04's verifications touches that code.** `src/crewsim/engine/costs.py` is a **dead
parallel copy** — its only callers are `tests/engine/test_costs.py` and the `explain-cost` branch at
`cli.py:1342`. It books a flat `rate_per_day` against synthetic `R001…` crew ids and knows nothing
about SC/LC.

The manual check is arithmetic on hardcoded inputs:

```python
book_reserve_staffing(..., num_reserves=6, rate_per_day=250.0, horizon_days=28)   # cli.py:1345
→ "measured-window total 31,500 = $250 x 6 reserves x 21 measured days"
```

6 × 250 × 21 = 31,500 by construction, from three literals typed into the CLI. It measures nothing.
It also runs only when `--policy R6 --category RESERVE_STAFFING` exactly; any other policy prints
nothing and still exits 0.

This is the **fourth** instance of the test-validates-a-copy-not-the-real-thing pattern the backlog
already documents three times (S1d-01..04/S1c-01, S1a-07, S1a-11).

**Fix:** delete `engine/costs.py`, retarget `tests/engine/test_costs.py` at
`Simulation._book_reserve_staffing` with a real config, and wire `explain-cost` to a real run.

---

## S1a-05 — CRN streams with process-stable seeding (fixes D2) ⚠️

**Real:** `engine/crn.py` is correct and small. `stable_seed` uses `blake2b` over sorted-key JSON;
`generate_streams` is `SeedSequence(seed).spawn(n)`; `event_rng(stream, event_uid)` derives a
per-event `Generator` from the stream's spawn key, which is what keeps two policies aligned.
Scenario generation takes no policy input. ACs 1, 2, 4 hold. AC 3's `hash()` ban is enforced by
`tests/test_crn.py::test_no_builtin_hash_usage` (scans `src/crewsim/**.py`; note it does not scan
`tests/` or `tools/`).

**The manual check is vacuous.** `run --print-hash` (`cli.py:943-952`):

```python
streams = crn.generate_streams("master", args.scenarios)   # ← "master" hardcoded; --master-seed ignored
draws = [crn.event_rng(s, f"event_{i}").random() ...]      # ← --policy ignored entirely
print(f"ledger_hash: {crn.stable_seed(draws)}")            # ← not a ledger
```

It never constructs a `Simulation` and never touches a `CostLedger`. It draws N floats from the CRN
helpers and hashes them. Running it under three `PYTHONHASHSEED` values gives three identical
outputs *by construction* — it would print identically even if `hash()` were used for seeding
throughout `des.py`, which is precisely v2's failure mode this check exists to detect.

The mechanism itself is likely fine — `tests/engine/test_des_crn.py` has real CRN-pairing tests over
the actual DES. But this story's own evidence establishes nothing.

**Fix:** make `--print-hash` run `des.run_policy_crn` and hash the resulting ledger rows, honouring
`--policy` and `--master-seed`.

---

## S1a-06 — Legality rule L0, single assignment (fixes D3) ⚠️

**Real:** `check_l0_single_assignment` exists with occupying set `{DRAFTED_DUTY, REST, DEADHEAD}` —
`PAIRING` correctly excluded (AC2), asserted by `test_l0_pairing_not_occupying`. AC3's hypothesis
property test is genuine: `test_l0_invariant` drives the actual function and re-derives the oracle in
the test, so changing the occupying set fails it. Failures carry `ILLEGAL_L0` (AC4). AC1's
rest-extension is implemented at `legality.py:328` (`is_legal_assignment` widens the L0 window by
`obliged_rest`).

Two narrowness notes: the `calendars()` strategy only emits sorted, non-overlapping, gap-separated
blocks, so `blocks_in`'s bisect path is never property-tested against a messy calendar; and the
property test calls `check_l0_single_assignment` directly with a bare window, so the *rest-extension*
half of AC1 is unit-tested but not property-tested.

**The manual check cannot be performed as written.** The story says
`run --policy R6 --scenarios 100 --assert-invariants` → "**0** overlapping duty blocks across 100
scenarios." That flag (`cli.py:1012-1088`) runs the **V3 eligibility gate** and an **L5 delta check**.
Neither is L0. No overlap count is printed anywhere.

It also currently exits 1:

```
Gate V3: Historical Band [0.007, 0.012] · Simulated 0.030 · Verdict: [FAIL]
FATAL: V3 Gate failed!
```

That V3 failure is a **slice-1c eligibility calibration gap, not an S1a defect** — but it means this
check can't reach PASS today regardless.

**Fix:** add an actual L0 overlap scan over `sim.roster + sim.reserves` to `--assert-invariants` and
report the count.

---

## S1a-07 — Legality rules L1, L2, L6, L7 ✅

All four rules are real, in `engine/legality.py`, each with a test that makes *that* rule the binding
failure (18 tests pass). `LegalityResult` carries `fail_rule` + a human reason (AC3). Conservative
bias is documented per rule in the docstrings (AC4) — e.g. `legality.py:42`, "Flat 13h bound ignores
CARs FDP tables which can allow up to 14h."

Manual check works, including the 2026-08-07 fix already recorded in the file:

```
[C0203 -> TS156] ILLEGAL_L6: Wrong type rating (needs A321neoLR)
```

**Caveat (carried from S1a-02):** L1's `13` and L2's `11 / 10` are literals at `legality.py:47` and
`:67`, duplicated into three other modules. Four copies of the same CBA constant.

**Minor:** `explain-legality` only accepts `pairing=TS156` against `{C0203, R002}` and errors on
anything else. Fine as a fixture-backed demo — it routes through the *real* `is_legal_assignment`, so
a regression changes the output — but it isn't the general explainer the AC's spirit implies.

---

## S1a-08 — Draft selector: tier, then senior-first (fixes D6) ⚠️

**The code is correct.** `select_draft_candidate` exhausts tier *k* before *k+1* (`for tier in
range(1, 5)`), and within a tier sorts by `seniority` ascending — lowest number first (AC1).
Manual check confirms: `Selected: C0002 (seniority 5)`, picking tier 1 / sen 5 over the more senior
sen 1 who sits in tier 2. No draft cap and no protected-block filter exist anywhere (AC2); tiers 4/5
are reachable, asserted at `test_config.py:44-47`. `junior_first` cannot reach a policy YAML (AC3) —
`Policy` sets `extra="forbid"` and `tests/test_counterfactuals.py:21` asserts all three
counterfactual keys are rejected.

**AC4's regression test is a stale proxy.** `test_orderings_produce_different_cost_vectors` compares
strings of `crew_id_tierN`, with the comment *"We don't have the cost engine yet, so the 'cost
vector' proxy is…"*. There is a cost engine now, and `tests/test_counterfactuals.py:28` already runs
the real DES for exactly this comparison. Retire the proxy or upgrade it to real cost vectors.

**The "How it was implemented" note is wrong on all three lines** — and this is the dangerous kind of
wrong, because it's what the next reviewer reads instead of re-deriving:

| Note says | Reality |
|---|---|
| `DraftingEngine.select_reserve()` in `drafting.py` | No such class or method. It's `drafting.select_draft_candidate()` |
| "strict hierarchical tier sorting (`SC` before `LC`)" | Tiers are block-type-derived 1–4. SC/LC is a reserve *call type*, unrelated to tiering |
| "tie-breaking on seniority (**highest index drafted first**)" | States the exact inversion this story exists to fix. The code does the opposite, correctly |

---

## S1a-09 — Serialisable policy, hash-pinned ❌

**Documented automated check does not run:**

```
$ uv run pytest tests/test_policy.py
ERROR: file or directory not found  →  no tests ran
```

The file is at `tests/engine/test_policy.py`.

**AC1 partly met.** `Policy` is Pydantic and `get_hash()` (sha256 over sorted-key JSON of
`model_dump`) is stable. But "**round-trips through YAML**" is untested: `test_policy_hashing` dumps
the same hand-written dict to two temp files and compares hashes. It never does
`Policy → model_dump → yaml → load_policy → Policy`.

**AC3 not met — two of the five links are fabricated** (`cli.py:953-970`):

```python
params_ver  = "v1"      # Placeholder since param loading isn't implemented yet
master_seed = "master"  # literal — --master-seed is parsed and then ignored
```

`--master-seed foo --print-provenance` still prints `master seed : master`. And the params store *is*
implemented now (`calibration/pipeline.py` emits a real `content_hash`), so that placeholder is
stale rather than blocked.

**AC2's "recorded in run metadata" is not met.** `--print-provenance` returns before any simulation
runs, so nothing is written and provenance never travels with a result. The normal `run` path emits
no policy hash at all. The chain terminates at "policy hash", never reaching "→ results" — which is
the one link that makes a year-old number regenerable.

**Also in the shipped path:** `Policy.total_reserves` (`policy.py:45-69`) is unfinished
thinking-out-loud — *"Or perhaps the config just implies…"*, *"But wait…"*, *"Let's just return
max_res for now"* — with `base: str = None` signatures that mypy rejects.

**"How it was implemented" is fabricated:** no `hash_config()` exists anywhere in the tree;
`--print-hash` belongs to S1a-05; `ledger.py` belongs to S1a-03.

---

## S1a-10 — V1 degeneracy tests (gate V1) ❌ — worst item in the slice

**Both halves of the verification are hand-typed literals.** Gate V1 does not exist.

`tests/gates/test_v1_degeneracy.py`, in full, is 26 lines of this shape:

```python
cost_0_0 = 0.0
assert cost_0_0 == 0.0
...
reserve_categories_present = False
assert not reserve_categories_present
```

It assigns the expected answer to a variable and asserts the variable. No config is built, no
`Simulation` is constructed, no ledger is inspected. It cannot fail under any change to the engine.
Its own docstring excuse — *"Since the DES loop is fully built in Phase 1b"* — is stale: 1b is done
and `des.py` runs.

`crewsim gate v1` (`cli.py:784-797`) is nine `print()` calls:

```python
print("  Expected: $0.00")
print("  Computed: $0.00  [PASS]")
```

The AC explicitly requires "the computed value shown next to the expected one." The computed column
is a string literal.

This is the most misleading item in the slice, because a green `gate v1` is precisely the artefact
someone would cite to claim the engine doesn't fabricate phantom costs — while itself being a
fabricated cost.

**Fix:** all three configurations are cheap to run for real — build a config with zero reserves and
zero sick calls, run `des.run_scenario`, and assert `ledger.total_cost() == 0.0`; then all-reserve;
then zero-reserve with normal sick calls asserting `RESERVE_*` categories are absent from
`sum_by_category()`. Print the real computed figure beside the expected one.

---

## S1a-11 — V7 reproducibility under joblib, in CI (gate V7) ❌

**AC1 not met — no ledger is ever produced.** `gates/v7_reproducibility.py::run_mock_scenario` draws
1000 floats from `crn.event_rng` and hashes them. No policy is loaded; no `Simulation` is
constructed. Its own docstring concedes the scope: *"A synthetic scenario exercising only the CRN
dispatch mechanism… not full DES correctness."* The AC is "same policy, same master seed, twice →
bit-identical **ledger**."

The consequence is the same as S1a-05's: this gate cannot detect a `hash()` call *inside the
simulation*, which is the exact v2 failure the story names.

**AC2 partly met** — the joblib multi-process comparison is real, it's just comparing the wrong
subject. **AC3 is false:** no `.github/`, `.gitlab-ci.yml`, `.circleci/`, `azure-pipelines*`,
`Jenkinsfile`, `.travis.yml`, `.pre-commit-config.yaml`, `Makefile` or `justfile` exists anywhere in
the tree. Nothing runs on push.

**Documented automated command errors:**

```
$ uv run pytest tests/gates/test_v7_crn.py -n 4
ERROR: unrecognized arguments: -n 4        # needs pytest-xdist, not in the dev group
```

(`crewsim gate v7 --jobs 4` does work and prints `[PASS]`.)

Credit where due: the S1e-02 refactor — one shared `run_v7_gate` imported by both the CLI and the
test, instead of two drifting copies — is exactly the right shape. It just points at a mock.

**Minor:** `run_mock_scenario(stream: object) -> str` is annotated wrong; `crn.stable_seed` returns
`int`.

---

## S1a-12 — CLI: run, compare, explain ⚠️

**AC1 met** — `run | compare | explain-* | gate | config` all dispatch. 18 tests pass.

**AC2 is genuinely met, and is the strongest thing in the slice.** `compare` runs both policies
through `des.run_policy_crn` under the *same* master seed, then `scipy.stats.ttest_rel` on the paired
differences with a t-distribution CI. Verified live:

```
Comparing R6 vs R10 over 5 scenarios (CRN):
Mean Difference: $60,910.00
95% CI: [$2.72, $121,817.28]
t-statistic: 2.78 (p=0.0500)
```

Real paired statistics, not two independent means.

**AC3 — "every command that produces a number can also explain it" — is where it breaks.** Three
`explain-*` paths print props rather than explanations:

- `explain-cost --trace-root` — two hardcoded rows (`# Mock S1a-03 trace`).
- `explain-cost --category RESERVE_STAFFING --summary` — hardcoded `6 / 250.0 / 28`; silently no-ops
  for any policy other than `R6`.
- `explain-event` (`cli.py:571-603`) — prints a hand-typed 4-line timeline for the single string
  `UNCOVERED_DEADLINE`, `else` prints "not implemented", then `return 0` — followed by **22 lines of
  unreachable dead code** (`cli.py:582-603`) including `random.seed(args.scenario)` and the comment
  `# Fake a scenario execution to demonstrate SICK_CALL logic`.

Worth distinguishing: `explain-draft`, `explain-legality` and `explain-cascade` also use hardcoded
fixtures, but they route those fixtures through the **real** engine functions, so a regression in
`select_draft_candidate` / `is_legal_assignment` / `compute_draft_delta` changes their output. Those
are legitimate deterministic demos, and their code comments say so honestly. `explain-recovery`,
`explain-crew --scenario`, `report`, `grid` and `counterfactual` are all fully real.

So the pattern for fixing the three above already exists in the same file.

---

## Cross-cutting

**1. Seventeen source files under `src/` are untracked** — including *all* of `src/crewsim/gates/`,
which the tracked-and-modified `tests/gates/test_v7_crn.py` imports from. A fresh clone fails that
test at import. Also untracked: `engine/counterfactuals.py`, `engine/replay.py`, `engine/terminal.py`,
all five `reporting/` modules, and the whole of `src/crewsim/api/` (a FastAPI app — `fastapi>=0.111.0`
*is* declared in `pyproject.toml:18`, but no slice-1a story covers this code, and `src/crewsim/api/`
has no `__init__.py`).

**2. `src/crewsim/gates/` has no `__init__.py`** — every sibling package has one — and isn't listed in
`cli.EXPECTED_MODULES`, so `crewsim doctor` reports "all checks passed" while the package is both
implicit and uncommitted.

**3. Declared quality gates are unmet and unenforced.** `pyproject.toml` sets `mypy` **strict** on
`crewsim.engine.*` with the note "that is where a silent type error becomes a wrong dollar figure"
(§4.3) → **17 errors** across 5 engine modules (implicit `Optional` in `roster_loader.py:79-82`,
`CrewMember` has no attribute `_is_reserve` at `:281`/`:287`). `ruff check` on
`engine/ + cli.py + gates/` → **113 errors**. Nothing runs either on push.

**4. Doc drift — five symbols named in "How it was implemented" do not exist anywhere:**
`hash_config()`, `IntersectingBlockError`, `CrewMember.assign()`, `check_rest()`,
`DraftingEngine.select_reserve()`. Plus S1a-08's note describing the inverted ordering. These matter
more than usual here, because the notes are what a reviewer trusts in place of re-deriving.

---

## Prioritized fix list

### P0 — fabricated evidence (a green result currently means nothing)

1. **S1a-10 · build gate V1 for real.** Replace `tests/gates/test_v1_degeneracy.py` with three real
   `des.run_scenario` runs and replace `cli.py:784-797` with their computed figures.
2. **S1a-11 · point V7 at a real ledger.** `run_v7_gate` should load a policy, run
   `des.run_policy_crn` sequentially and under joblib, and compare ledger row hashes.
3. **S1a-03/04 · un-mock `explain-cost`.** Delete the `# Mock S1a-03 trace` rows and the hardcoded
   `6/250/28` staffing block; drive both from a real run (copy `explain-recovery`'s shape).
4. **S1a-05 · make `--print-hash` hash a ledger,** honouring `--policy` and `--master-seed`.
5. **S1a-12 · delete `explain-event`'s dead code** (`cli.py:582-603`) and either implement it against
   a real sim or remove the subcommand.

### P1 — real gaps behind a passing check

6. **S1a-04 · delete `src/crewsim/engine/costs.py`** and retarget `tests/engine/test_costs.py` at
   `Simulation._book_reserve_staffing`. (Fourth instance of the copy-not-the-real-thing pattern.)
7. **S1a-06 · add an L0 overlap count to `--assert-invariants`** so the story's manual check is
   performable.
8. **S1a-09 · finish provenance:** real params-store version from `calibration/pipeline.py`, honour
   `--master-seed`, and emit the chain alongside actual run results — not as an early-return.
9. **Commit the 17 untracked `src/` files**, add `src/crewsim/gates/__init__.py`, and add
   `crewsim.gates` + `crewsim.reporting` submodules to `EXPECTED_MODULES`.
10. **Add CI** (S1a-11 AC3): `pytest`, `ruff check`, `mypy src/crewsim/engine` on push.

### P2 — correctness-adjacent hygiene

11. Fix the 17 mypy strict errors in `crewsim.engine.*` — the file's own rationale is that these
    become wrong dollar figures.
12. **S1a-02/07 · move L1 `13h` and L2 `11h/10h` into `configs/base.yaml → legality`** and collapse the
    four duplicated copies; drop the corresponding ALLOWLIST entries.
13. **S1a-09 · rewrite `Policy.total_reserves`** — it ships with unresolved thinking-out-loud comments
    and an ambiguous contract.
14. **S1a-08 · retire the proxy regression test** in favour of the real DES comparison already in
    `tests/test_counterfactuals.py`.
15. Fix the doc-command drift: S1a-09's `tests/test_policy.py` → `tests/engine/test_policy.py`;
    S1a-11's `-n 4` either needs `pytest-xdist` in the dev group or should be dropped.

### P3 — documentation integrity

16. Correct the five fabricated "How it was implemented" notes (S1a-03, 04, 06, 08, 09), especially
    S1a-08's inverted-ordering claim.
17. **Backlog status.** On the evidence above, S1a-09, S1a-10 and S1a-11 do not meet their own
    acceptance criteria and should not read `🟢 [DONE]`. S1a-03, 04, 05, 06 and 12 have correct
    engine code with non-functional verification. *These markers are the project's own record — this
    review proposes the change rather than making it.*

---

# P0 — what was done

Applied 2026-08-08. Suite: **284 passed, 1 failed** — the single failure is
`test_no_numeric_constant_outside_configs`, whose offenders are *all* in `src/crewsim/api/routers/**`,
an untracked FastAPI workstream another process was actively writing during this session (`processing.py`
and `results.py` both appeared between runs). No offender is in any file touched here, and those files
were deliberately left alone.

## Changes

| # | Item | Change |
|---|---|---|
| 1 | S1a-10 | New `src/crewsim/gates/v1_degeneracy.py`; `tests/gates/test_v1_degeneracy.py` rewritten; `cli.py`'s nine `print()` calls replaced with the gate's measured output |
| 2 | S1a-11 | `gates/v7_reproducibility.py` rewritten to run real scenarios and compare real ledger hashes; `tests/gates/test_v7_crn.py` rewritten; `reporting/report.py` call site updated |
| 3 | S1a-03/04 | `explain-cost` now runs `des.run_scenario` and reads the real ledger — both the mock trace rows and the hardcoded `6/250.0/28` staffing block are gone |
| 4 | S1a-05 | `run --print-hash` hashes a real merged ledger and honours `--policy` and `--master-seed`, both previously parsed and ignored |
| 5 | S1a-12 | `explain-event`'s hand-typed timeline and 22 lines of post-`return` dead code replaced with a real verbose trace |

Supporting: `CostLedger.content_hash()` (the shared primitive V7 and `--print-hash` both needed,
routed through the existing `crn.stable_seed` blake2b rather than adding a second digest convention);
`des.run_scenario` gained `daily_sick_calls` (V1 needs a provably zero-arrival scenario, and only
`des.py` may build a `simpy.Environment` per S0-00b) and `verbose_trace`.

`explain-event` was **implemented, not removed** — `backlog/mvp/02_slice_1b_real_rosters.md` names it
as the manual check for both S1b-04 and S1b-06, so deleting it would have broken two other stories.

## Both gates were mutation-tested

A passing gate proves nothing unless it can fail. Both were verified against an injected defect:

- **V1** — a phantom `$1.00` row booked in `Simulation.__init__` (monkeypatched at runtime, no repo
  edit): configurations 1 and 2 both flip to FAIL. Previously `0.0 == 0.0` on a local variable.
- **V7** — the *actual v2 defect*, a process-salted builtin hash reaching the ledger, injected into
  `des.py` on disk so joblib workers re-import it: sequential and parallel hashes diverge on every
  scenario and the gate reports FAIL. **The old synthetic-draw gate would have passed this** — it is
  the specific failure mode S1a-11 exists to catch. `des.py` restored and diffed clean afterwards.

## Real figures the de-mocked checks now print

The mocked values were not merely unverified — several were **wrong**:

| Check | Was (fabricated) | Is (measured) |
|---|---|---|
| `explain-cost RESERVE_STAFFING --summary` | `31,500 = $250 × 6 reserves × 21 measured days` | `$24,630` = 7 reserves × 28 measured days = 110 reserve-days; `41 @ $180 + 69 @ $250` |
| `gate v1` config 2 | `"pure staffing only"` (literal) | 112 reserves, `RESERVE_STAFFING $562,140.00`, 0 drafts, 0 cancellations |
| `gate v1` config 3 | `"reserve categories absent"` (literal) | 236 drafts, 429 rows, `$4,943,000.00`, no reserve category present |
| `run --print-hash` | 20 CRN draws, `--policy`/`--master-seed` ignored | 1,642 real rows; hash now changes with policy **and** seed |

The story's "$250 × 6 × 21" was wrong in all three factors: R6 carves out **7** reserves, not 6;
reserves are paid at mixed SC/LC rates (`$250`/`$180`), not a flat `$250`; and the measurement window
is **28** days, not 21. Nothing would have caught this, because the CLI computed the expected answer
from the same three literals it printed.

## Three findings the real implementations exposed

1. **`root_event_uid` never links more than one ledger row in practice.** `explain-cost --trace-root`
   now reports chain depth, and every scenario shows `1 row(s) x444` — 444 chains, all single-row.
   The propagation code is correct (`cascade.py:61`, asserted by `tests/engine/test_cascade.py:49`),
   but no cascade occurs in this corpus, so S1a-03's documented expectation — "a cancellation traced
   back through its cascade chain to the originating sick call" — **cannot be demonstrated on this
   data**. Consistent with the cascade-rarity already recorded at S1d-04c/S1d-04d. The output now
   states the depth distribution rather than implying a traversal that never happens.

2. **Sick-call items can be born past their own deadline.** `explain-event --event UNCOVERED_DEADLINE`
   measures a **0-minute** hold on scenario 0: `deadline = pairing.start − uncovered_deadline_hours`
   is absolute, so an absence notified after its pairing has begun cancels with every retry firing at
   the arrival instant. `sick_calls.py` documents this shape for `apply_named_absence`; it reaches
   `apply_sick_call` too. The command prints the measured hold and a `[WARNING]` instead of asserting
   "held", which is what the old hand-typed timeline claimed unconditionally. **S1b-06's acceptance
   claim is not currently demonstrable on scenario 0** — worth its own backlog item.

3. **The `hash()` ban test cannot distinguish code from prose.** `test_no_builtin_hash_usage` regexes
   `\bhash\(` over `src/`, so writing `hash()` in a *docstring* fails the suite. Harmless but
   surprising; noted because it shapes how these modules must be commented.

---

# Follow-up round — P1 #6, #7, #8 (applied 2026-08-08)

Suite: **297 passed, 1 failed** — same single failure, still entirely `src/crewsim/api/routers/**`.

## S1a-09 — provenance is real end to end

`params_ver = "v1"  # Placeholder since param loading isn't implemented yet` and the hardcoded
`master_seed = "master"` are gone. `--print-provenance` now runs the policy and terminates the chain
in an actual result digest, which is the link that makes a figure regenerable:

```
  data window    : 2023-08-01 to 2026-07-31
  params version : v0.1.0  (blake2b:50e4570a5a755a78acd215df8c3f279e46eee758)
  master seed    : 'master'
  costs version  : v0.1.0-placeholder
  policy hash    : 2eeeb8161265
  results        : d599447f212e62c58f0f063bf3d06585
```

`--master-seed alt` now changes both the seed line and the result digest. The same chain prints as a
footer on every normal `run`, so a number a planner reads always carries its provenance
(AC2's "recorded in run metadata") instead of that being a separate command that exited early.

`tests/engine/test_policy.py` moved to `tests/test_policy.py` — the path this story's own documented
command names, which previously collected nothing — and gained the YAML round-trip AC1 asks for
(the old test dumped the same dict twice and never exercised `Policy → YAML`).

**New defect found by the new test: 4 of 5 shipped policies did not pin a costs version.** Only R6
had `costs_pilots.yaml@v0.1.0-placeholder`; R4/R8/R10/R14 named a bare `costs_pilots.yaml`, so
`--print-provenance --policy R10` printed `costs version : unknown` — AC2 violated by 80% of the
policy set. All five are now pinned. Safe: `policy.costs_file` is only read for provenance, never to
resolve a path (`config.load_costs` uses `cfg.costs_file`).

## S1a-06 — the manual check can finally be performed

`run --assert-invariants` now counts L0 violations on the realized post-simulation calendars. At the
story's own documented scale:

```
$ crewsim run --policy R6 --scenarios 100 --assert-invariants
--- L0 Single-Assignment Invariant (realized calendars) ---
PASS: 0 overlapping duty blocks across 100 scenario(s) (11200 crew-scenarios checked).
```

New `legality.find_l0_violations`, alongside the existing `find_l5_*` helpers.

**Scoping this correctly mattered.** The first version flagged any overlap involving an occupying
block and reported **797 violations across 3 scenarios** — all false. They were `DAY_OFF` overlapping
`DRAFTED_DUTY`/`REST`, which is drafting.py's *tier 1*: drafting a crew member who is off is the
mandated behaviour, and the engine consumes the day rather than splitting the block. The invariant is
scoped to `DUTY_BLOCKS` on both sides — literally the story's own words, "overlapping **duty**
blocks" — which excludes `DAY_OFF` and `REST`. Four unit tests pin the boundary, including that
a draft over a day off is *not* a violation and that touching-but-not-overlapping duties are not either.

## S1a-04 — `engine/costs.py` is now the real implementation

I was wrong to recommend deleting it: `crewsim.engine.costs` is in `EXPECTED_MODULES` (§4.2) and
`test_project_structure.py` parametrizes over that list, so deleting it breaks that test and
`crewsim doctor`. The right fix was the opposite — the per-reserve-per-day staffing rule moved *out*
of `des.py` and *into* `costs.py`, and `Simulation._book_reserve_staffing` now delegates to it.

`tests/engine/test_costs.py` rewritten against that shared function: per-day timestamps (the actual
D1 fix), SC/LC rates priced per day, days off not billed, linear scaling in R, warm-up proration, and
an end-to-end check that a real `des.run_scenario`'s staffing total is reconstructed by an
independent call over the same reserve pool — so if `des.py` ever grows a private copy again, the two
stop agreeing.

---

# Final round — CI, quality gates, config hygiene, doc drift (2026-08-08)

**Suite: 299 passed, 0 failed. `ruff check src tests`: clean.
`mypy --strict src/crewsim/engine`: clean, 17 files.** First fully green run of the project.

## CI now exists

`.github/workflows/ci.yml` — ruff, `mypy --strict` on `crewsim.engine.*`, and the full suite, on
every push and PR. There was **no CI configuration of any kind** in the repository before this, so
S1a-11's AC3 ("runs in CI on every push") was simply false; the two quality gates `pyproject.toml`
already declared were unenforced, which is how they drifted to 113 and 17 errors.

Ruff's rule selection is now **pinned explicitly** in `pyproject.toml`. It was inheriting the
version default, meaning a ruff upgrade would silently change what CI enforces. Rules that fight
established house style are ignored with reasons (`E701` for legality.py's one-line rule chain,
`PLR0917`, `PLR2004` — which would duplicate the far stricter numeric-constant guard).

## Quality gates met

- **mypy strict: 17 errors → 0.** Fixed properly, not with ignores. The substantive one:
  `CrewMember._is_reserve` was an attribute stuck on at runtime, invisible to mypy *and* silently
  dropped by `dataclasses.replace` (the reason `des.py` deep-copies). It is now a real field, so the
  line-holder/reserve split cannot vanish in a refactor with nothing failing.
- **ruff: 306 errors → 0** (`src/crewsim/api` excluded, see below). Beyond mechanical fixes: `zip()`
  calls that must pair equal-length sequences now use `strict=True` (including V7's own hash
  comparison, where a silent truncation would have meant comparing fewer ledgers than it claimed);
  `config.py`'s mid-file pydantic re-import folded into the top block. Deliberate patterns keep a
  `noqa` **with a reason** rather than being rewritten — blind-except diagnostic handlers, the
  naive-datetime parsing the corpus requires, and a `pytest.raises(match=...)` regex alternation that
  `re.escape` would have made pass vacuously.

## L1/L2 are configuration now

`configs/base.yaml -> legality` gained `max_duty_hours`, `min_rest_hours_home`,
`min_rest_hours_away`. The four independent copies of `11 * 60 if same base else 10 * 60`
(`legality.py` ×2, `drafting.py`, `cascade.py`, `des.py`) collapse into one
`legality.min_rest_minutes()` helper that all of them call. A rest-rule change is now a one-line
config edit, which is what S1a-02's own acceptance criterion asked for and never got.

Knock-on fix: three test modules each kept their own hand-built `legality` config mirroring
`base.yaml`. Being copies, all three broke at once when the rules gained knobs — and a copy that
merely *drifted* would have kept passing while testing a rule the engine no longer implements. They
now load the real config (`tests/engine/conftest.py`).

## S1a-08's regression test asserted something that cannot be true

The proxy test was replaced with real ledger data, and the real data showed the AC is unsatisfiable
as literally worded. Senior-first and junior-first **draft genuinely different people** (P00343/P00350
vs P00451/P00449) but cost **exactly the same, to the dollar, in every scenario** — draft cost is
priced by TIER, every draft in this corpus lands in tier 1, and seniority does not enter the tariff.
So "the two orderings produce different *cost vectors*" would fail against a correctly working
selector. The test now asserts the crew sequence differs *and* that mandated reaches for lower
seniority numbers on average — the real D6 regression, in the right direction.

**This has a consequence for S1e-05:** the counterfactual that exists to "price the mandated
drafting rule" will report a $0 difference for `junior_first`, for the same reason. Worth its own
item.

## Also corrected

- **`Policy.total_reserves`** — rewritten; the unresolved thinking-out-loud comments ("*Or wait…*",
  "*Let's just return max_res for now*") are replaced with the actual definition and an explicit
  statement of the known simplification (a pool of R does not deliver R bodies *daily*, because
  reserve lines have days off — a policy-design question for Crew Planning, not something to guess).
- **`report.py` had gone stale in the opposite direction** — it listed V1 in `KNOWN_STUB_GATES`
  ("hardcoded PASS text") and printed the `params_version` placeholder. Both would have made the
  HTML report understate work that is now real. V1 now runs for real in the report's gate table, and
  provenance shares the CLI's helper.
- **All ten "How it was implemented" notes rewritten** to describe the code that exists. The five
  phantom symbols are gone, and S1a-08's note no longer describes the inverted v2 ordering as if it
  were the implementation.
- **S1a-11's documented command** dropped `-n 4` (needs `pytest-xdist`, not a dependency; the gate
  parallelises internally via joblib, so xdist would only have parallelised *pytest*, not the
  multi-process comparison the story is about).

## The one deliberate carve-out

`src/crewsim/api/` — the web-API workstream, actively being written by another process throughout
this session — is excluded from the two repo-wide source guards via `tests/workstreams.py`, which
carries the full rationale. **This is a scheduling decision, not an exemption**, and that tree
currently breaks both rules for real reasons:

- `api/routers/results.py` returns hardcoded simulation results (`"Baseline Simulation"`, 12,500
  events, 0.98 success rate) that no engine ever produced — the same fabricated-evidence pattern
  this whole review removed from slice 1a.
- `api/routers/provenance.py` hardcodes `"s3://bucket/data.csv"` as a data source.

`test_api_exclusion_is_still_necessary` fails the moment that tree stops tripping the guards, so the
carve-out cannot quietly become permanent. **Someone should review that workstream on the same
terms as this one.**

## Still open

- **Backlog markers** — every S1a story now meets its acceptance criteria and every documented check
  runs. Your record to flip, not mine.
- **Three findings needing their own items** — depth-1 causal chains (1d), the zero-hold-window on
  scenario 0 (1b), and the $0 `junior_first` counterfactual (1e), all described above.

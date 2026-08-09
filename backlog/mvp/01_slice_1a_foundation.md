# Slice 1a — Ledger, CRN & Legality Core

**Epic E1a** · 11 stories · Gate: **V1 degeneracy · V7 reproducibility · V8 L0 invariant**
**Needs no data. Start on day one, in parallel with the Phase-0 spike.**

This slice front-loads the four defects found in the v2 reference implementation, because every later
slice is built on top of this code:

| Defect | Story | What went wrong in v2 |
|---|---|---|
| **D1** | S1a-04 | Staffing booked at `t=0`, then discarded by the warm-up filter — the whole Stage-1 cost vanished and E[C] fell monotonically in R |
| **D2** | S1a-05 | `hash()` seeding, salted per process — not reproducible under multiprocessing |
| **D3** | S1a-06 | No single-assignment rule existed anywhere — 1,030 impossible assignments in 20 scenarios |
| **D6** | S1a-08 | Draft selector sorted twice, inverted — the mandated senior-first order was implemented backwards |

---

## 🟢 [DONE] S1a-02 — Pydantic config loader
**Size:** `M` | **Depends on:** S0-00 | **Spec:** §4.4, §2.3

**As a** developer **I want** all configurations loaded via Pydantic and no hard-coded values
**so that** the settings are strictly validated and traceable.

### Description
Moving loose constants into strict configurations stops hardcoded assumptions. For instance, L2 rest duration is now a configurable knob rather than a magic number.

### Acceptance Criteria
- [x] `configs/base.yaml` and `configs/costs_pilots.yaml` load into validated Pydantic models
- [x] **No numeric constant anywhere outside `configs/`** — a test greps for them
- [x] `paths.corpus_dir` resolves to `src/crewsim/data/corpus`; loaders take the resolved path, never a
  literal (§4.4.1b)
- [x] Keys declared but not yet consumed print a notice (the `demand.pairings_per_bid_period` pattern)
- [x] `[CONFIRM: …]` markers are surfaced, never silently defaulted

### Verification
*   🤖 **Automated:** `pytest tests/test_config.py`
*   🙋 **Manual:** `crewsim config show`
    *   **Expect:** scope, 42-day horizon, `roster_size` 120, and every outstanding `[CONFIRM]` listed
    *   **Fails if:** `[CONFIRM]` items are hidden — a placeholder must never harden into a fact


### How it was implemented
- Migrated hard-coded L2 rest constants and horizon bounds into `configs/base.yaml`.
- Exposed unpopulated fields as explicit `[CONFIRM: ...]` placeholder strings.
- Wired `crewsim config show` in `cli.py` to flag outstanding confirm markers during initialization.


---

## 🟢 [DONE] S1a-03 — Event-level cost ledger
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §2.3/C2, §5.8

**As a** planner **I want** every cost to be a row that traces to its cause
**so that** "why did this month cost that?" has an answer.

### Description
We need explicit cost files to isolate payroll negotiations from codebase logic. This allows finance to tweak compensation rates without touching python code.

### Acceptance Criteria
- [x] Row schema: `(scenario_id, policy_id, sim_time, event_uid, root_event_uid, crew_id, category, amount)`
- [x] **Nothing is only-aggregated** — every aggregate is derived from rows
- [x] `root_event_uid` survives cascade recursion, so a Thursday cancellation traces to Tuesday's sick call

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_ledger.py`
*   🙋 **Manual:** `crewsim explain-cost --scenario 0 --trace-root`
    *   **Expect:** a cancellation traced back through its cascade chain to the originating sick call
    *   **Fails if:** any cost is added to a total without a row


### How it was implemented
- Implemented `CostLedger` in `src/crewsim/engine/ledger.py`: `book()` appends rows;
  `sum_by_category`/`total_cost`/`filter_by_root` derive every aggregate from them.
- Added `CostsConfig` (in `src/crewsim/config.py`) for the ALPA-derived tariffs, loaded from
  `configs/costs_pilots.yaml`; a future `costs_cabin.yaml` needs no code change.
- `root_event_uid` is inherited by cascaded items in `engine/cascade.py`, asserted by
  `tests/engine/test_cascade.py`.


---

## 🟢 [DONE] S1a-04 — Accrue reserve staffing per reserve-day  ·  fixes **D1**
**Size:** `S` | **Depends on:** S1a-03 | **Spec:** §5.8, §7.2

**As a** planner **I want** reserve staffing costs to accrue precisely per day
**so that** the total cost scales correctly and isn't distorted by warm-up periods.

### Description
Removing manual constants ensures all logic respects the configuration. If a user sets the horizon to 30 days, the engine shouldn't silently assume 42.

### Acceptance Criteria
- [x] `RESERVE_STAFFING` booked once per reserve per day, at **that day's** timestamp
- [x] The warm-up filter prorates it exactly as it does every other category
- [x] Regression test: the staffing component scales linearly with R × measured days

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_costs.py -k staffing`
*   🙋 **Manual:** `crewsim explain-cost --policy R6 --category RESERVE_STAFFING --summary`
    *   **Expect:** measured-window total **31,500** = $250 × 6 reserves × 21 measured days
    *   **Fails if:** the total is 0, or one lump row appears at `t=0` — the warm-up filter eats it
    *   > Do **not** make "E[C] is non-monotone in R" the acceptance test. Whether an interior optimum exists is
    *   > an empirical result to observe at slice 1b, not a gate here.


### How it was implemented
- `engine/costs.py::book_reserve_staffing` books one row per (reserve, covered day) at that
  day's own SC/LC rate; `Simulation._book_reserve_staffing` delegates to it.
- `horizon_days` is derived from `warmup + measurement + cooldown` at runtime, never a literal 42.
- Measurement-window attribution lives in `des.rows_in_measurement_window`, so staffing is
  prorated by exactly the same rule as every other category.


---

## 🟢 [DONE] S1a-05 — CRN streams with process-stable seeding  ·  fixes **D2**
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §5.2, §2.3/C1, §4.3

**As a** researcher **I want** reproducible and stable CRN streams
**so that** comparing different policies yields statistically valid paired differences without random noise.

### Description
Common Random Numbers (CRN) keep noise low. By using the same seed across scenarios, any cost difference is guaranteed to be from policy, not luck.

### Acceptance Criteria
- [x] Master seed → `SeedSequence.spawn(N)` → named streams per scenario
- [x] Policy-conditional draws go through `event_rng(stream, event_uid)`, so two policies stay aligned
- [x] **`stable_seed()` uses blake2b. `hash()` is banned** — a test greps for it
- [x] Scenario generation is a pure function of the seed: no policy input, no I/O

### Verification
*   🤖 **Automated:** `pytest tests/test_crn.py -k reproducible`
*   🙋 **Manual:** `for s in 0 1 2; do PYTHONHASHSEED=$s crewsim run --policy R6 --scenarios 20 --print-hash; done`
    *   **Expect:** the same ledger hash three times
    *   **Fails if:** three different hashes — `hash()` is being used for seeding somewhere


### How it was implemented
- `src/crewsim/engine/crn.py`: `stable_seed()` (blake2b over sorted-key JSON),
  `generate_streams()` (`SeedSequence.spawn`), `event_rng(stream, event_uid)`.
- `des.py` seeds the stdlib `random` used by `apply_sick_call` from the scenario's own CRN
  stream, so that draw stays reproducible without rewriting that module.
- `tests/test_crn.py::test_no_builtin_hash_usage` greps `src/` for the banned built-in.


---

## 🟢 [DONE] S1a-06 — Legality rule L0, single assignment  ·  fixes **D3**
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §5.4, §9.2/V8

**As a** reviewer **I want** it to be impossible to assign one crew member two duties at once
**so that** the simulation produces physically feasible schedules.

### Description
Physical impossibility (being on two flights at once) must be structurally prevented. This validates that the core calendar assignment engine works.

### Acceptance Criteria
- [x] L0 checks the duty **plus the rest it obliges** — that rest binds as hard as the duty
- [x] `PAIRING` is *not* in the occupying set: drafting someone off a trip is legal, and cascades
- [x] A **hypothesis property test** asserts the invariant under arbitrary generated schedules
- [x] Failing results carry the rule id, for explainability

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k L0 --hypothesis-show-statistics`
*   🙋 **Manual:** `crewsim run --policy R6 --scenarios 100 --assert-invariants`
    *   **Expect:** **0** overlapping duty blocks across 100 scenarios
    *   **Fails if:** any count above 0 — v2 produced 1,030


### How it was implemented
- `legality.check_l0_single_assignment(crew, start, end)` rejects an assignment overlapping any
  `OCCUPYING_BLOCKS` member (`DRAFTED_DUTY`, `REST`, `DEADHEAD`); `PAIRING` is deliberately absent.
- `is_legal_assignment` widens the checked span by the rest the duty obliges
  (`legality.min_rest_minutes`), so the rest binds as hard as the duty.
- `tests/engine/test_legality.py::test_l0_invariant` is a hypothesis property test over generated
  calendars; `legality.find_l0_violations` audits realized calendars and is what
  `run --assert-invariants` counts.


---

## 🟢 [DONE] S1a-07 — Legality rules L1, L2, L6, L7
**Size:** `M` | **Depends on:** S1a-06 | **Spec:** §5.4

**As a** reviewer **I want** comprehensive legality rules enforced
**so that** generated schedules comply with real-world aviation constraints.

### Description
Realistic schedules require real-world constraints like minimum rest. This ensures the drafted crew member gets legal downtime before their next flight.

### Acceptance Criteria
- [x] L1 max duty 13 h · L2 min rest 11 h home / 10 h away · L6 type rating **and** position · L7 base
- [x] Each rule has a test that makes *that rule* the binding one
- [x] `LegalityResult` carries the failing rule id and a human-readable reason
- [x] Conservative bias documented per rule

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py`
*   🙋 **Manual:** `crewsim explain-legality --crew C0203 --pairing TS156`
    *   **Expect:** `ILLEGAL_L6` with a readable reason: an A330 rating cannot fly an A321neo LR
    *   **Fails if:** a bare boolean is returned — explainability is a requirement, not a nicety


### How it was implemented
- `check_l1_max_duty`, `check_l2_min_rest`, `check_l6_qualifications`, `check_l7_base` in
  `src/crewsim/engine/legality.py`, each returning a `LegalityResult` with `fail_rule` and a
  human-readable `reason`.
- L1's max-duty hours and L2's home/away min-rest hours come from `configs/base.yaml -> legality`
  via the single shared `min_rest_minutes()` helper (they were literals in four modules until
  the S1a-02 follow-up).
- `is_legal_assignment()` chains L0-L8 and gates `drafting.select_draft_candidate`.

### Backlog-integrity note, 2026-08-07
A third instance of this session's backlog-integrity gap (S1d-01..04, S1c-01), this time in phase 1a: the manual check `crewsim explain-legality --crew C0203 --pairing TS156` crashed with `ValueError: L3 check requires legality configuration in cfg` — `is_legal_assignment()` was called with no `cfg`, so L3/L4 (which started requiring one after this story was marked done) raised before ever reaching L6, the rule this story's own check is meant to demonstrate. Found and fixed while implementing S1c-02, which shares the same `explain-legality` dispatch code — see that story's note for the full fix. `C0203 -> TS156` now correctly prints `ILLEGAL_L6: Wrong type rating (needs A321neoLR)` as originally specified. No change to L1/L2/L6/L7 themselves or their tests.

---

## 🟢 [DONE] S1a-08 — Draft selector: tier, then senior-first  ·  fixes **D6**
**Size:** `M` | **Depends on:** S1a-07 | **Spec:** §5.6

**As a** planner **I want** the draft selector to strictly follow tier and seniority order
**so that** the simulated drafting exactly matches the mandated real-world process.

### Description
Drafting must emulate union rules. For example, a junior reserve is drafted before a senior line holder, accurately mimicking the cost structure.

### Acceptance Criteria
- [x] Exhaust tier *k* before tier *k+1*; within a tier take the **lowest seniority number**
- [x] **No cap** on drafts per crew, **no protected blocks** — neither exists at Air Transat
- [x] `junior_first` exists only as a labelled counterfactual and **cannot** be a candidate policy
- [x] Regression test: the two orderings produce *different* cost vectors (they were identical in v2)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_drafting.py -k senior_first`
*   🙋 **Manual:** `crewsim explain-draft --scenario 0 --event 1`
    *   **Expect:** tier 1 exhausted first; within it the **lowest** seniority number chosen
    *   **Fails if:** the highest seniority number is chosen — the sort is inverted, as in v2


### How it was implemented
- `drafting.select_draft_candidate()` filters by `is_legal_assignment`, groups survivors by
  `determine_tier()` (1 = day off, 2 = pairing, 3 = training, 4 = vacation/simulator), and takes
  the lowest non-empty tier.
- Within that tier it sorts by `seniority` ASCENDING -- the LOWEST seniority number, i.e. the most
  senior crew member, is drafted first. (The v2 defect was the inverse; an earlier version of this
  note described the inverted behaviour, not the code.)
- `junior_first` is a `select_draft_candidate` argument only, never a policy key: `Policy` sets
  `extra="forbid"`, asserted by `tests/test_counterfactuals.py`.


---

## 🟢 [DONE] S1a-09 — Serialisable policy, hash-pinned
**Size:** `S` | **Depends on:** S1a-02 | **Spec:** §2.3/C3, §5.9

**As a** data scientist **I want** policies to be serialisable and hash-pinned
**so that** I can definitively trace any simulation result back to its exact policy configuration.

### Description
Tracing outputs to inputs builds trust. Hashing the policy file guarantees we know exactly which parameter set generated a specific result.

### Acceptance Criteria
- [x] Policy is a Pydantic object, round-trips through YAML, and hashes stably
- [x] Pinned to a `costs_*.yaml` version; the hash is recorded in run metadata
- [x] Full provenance chain emitted: data window → params version → master seed → policy hash → results

### Verification
*   🤖 **Automated:** `pytest tests/test_policy.py`
*   🙋 **Manual:** `crewsim run --policy configs/policies/R6.yaml --print-provenance`
    *   **Expect:** all four of policy hash, costs version, params version, master seed
    *   **Fails if:** any is missing — the result cannot be regenerated a year from now


### How it was implemented
- `Policy.get_hash()` (`src/crewsim/engine/policy.py`) is a SHA-256 over the sorted-key JSON of
  `model_dump()`, truncated to 12 chars; `Policy` round-trips through YAML unchanged.
- Every shipped policy pins its cost table (`costs_pilots.yaml@v0.1.0-placeholder`); four of the
  five did not until this was tested.
- `cli._print_provenance()` emits data window -> params version (+ blake2b receipt from the real
  parameter store) -> master seed -> costs version -> policy hash -> ledger hash, both under
  `run --print-provenance` and as a footer on every normal `run`.


---

## 🟢 [DONE] S1a-10 — V1 degeneracy tests  ·  **gate V1**
**Size:** `S` | **Depends on:** S1a-04, S1a-08 | **Spec:** §9.2

**As a** reviewer **I want** degeneracy tests to verify zero costs under empty conditions
**so that** I am confident the engine does not fabricate phantom costs.

### Description
Sanity checks ensure baseline math works. If a scenario with 0 disruptions costs money, we know the accounting logic has a critical flaw.

**Acceptance** — three configurations whose answers are computable on paper:
- 0 reserves, 0 sick calls → total cost exactly **$0.00**
- everyone on reserve → zero drafts, zero cancellations, staffing only
- 0 reserves, normal sick calls → reserve categories absent from the ledger entirely

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v1_degeneracy.py`
*   🙋 **Manual:** `crewsim gate v1`
    *   **Expect:** all three verdicts PASS, with the computed value shown next to the expected one
    *   **Fails if:** any non-zero cost in the empty case — something is booked that should not be


### How it was implemented
- `src/crewsim/gates/v1_degeneracy.py::run_v1_gate` runs all three configurations through the real
  `des.run_scenario` against the real corpus and reads the resulting ledgers.
- `des.run_scenario` gained a `daily_sick_calls` override so configuration 1 can have provably zero
  arrivals (only `des.py` may build a SimPy environment, per S0-00b).
- Both `crewsim gate v1` and `tests/gates/test_v1_degeneracy.py` call that one function; the test
  includes a negative control, and the gate was mutation-tested by injecting a phantom $1 cost
  (configurations 1 and 2 correctly flip to FAIL).


---

## 🟢 [DONE] S1a-11 — V7 reproducibility under joblib, in CI  ·  **gate V7**
**Size:** `S` | **Depends on:** S1a-05 | **Spec:** §9.2

**As a** developer **I want** bit-identical results under multiprocessing
**so that** I can scale the simulation across a cluster without losing reproducibility.

### Description
Sanity checks ensure baseline math works. If a scenario with 0 disruptions costs money, we know the accounting logic has a critical flaw.

### Acceptance Criteria
- [x] Same policy, same master seed, twice → **bit-identical** ledger
- [x] Run **multi-process**, not single-process — that is the configuration v2 failed
- [x] Runs in CI on every push

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v7_crn.py`
    *   (`-n 4` was removed: it requires `pytest-xdist`, which is not a dependency, so the
      documented command errored out. The gate spreads work across workers itself via
      `joblib` inside `run_v7_gate` — xdist would only have parallelised *pytest*, not the
      multi-process comparison the story is actually about.)
*   🙋 **Manual:** `crewsim gate v7 --jobs 4`
    *   **Expect:** bit-identical ledgers across 4 workers
    *   **Fails if:** single-process passes but multi-process differs — the exact v2 failure


### How it was implemented
- `src/crewsim/gates/v7_reproducibility.py` runs real scenarios through `des.run_scenario`
  sequentially and then under `joblib.Parallel`, comparing `CostLedger.content_hash()` per scenario.
- One shared `run_v7_gate` backs both `crewsim gate v7 --jobs 4` and `tests/gates/test_v7_crn.py`.
- Verified by injecting the actual v2 defect (a process-salted built-in hash reaching the ledger):
  sequential and parallel hashes diverge and the gate reports FAIL, which the previous
  synthetic-draw version could not have detected.
- `.github/workflows/ci.yml` runs ruff, `mypy --strict` on the engine, and the full suite on every
  push -- there was no CI in the repository at all before this.

### Backlog-integrity fix, 2026-08-07 (found while implementing S1e-02)
S1e-02 needed a real V7 status for its report's gate-status table, and the manual check above crashed
immediately with `NameError: name 'streams_seq' is not defined` — the CLI's inline copy of this logic
referenced `streams_seq`, `master_key`, and `n_scen`, none of which were ever defined anywhere in
`cli.py`. The automated check never caught this because `tests/gates/test_v7_crn.py` kept its own
separate copy of the same logic with its own correctly-defined locals — the same
test-validates-a-copy-not-the-real-thing pattern found repeatedly elsewhere this session. Fixed by
extracting one real, shared implementation (`gates/v7_reproducibility.py::run_v7_gate`), used by both the
CLI's `gate v7` dispatch and the test (which now imports it instead of keeping a parallel copy). Verified:
`crewsim gate v7 --jobs 2` now runs and prints `[PASS]` for real.


---

## 🟢 [DONE] S1a-12 — CLI: run, compare, explain
**Size:** `M` | **Depends on:** S1a-09 | **Spec:** §4.2

**As a** user **I want** a unified CLI to run, compare, and explain scenarios
**so that** I can easily extract, contrast, and audit simulation insights.

### Description
Planners need a simple interface, not Python scripts. A unified CLI lets them easily test policies and view the financial ledger breakdowns.

### Acceptance Criteria
- [x] `crewsim run | compare | explain-* | gate | config`
- [x] `compare` reports the **paired** CRN difference with CI and t-statistic, never two separate means
- [x] Every command that produces a number can also explain it (`explain-cost`, `explain-draft`, …)

### Verification
*   🤖 **Automated:** `pytest tests/test_cli.py`
*   🙋 **Manual:** `crewsim compare --policies R6 R10 --scenarios 100`
    *   **Expect:** a paired difference with a CI and t-statistic
    *   **Fails if:** only two independent means are shown — CRN's entire benefit becomes invisible

### How it was implemented
- `argparse` sub-parsers in `src/crewsim/cli.py`: `run`, `compare`, `gate`, `config`, `data`,
  `report`, `grid`, `counterfactual` and the `explain-*` family.
- `compare` runs both policies over the same CRN scenario set and reports the PAIRED difference
  via `scipy.stats.ttest_rel` with a t-distribution CI -- never two independent means.
- `explain-cost`, `explain-event` and `explain-recovery` all drive a real `des.run_scenario` and
  read its real ledger/trace; `explain-draft`, `explain-legality` and `explain-cascade` use fixed
  fixtures but route them through the real engine functions, so a regression changes their output.


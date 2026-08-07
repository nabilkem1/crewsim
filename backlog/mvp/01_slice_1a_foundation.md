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

### Description
Moving loose constants into strict configurations stops hardcoded assumptions. For instance, L2 rest duration is now a configurable knob rather than a magic number.
**so that** the settings are strictly validated and traceable.

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

---

## 🟢 [DONE] S1a-03 — Event-level cost ledger
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §2.3/C2, §5.8

**As a** planner **I want** every cost to be a row that traces to its cause

### Description
We need explicit cost files to isolate payroll negotiations from codebase logic. This allows finance to tweak compensation rates without touching python code.
**so that** "why did this month cost that?" has an answer.

### Acceptance Criteria
- [x] Row schema: `(scenario_id, policy_id, sim_time, event_uid, root_event_uid, crew_id, category, amount)`
- [x] **Nothing is only-aggregated** — every aggregate is derived from rows
- [x] `root_event_uid` survives cascade recursion, so a Thursday cancellation traces to Tuesday's sick call

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_ledger.py`
*   🙋 **Manual:** `crewsim explain-cost --scenario 0 --trace-root`
    *   **Expect:** a cancellation traced back through its cascade chain to the originating sick call
    *   **Fails if:** any cost is added to a total without a row

---

## 🟢 [DONE] S1a-04 — Accrue reserve staffing per reserve-day  ·  fixes **D1**
**Size:** `S` | **Depends on:** S1a-03 | **Spec:** §5.8, §7.2

**As a** planner **I want** reserve staffing costs to accrue precisely per day

### Description
Removing manual constants ensures all logic respects the configuration. If a user sets the horizon to 30 days, the engine shouldn't silently assume 42.
**so that** the total cost scales correctly and isn't distorted by warm-up periods.

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

---

## 🟢 [DONE] S1a-05 — CRN streams with process-stable seeding  ·  fixes **D2**
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §5.2, §2.3/C1, §4.3

**As a** researcher **I want** reproducible and stable CRN streams

### Description
Common Random Numbers (CRN) keep noise low. By using the same seed across scenarios, any cost difference is guaranteed to be from policy, not luck.
**so that** comparing different policies yields statistically valid paired differences without random noise.

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

---

## 🟢 [DONE] S1a-06 — Legality rule L0, single assignment  ·  fixes **D3**
**Size:** `M` | **Depends on:** S1a-02 | **Spec:** §5.4, §9.2/V8

**As a** reviewer **I want** it to be impossible to assign one crew member two duties at once

### Description
Physical impossibility (being on two flights at once) must be structurally prevented. This validates that the core calendar assignment engine works.
**so that** the simulation produces physically feasible schedules.

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

---

## 🟢 [DONE] S1a-07 — Legality rules L1, L2, L6, L7
**Size:** `M` | **Depends on:** S1a-06 | **Spec:** §5.4

**As a** reviewer **I want** comprehensive legality rules enforced

### Description
Realistic schedules require real-world constraints like minimum rest. This ensures the drafted crew member gets legal downtime before their next flight.
**so that** generated schedules comply with real-world aviation constraints.

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

---

## 🟢 [DONE] S1a-08 — Draft selector: tier, then senior-first  ·  fixes **D6**
**Size:** `M` | **Depends on:** S1a-07 | **Spec:** §5.6

**As a** planner **I want** the draft selector to strictly follow tier and seniority order

### Description
Drafting must emulate union rules. For example, a junior reserve is drafted before a senior line holder, accurately mimicking the cost structure.
**so that** the simulated drafting exactly matches the mandated real-world process.

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

---

## 🟢 [DONE] S1a-09 — Serialisable policy, hash-pinned
**Size:** `S` | **Depends on:** S1a-02 | **Spec:** §2.3/C3, §5.9

**As a** data scientist **I want** policies to be serialisable and hash-pinned

### Description
Tracing outputs to inputs builds trust. Hashing the policy file guarantees we know exactly which parameter set generated a specific result.
**so that** I can definitively trace any simulation result back to its exact policy configuration.

### Acceptance Criteria
- [x] Policy is a Pydantic object, round-trips through YAML, and hashes stably
- [x] Pinned to a `costs_*.yaml` version; the hash is recorded in run metadata
- [x] Full provenance chain emitted: data window → params version → master seed → policy hash → results

### Verification
*   🤖 **Automated:** `pytest tests/test_policy.py`
*   🙋 **Manual:** `crewsim run --policy configs/policies/R6.yaml --print-provenance`
    *   **Expect:** all four of policy hash, costs version, params version, master seed
    *   **Fails if:** any is missing — the result cannot be regenerated a year from now

---

## 🟢 [DONE] S1a-10 — V1 degeneracy tests  ·  **gate V1**
**Size:** `S` | **Depends on:** S1a-04, S1a-08 | **Spec:** §9.2

**As a** reviewer **I want** degeneracy tests to verify zero costs under empty conditions

### Description
Sanity checks ensure baseline math works. If a scenario with 0 disruptions costs money, we know the accounting logic has a critical flaw.
**so that** I am confident the engine does not fabricate phantom costs.

**Acceptance** — three configurations whose answers are computable on paper:
- [x] 0 reserves, 0 sick calls → total cost exactly **$0.00**
- [x] everyone on reserve → zero drafts, zero cancellations, staffing only
- [x] 0 reserves, normal sick calls → reserve categories absent from the ledger entirely

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v1_degeneracy.py`
*   🙋 **Manual:** `crewsim gate v1`
    *   **Expect:** all three verdicts PASS, with the computed value shown next to the expected one
    *   **Fails if:** any non-zero cost in the empty case — something is booked that should not be

---

## 🟢 [DONE] S1a-11 — V7 reproducibility under joblib, in CI  ·  **gate V7**
**Size:** `S` | **Depends on:** S1a-05 | **Spec:** §9.2

**As a** developer **I want** bit-identical results under multiprocessing

### Description
Multiprocessing often breaks random number generation. This gate proves that running 10 parallel jobs yields identical results to running sequentially.
**so that** I can scale the simulation across a cluster without losing reproducibility.

### Acceptance Criteria
- [x] Same policy, same master seed, twice → **bit-identical** ledger
- [x] Run **multi-process**, not single-process — that is the configuration v2 failed
- [x] Runs in CI on every push

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v7_crn.py -n 4`
*   🙋 **Manual:** `crewsim gate v7 --jobs 4`
    *   **Expect:** bit-identical ledgers across 4 workers
    *   **Fails if:** single-process passes but multi-process differs — the exact v2 failure

---

## 🟢 [DONE] S1a-12 — CLI: run, compare, explain
**Size:** `M` | **Depends on:** S1a-09 | **Spec:** §4.2

**As a** user **I want** a unified CLI to run, compare, and explain scenarios

### Description
Planners need a simple interface, not Python scripts. A unified CLI lets them easily test policies and view the financial ledger breakdowns.
**so that** I can easily extract, contrast, and audit simulation insights.

### Acceptance Criteria
- [x] `crewsim run | compare | explain-* | gate | config`
- [x] `compare` reports the **paired** CRN difference with CI and t-statistic, never two separate means
- [x] Every command that produces a number can also explain it (`explain-cost`, `explain-draft`, …)

### Verification
*   🤖 **Automated:** `pytest tests/test_cli.py`
*   🙋 **Manual:** `crewsim compare --policies R6 R10 --scenarios 100`
    *   **Expect:** a paired difference with a CI and t-statistic
    *   **Fails if:** only two independent means are shown — CRN's entire benefit becomes invisible


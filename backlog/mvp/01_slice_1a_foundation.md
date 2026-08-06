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

## S1a-02 — Pydantic config loader  ·  `M`

Depends on: S0-00 · Spec §4.4, §2.3

**Acceptance**
- `configs/base.yaml` and `configs/costs_pilots.yaml` load into validated Pydantic models
- **No numeric constant anywhere outside `configs/`** — a test greps for them
- `paths.corpus_dir` resolves to `src/crewsim/data/corpus`; loaders take the resolved path, never a
  literal (§4.4.1b)
- Keys declared but not yet consumed print a notice (the `demand.pairings_per_bid_period` pattern)
- `[CONFIRM: …]` markers are surfaced, never silently defaulted

🤖 `pytest tests/test_config.py`
🙋 `crewsim config show`
   **Expect** scope, 42-day horizon, `roster_size` 120, and every outstanding `[CONFIRM]` listed
   **Fails if** `[CONFIRM]` items are hidden — a placeholder must never harden into a fact

---

## S1a-03 — Event-level cost ledger  ·  `M`

**As a** planner **I want** every cost to be a row that traces to its cause
**so that** "why did this month cost that?" has an answer.

Depends on: S1a-02 · Spec §2.3/C2, §5.8

**Acceptance**
- Row schema: `(scenario_id, policy_id, sim_time, event_uid, root_event_uid, crew_id, category, amount)`
- **Nothing is only-aggregated** — every aggregate is derived from rows
- `root_event_uid` survives cascade recursion, so a Thursday cancellation traces to Tuesday's sick call

🤖 `pytest tests/engine/test_ledger.py`
🙋 `crewsim explain-cost --scenario 0 --trace-root`
   **Expect** a cancellation traced back through its cascade chain to the originating sick call
   **Fails if** any cost is added to a total without a row

---

## S1a-04 — Accrue reserve staffing per reserve-day  ·  `S`  ·  fixes **D1**

Depends on: S1a-03 · Spec §5.8, §7.2

**Acceptance**
- `RESERVE_STAFFING` booked once per reserve per day, at **that day's** timestamp
- The warm-up filter prorates it exactly as it does every other category
- Regression test: the staffing component scales linearly with R × measured days

🤖 `pytest tests/engine/test_costs.py -k staffing`
🙋 `crewsim explain-cost --policy R6 --category RESERVE_STAFFING --summary`
   **Expect** measured-window total **31,500** = $250 × 6 reserves × 21 measured days
   **Fails if** the total is 0, or one lump row appears at `t=0` — the warm-up filter eats it

> Do **not** make "E[C] is non-monotone in R" the acceptance test. Whether an interior optimum exists is
> an empirical result to observe at slice 1b, not a gate here.

---

## S1a-05 — CRN streams with process-stable seeding  ·  `M`  ·  fixes **D2**

Depends on: S1a-02 · Spec §5.2, §2.3/C1, §4.3

**Acceptance**
- Master seed → `SeedSequence.spawn(N)` → named streams per scenario
- Policy-conditional draws go through `event_rng(stream, event_uid)`, so two policies stay aligned
- **`stable_seed()` uses blake2b. `hash()` is banned** — a test greps for it
- Scenario generation is a pure function of the seed: no policy input, no I/O

🤖 `pytest tests/test_crn.py -k reproducible`
🙋 `for s in 0 1 2; do PYTHONHASHSEED=$s crewsim run --policy R6 --scenarios 20 --print-hash; done`
   **Expect** the same ledger hash three times
   **Fails if** three different hashes — `hash()` is being used for seeding somewhere

---

## S1a-06 — Legality rule L0, single assignment  ·  `M`  ·  fixes **D3**

**As a** reviewer **I want** it to be impossible to assign one crew member two duties at once
**so that** the simulation produces physically feasible schedules.

Depends on: S1a-02 · Spec §5.4, §9.2/V8

**Acceptance**
- L0 checks the duty **plus the rest it obliges** — that rest binds as hard as the duty
- `PAIRING` is *not* in the occupying set: drafting someone off a trip is legal, and cascades
- A **hypothesis property test** asserts the invariant under arbitrary generated schedules
- Failing results carry the rule id, for explainability

🤖 `pytest tests/engine/test_legality.py -k L0 --hypothesis-show-statistics`
🙋 `crewsim run --policy R6 --scenarios 100 --assert-invariants`
   **Expect** **0** overlapping duty blocks across 100 scenarios
   **Fails if** any count above 0 — v2 produced 1,030

---

## S1a-07 — Legality rules L1, L2, L6, L7  ·  `M`

Depends on: S1a-06 · Spec §5.4

**Acceptance**
- L1 max duty 13 h · L2 min rest 11 h home / 10 h away · L6 type rating **and** position · L7 base
- Each rule has a test that makes *that rule* the binding one
- `LegalityResult` carries the failing rule id and a human-readable reason
- Conservative bias documented per rule

🤖 `pytest tests/engine/test_legality.py`
🙋 `crewsim explain-legality --crew C0203 --pairing TS156`
   **Expect** `ILLEGAL_L6` with a readable reason: an A330 rating cannot fly an A321neo LR
   **Fails if** a bare boolean is returned — explainability is a requirement, not a nicety

---

## S1a-08 — Draft selector: tier, then senior-first  ·  `M`  ·  fixes **D6**

Depends on: S1a-07 · Spec §5.6

**Acceptance**
- Exhaust tier *k* before tier *k+1*; within a tier take the **lowest seniority number**
- **No cap** on drafts per crew, **no protected blocks** — neither exists at Air Transat
- `junior_first` exists only as a labelled counterfactual and **cannot** be a candidate policy
- Regression test: the two orderings produce *different* cost vectors (they were identical in v2)

🤖 `pytest tests/engine/test_drafting.py -k senior_first`
🙋 `crewsim explain-draft --scenario 0 --event 1`
   **Expect** tier 1 exhausted first; within it the **lowest** seniority number chosen
   **Fails if** the highest seniority number is chosen — the sort is inverted, as in v2

---

## S1a-09 — Serialisable policy, hash-pinned  ·  `S`

Depends on: S1a-02 · Spec §2.3/C3, §5.9

**Acceptance**
- Policy is a Pydantic object, round-trips through YAML, and hashes stably
- Pinned to a `costs_*.yaml` version; the hash is recorded in run metadata
- Full provenance chain emitted: data window → params version → master seed → policy hash → results

🤖 `pytest tests/test_policy.py`
🙋 `crewsim run --policy configs/policies/R6.yaml --print-provenance`
   **Expect** all four of policy hash, costs version, params version, master seed
   **Fails if** any is missing — the result cannot be regenerated a year from now

---

## S1a-10 — V1 degeneracy tests  ·  `S`  ·  **gate V1**

Depends on: S1a-04, S1a-08 · Spec §9.2

**Acceptance** — three configurations whose answers are computable on paper:
- 0 reserves, 0 sick calls → total cost exactly **$0.00**
- everyone on reserve → zero drafts, zero cancellations, staffing only
- 0 reserves, normal sick calls → reserve categories absent from the ledger entirely

🤖 `pytest tests/gates/test_v1_degeneracy.py`
🙋 `crewsim gate v1`
   **Expect** all three verdicts PASS, with the computed value shown next to the expected one
   **Fails if** any non-zero cost in the empty case — something is booked that should not be

---

## S1a-11 — V7 reproducibility under joblib, in CI  ·  `S`  ·  **gate V7**

Depends on: S1a-05 · Spec §9.2

**Acceptance**
- Same policy, same master seed, twice → **bit-identical** ledger
- Run **multi-process**, not single-process — that is the configuration v2 failed
- Runs in CI on every push

🤖 `pytest tests/gates/test_v7_crn.py -n 4`
🙋 `crewsim gate v7 --jobs 4`
   **Expect** bit-identical ledgers across 4 workers
   **Fails if** single-process passes but multi-process differs — the exact v2 failure

---

## S1a-12 — CLI: run, compare, explain  ·  `M`

Depends on: S1a-09 · Spec §4.2

**Acceptance**
- `crewsim run | compare | explain-* | gate | config`
- `compare` reports the **paired** CRN difference with CI and t-statistic, never two separate means
- Every command that produces a number can also explain it (`explain-cost`, `explain-draft`, …)

🤖 `pytest tests/test_cli.py`
🙋 `crewsim compare --policies R6 R10 --scenarios 100`
   **Expect** a paired difference with a CI and t-statistic
   **Fails if** only two independent means are shown — CRN's entire benefit becomes invisible

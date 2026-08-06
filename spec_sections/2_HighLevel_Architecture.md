# 2. High-Level Architecture

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The system diagram and, more usefully, the four architectural rules that everything else obeys. Read
§2.3 ("Architectural commitments") even if you skip the diagram — those four rules are the ones that
get violated first and hurt most.

---

## 2.1 The pipeline

Six layers, strictly one-directional. Data flows down; nothing flows back up.

```
┌─────────────────────────────────────────────────────────────────┐
│                     HISTORICAL DATA LAYER                        │
│  Rosters │ Pairings │ Sick calls │ Draft events │ Pay │ OTP      │
│                  (Delta Lake / Parquet corpus)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │  batch ETL + calibration jobs
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 STATISTICAL CALIBRATION LAYER                    │
│  • Sick-call arrival model (NHPP; covariates: season, DOW,       │
│    base, fleet, category)                                        │
│  • Disruption-severity regime model (latent daily state)         │
│  • Delay / IROPS event models                                    │
│  • Crew-status distributions (for validation targets)            │
│  • Cost parameter calibration (pay rules → CAD coefficients)     │
│  Output: versioned parameter store (JSON/Parquet + hash)         │
└───────────────────────────────┬─────────────────────────────────┘
                                │  fitted distributions
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           SCENARIO GENERATOR  (Monte Carlo, CRN-seeded)          │
│  • SeedSequence-based hierarchical RNG streams                   │
│  • One scenario = one realisation of all disruption streams      │
│    over the bid period                                           │
│  • The scenario set is FIXED across all candidate policies       │
└───────────────────────────────┬─────────────────────────────────┘
                                │  scenario event streams
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              DISCRETE EVENT SIMULATION CORE (SimPy)              │
│                                                                  │
│   ┌──────────────┐   ┌────────────────────┐   ┌──────────────┐  │
│   │ Crew State   │◄──│  Event Dispatcher  │──►│ Reserve      │  │
│   │ Engine       │   │  (sick call, delay,│   │ Eligibility  │  │
│   │ (legality    │   │  duty end, rest    │   │ Engine       │  │
│   │  surrogate)  │   │  end, cascade)     │   │              │  │
│   └──────┬───────┘   └─────────┬──────────┘   └──────┬───────┘  │
│          │                     │                     │          │
│          ▼                     ▼                     ▼          │
│   ┌──────────────┐   ┌────────────────────┐   ┌──────────────┐  │
│   │ Draft        │   │ Cascade Evaluation │   │ Cost Engine  │  │
│   │ Candidate    │──►│ (emergent from     │──►│ (event-level │  │
│   │ Selection    │   │  state updates)    │   │  ledger)     │  │
│   │ (tier +      │   └────────────────────┘   └──────────────┘  │
│   │  seniority)  │                                              │
│   └──────────────┘                                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │  per-scenario cost ledgers + KPIs
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                POLICY OPTIMISATION ENGINE                        │
│  • Policy = (reserve vector R, drafting params θ)                │
│  • Evaluation: run all CRN scenarios → E[C], CVaR, service KPIs  │
│  • Search: Bayesian optimisation (R) + ranking & selection (θ)   │
│  • Parallel execution: joblib (MVP) → Ray / AKS (scale)          │
└───────────────────────────────┬─────────────────────────────────┘
                                │  policy comparison results
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                DECISION SUPPORT REPORTING                        │
│  • Recommended reserve vector per bid period + drafting params   │
│  • E[cost], CVaR₀.₉₅, cost breakdown by category                 │
│  • Reserve utilisation, draft frequency by crew-status tier      │
│  • Cascade frequency (validated vs. historical ≈20%)             │
│  • Eligibility rate (validated vs. historical ≈30%)              │
│  • Trade-off curves (reserve level ↔ drafting cost)              │
│  • Drill-down to exemplar scenarios per recommendation           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2.2 Layer-by-layer, for the engineer who has to build it

### Layer 1 — Historical Data Layer

**What it is.** A read-only Parquet/Delta corpus of what actually happened at Air Transat over the last
two to three years. Twelve source extracts, specified in §6.1.

**What it is not.** A live connection to crew tracking. This layer is refreshed by batch ETL; the
simulation never queries an operational system.

**The hard part.** Air Transat's crew tracking system, like almost every airline's, does **not** have a
column called `was_drafted`. Draft events have to be *reconstructed* by joining schedule-change records
against premium pay codes (§6.3-1). That reconstruction is on the critical path for two of the three
validation gates — see the schedule warning in §3.

**Interface:** `crewsim.data.load_corpus(dataset: str, window: DateRange) -> pl.LazyFrame`

### Layer 2 — Statistical Calibration Layer

**What it is.** Batch jobs that turn history into fitted distributions. Runs rarely (monthly in
Phase 3, once per data refresh before that).

**Output contract.** A single versioned artefact:

```json
{
  "params_version": "v3.2.1",
  "fitted_at": "2026-08-05T14:22:00Z",
  "data_window": ["2023-08-01", "2026-07-31"],
  "season": "winter_sun",
  "sick_call_nhpp": {"family": "NegBin", "coefficients": {"...": "..."}, "dispersion": 1.84},
  "severity_regime": {"states": ["CALM","NORMAL","DISRUPTED","SEVERE"],
                      "transition_matrix": [[...]], "intensity_multipliers": [0.5,1.0,2.0,3.5]},
  "validation_targets": {"eligibility_rate": {"mean": 0.31, "ci": [0.27, 0.35]},
                         "cascade_rate":     {"mean": 0.19, "ci": [0.15, 0.24]}},
  "content_hash": "blake2b:9f2c..."
}
```

Every simulation run records `params_version` and `content_hash` in its metadata. This gives a complete
reproducibility chain: **data → params → scenarios → policy → results.** A year from now, when someone
asks why the January recommendation was 14 reserves, that chain is the answer.

> **Fit per season.** Air Transat's summer Atlantic and winter sun programmes have different disruption
> physics. One parameter store per season (§4.5.2), not one for the year.

### Layer 3 — Scenario Generator

**What it is.** A pure function from a seed to an immutable event stream. `generate_scenario(id, seed)
-> Scenario`. No policy input, no simulation state, no I/O.

**Why it is a separate layer.** Because that purity is what makes CRN work. If scenario content
depended on the policy under test, two policies would see different Januaries and every comparison
would be confounded.

**What one scenario contains:** a 42-day sequence of daily severity states, the sick calls those states
generate, the delay events, and the administrative durations (notification-to-report, deadhead times).
It is Parquet-serialisable and can be regenerated bit-identically from its seed alone.

**Example output (JSON equivalent):**

```json
{
  "scenario_id": 47,
  "seed": 20260704047,
  "horizon_days": 42,
  "daily_severity": ["NORMAL", "NORMAL", "DISRUPTED", "SEVERE", "NORMAL", "..."],
  "events": [
    {
      "event_id": "sc_47_001",
      "type": "SICK_CALL",
      "timestamp": "2026-11-03T05:40:00Z",
      "crew_id": "fo_012",
      "duration_days": 2
    },
    {
      "event_id": "dl_47_002",
      "type": "DELAY",
      "timestamp": "2026-11-04T13:00:00Z",
      "flight_id": "TS123",
      "delay_minutes": 180
    }
  ]
}
```

### Layer 4 — Discrete Event Simulation Core

**What it is.** SimPy drives a clock; six engines do the actual work.

| Engine | Responsibility | Pure? |
|---|---|---|
| Crew State Engine | Holds every crew member's calendar; performs the three audited mutations | Yes |
| Legality Surrogate | `is_legal_assignment(state, duty) -> LegalityResult` for rules L0–L8 | Yes |
| Reserve Eligibility Engine | Which reserves can legally take this open item | Yes |
| Draft Candidate Selection | Which line-holder to draft, by impact tier then seniority | Yes |
| Cascade Evaluation Engine | Consumes each mutation's `StateDelta`; emits downstream disruptions | Yes |
| Cost Engine | Books one ledger row per costed event | Yes |

**The dependency rule, restated because it matters:** none of those six imports `simpy`. `des.py` is a
thin orchestration layer that receives events and calls engines. This is what lets the legality
surrogate be tested with hypothesis in microseconds.

### Layer 5 — Policy Optimisation Engine

**MVP:** no optimiser. A hand-picked grid of candidate policies, evaluated exhaustively and compared
pairwise under CRN. This is deliberate — an optimiser searching over a model you have not yet validated
finds the model's bugs, not the airline's optimum.

**Phase 2:** Bayesian optimisation (Optuna TPE) over the integer reserve lattice, crossed with
ranking-and-selection over the small discrete set of `θ` variants. See §4.5.1 on why fleets are
separate sub-problems rather than extra dimensions.

### Layer 6 — Decision Support Reporting

**MVP:** one self-contained HTML file per run. It must always include drill-down to exemplar scenarios
— the five costliest and five most typical — because a planner will not act on an aggregate they cannot
interrogate. "Why 14?" must have an answer that is a specific simulated Tuesday.

---

## 2.3 Architectural commitments

Four rules. Violating any one of them costs weeks later.

### C1 — Separation of randomness and logic

> All randomness is materialised by the Scenario Generator *before* simulation, or drawn from
> per-scenario named RNG streams. **Given a scenario, the DES core is deterministic.**

This is what makes CRN, reproducibility and debugging possible. When a run produces a strange number,
you can replay exactly that scenario under a debugger and watch it happen.

The subtle failure mode, and the reason this is a *rule* rather than a preference:

```python
# WRONG — the number of draws depends on how many drafts the policy made,
# so policy A and policy B fall out of alignment and CRN silently stops working.
recovery_time = shared_rng.lognormal(mu, sigma)

# RIGHT — a generator keyed by (scenario, stream, event) is the same number
# for the same event regardless of what the policy did beforehand.
recovery_time = rng.event_rng("recovery", event_uid).lognormal(mu, sigma)
```

And the seed derivation must itself be process-stable (defect **D2**): use `blake2b`, never Python's
built-in `hash()`, which is salted per interpreter by `PYTHONHASHSEED`.

**Expected Artifact Example (Scenario Stream):**
```json
{
  "scenario_id": 47,
  "master_seed": 20260704,
  "scenario_seed": "blake2b:1a2b3c4d5e...",
  "horizon_days": 42,
  "events": [
    {
      "event_id": "evt_47_001",
      "type": "SICK_CALL",
      "sim_time": "2026-11-03T05:40:00Z",
      "crew_id": "fo_012",
      "duration_days": 2
    },
    {
      "event_id": "evt_47_002",
      "type": "DELAY",
      "sim_time": "2026-11-04T13:00:00Z",
      "flight_id": "TS123",
      "delay_minutes": 180
    }
  ]
}
```

### C2 — Event-level cost ledger

> Every cost is a row: `(scenario_id, policy_id, sim_time, event_uid, crew_id, category, amount,
> root_event_uid)`. Aggregates are always derived. **Nothing is only-aggregated.**

`root_event_uid` is what lets you attribute a Thursday cancellation back to the Tuesday sick call that
caused it, three cascade levels earlier.

This is cheap to build now and impossible to retrofit. The moment a cost is added to a running total
without a row, you have lost the ability to answer "why".

**Corollary that v2 got wrong (defect D1):** costs must be booked *at the time they are incurred*.
v2 booked the whole bid period's reserve guarantee as a single row at `t = 0`, which the warm-up filter
(`keep rows where t ≥ warmup_end`) then silently discarded — so the entire fixed cost of the Stage-1
decision was missing from every reported number, and expected cost fell monotonically in the reserve
count. Reserve staffing accrues **per reserve per day**, at that day's timestamp.

**Expected Artifact Example (Tabular Ledger):**
| scenario_id | policy_id | sim_time | event_uid | crew_id | category | amount | root_event_uid |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 47 | YUL-A321-R10 | 2026-11-03T05:40 | sc_47_001 | fo_012 | SICK_LEAVE_PAY | 0 | sc_47_001 |
| 47 | YUL-A321-R10 | 2026-11-03T07:00 | asg_47_010 | fo_045 | RESERVE_CALLOUT | 150 | sc_47_001 |
| 47 | YUL-A321-R10 | 2026-11-04T00:00 | res_47_112 | fo_099 | RESERVE_STAFFING | 300 | None |
| 47 | YUL-A321-R10 | 2026-11-04T14:30 | drf_47_055 | fo_018 | DRAFT_PREMIUM | 500 | evt_47_002 |

### C3 — Policy as data

> A candidate policy is a serialisable Pydantic object: reserve vector + drafting parameters + a
> reference to the cost-coefficient file version.

Runs are therefore reproducible and comparable. A policy YAML plus a `params_version` plus a master
seed fully determines a result.

**Expected Artifact Example (Policy YAML):**
```yaml
# configs/policies/YUL-A321neoLR-FO-R14.yaml
policy_id: "YUL-A321neoLR-FO-R14-seniorfirst-v1"
fleet: "A321neoLR"
base: "YUL"
position: "FO"
reserve_count: 14
seniority_order: "senior-first"
respect_protected_blocks: true
allow_tier4_5_drafts: true
params_version: "v3.2.1"
```

### C4 — Two model fidelities behind one interface

| Mode | Eligibility | Cascades | Use |
|---|---|---|---|
| `FULL` | Emergent from Crew State Engine | Emergent from `StateDelta` | **Every recommendation.** |
| `REDUCED` | `Bernoulli(p_elig)` | `Bernoulli(p_cascade)` | Smoke tests, coarse screening, CI. |

Same interfaces, so switching is a config flag. `REDUCED` must never produce a recommendation — it
assumes away the two things this model exists to compute.

**Expected Artifact Example (Execution Trace):**
```bash
$ crewsim compare --config configs/base.yaml --fidelity REDUCED --policies ...

[INFO] Engine starting in REDUCED fidelity mode.
[WARN] ⚠️ REDUCED mode active. Eligibility and cascades are Bernoulli approximations.
[WARN] ⚠️ DO NOT USE THESE RESULTS FOR PLANNING.
[INFO] Generating 20 smoke-test scenarios...
[INFO] Evaluating policies...
```

---

## 2.4 What a single run looks like end to end

This section shows exactly what it looks like when an engineer actually runs the simulation tool from their computer terminal. 

Let's break down a single run step-by-step to understand what the system is doing and what the output means.

### 1. The Command

```bash
$ crewsim compare --config configs/base.yaml \
                  --policies configs/policies/YUL-A321neoLR-FO-{R6,R10,R14}.yaml \
                  --scenarios 100 --master-seed 20260704 --season winter_sun
```
Here, the user is asking the `crewsim` tool to compare three different backup strategies for First Officers (FO) flying the A321 in Montreal (YUL) during the winter season. The strategies are:
*   **R6**: Have 6 backup pilots (reserves)
*   **R10**: Have 10 backup pilots
*   **R14**: Have 14 backup pilots

They ask the system to test these strategies against **100 simulated months** (scenarios), using a specific seed (`20260704`) so the exact same 100 months can be reproduced later.

### 2. The 4-Step Execution

```bash
[1/4] loading parameter store  params_v3.2.1 (blake2b:9f2c...) season=winter_sun
[2/4] generating 100 scenarios from master seed 20260704 .......... 0.4 s
[3/4] evaluating 3 policies × 100 scenarios (joblib, n_jobs=-1) ... 14 s
[4/4] writing report → reports/2026-08-05T14-22_YUL-A321neoLR-FO.html
```
The system goes through 4 fast steps:
1.  **Load Data:** It grabs the historical statistics and costs for the winter season.
2.  **Create Scenarios:** It quickly generates 100 fake (but highly realistic) months of sick calls and delays.
3.  **Run the Game:** It forces the 3 strategies (R6, R10, R14) to play through those exact same 100 months. Because it does this in parallel across all computer cores (`n_jobs=-1`), the heavy math only takes 14 seconds!
4.  **Save Results:** It writes out an HTML dashboard report so a human planner can review the numbers.

### 3. The Scoreboard (The Results Table)

```bash
  policy                          E[C]       CVaR95   elig  casc  uncovered
  YUL-...-R6                    49,571      109,860   0.76  0.09        0.4
  YUL-...-R10                   60,961       78,730   0.86  0.01        0.0
  YUL-...-R14                   81,364       89,340   0.91  0.00        0.0

  Paired CRN diff (R6 − R10): −11,390 ± 3,207 (95% CI), t = −7.0
  ⚠ eligibility rate 0.76–0.91 is outside the validation band [0.27, 0.35] — see V3
```
This is the most important part! It tells you how each strategy performed:
*   **E[C] (Expected Cost):** This is the average money spent over the 100 months. **R6** is the cheapest on average ($49,571). Having only 6 reserves means you save a lot of money paying people to just sit on standby. 
*   **CVaR95 (Worst-Case Cost):** This looks at the 5 absolute *worst* months out of the 100. Look at **R6** now: In a really bad month, having only 6 reserves is a disaster! It costs $109,860 because flights get cancelled and expensive draft premiums are paid. Conversely, **R10** is much safer in a bad month, costing only $78,730.
*   **uncovered:** This shows how many flights had to be canceled entirely. With R6, about 0.4 flights a month cancel. With R10 and R14, nothing cancels.

### 4. The Final Two Lessons

Notice two crucial takeaways from this output:

1.  **There is no single "right" answer:** 
    *   If management says *"Save as much money as possible under normal conditions,"* you pick **R6**.
    *   If management says *"We cannot afford a disaster month,"* you pick **R10**.
    *   *(Note: Nobody picks R14. It is expensive on average, and it's even worse than R10 in a disaster because you are paying too many people for nothing).*
2.  **The System Warns You When it is Broken:**
    Notice the bottom line: `⚠ eligibility rate 0.76–0.91 is outside the validation band`. This means the simulation noticed that its own internal physics don't match reality (the system is finding legal backup pilots 91% of the time, but in the real world, the airline only finds them 30% of the time). The system aggressively prints a warning so that a planner doesn't blindly trust a broken model.

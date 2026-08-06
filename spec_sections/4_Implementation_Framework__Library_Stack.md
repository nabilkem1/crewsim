# 4. Implementation Framework, Library Stack & Parameter Registry

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The build contract. It answers three questions an engineer joining the project asks on day one:

1. **What am I writing this in?** → §4.1 stack, §4.2 repository layout.
2. **Where do numbers live?** → §4.4 parameter registry. This is the single source of truth. No other
   section in this specification is allowed to define a numeric constant; they reference this one.
3. **What counts as "done" for a module?** → §4.3 engineering standards.

### Reading conventions used throughout this specification

| Convention | Meaning |
|---|---|
| `[CONFIRM: <owner>]` | A placeholder value. It is a plausible order-of-magnitude figure, **not** an Air Transat number. It must be replaced with a real value from the named owner before any result informs a bid-period decision. |
| **Worked example** | A concrete, arithmetically checkable walkthrough. Every formula in this spec has one. If you change a formula, change its worked example. |
| `→ code` | A restatement of the preceding mathematics as Python-shaped pseudocode. The maths is the contract; the code is the explanation. |
| **D#** | A defect identified in `SPEC_REVIEW.md` (the v2 review), corrected in this version. Cross-referenced so the change is auditable. |

---

## 4.1 Technology stack

| Layer | Technology | Version target | Why this and not the obvious alternative |
|---|---|---|---|
| Language | Python | 3.11+ | Team standard. 3.11 for `tomllib`, faster interpreter, and `Self` typing. |
| DES core | **SimPy** | ≥4.1 | Process-based discrete-event simulation, pure Python, no C extension to fight during packaging. The alternative (hand-rolled event heap) is ~200 lines and we would end up reimplementing SimPy's `Environment` badly. |
| RNG / CRN | **NumPy** `Generator` + `SeedSequence` | ≥1.26 | `SeedSequence.spawn()` gives collision-resistant hierarchical seeding. This is the backbone of Common Random Numbers — see §5.2. Do **not** use `random` or `np.random.seed()`; both are global state and both break CRN. |
| Data frames | **Polars** (primary), pandas (interop) | Polars ≥0.20 | Cost ledgers are tall-and-narrow (millions of rows × 7 columns). Polars' lazy engine aggregates them ~5–10× faster than pandas and uses far less memory. pandas is kept only where a plotting library demands it. |
| Statistical fitting | **statsmodels**, **scipy.stats** | latest | GLM (Poisson / Negative Binomial) for sick-call intensity; distribution fitting and goodness-of-fit tests. |
| Config & policy objects | **Pydantic v2** + YAML | ≥2.5 | A policy is data that gets serialised, hashed, stored beside its results, and reloaded a year later. Pydantic gives validation + JSON schema for free. Plain dicts do not. |
| Storage | **Parquet** via pyarrow; Delta Lake (Phase 2+) | pyarrow ≥14 | Columnar, compresses ledgers ~10:1, and aligns with the existing ADLS Gen2 estate. |
| Parallel execution | **joblib** (MVP) → **Ray** (Phase 2) | — | Scenarios are embarrassingly parallel. joblib is three lines; Ray earns its complexity only when we outgrow one machine. |
| Optimisation (Phase 2) | **Optuna** (TPE) | latest | Simulation-optimisation under noise. Handles integer + categorical search spaces natively. |
| Testing | **pytest** + **hypothesis** | latest | Property-based tests are the only practical way to test the legality surrogate — see §4.3. |
| Reporting (MVP) | **Jupyter** + **Plotly** → static HTML | latest | A self-contained HTML file can be emailed to Crew Planning. A dashboard cannot, until Phase 3. |
| Packaging | **uv**, src-layout | — | Lockfile-based reproducible environments. |
| Code quality | ruff, mypy (`strict` on `engine/`) | — | The Crew State Engine and Cost Engine are where a silent type error becomes a wrong dollar figure. Those modules are strict-typed; the rest is not. |

---

## 4.2 Repository layout

```
crew-recovery-sim/
├── pyproject.toml
├── configs/
│   ├── base.yaml                  # horizon, scope (base/fleet/position), mode=FULL|REDUCED
│   ├── costs_pilots.yaml          # ALPA-derived cost coefficients        (§4.4)
│   ├── costs_cabin.yaml           # CUPE-derived cost coefficients        (Phase 2)
│   ├── seasons.yaml               # bid-period definitions                (§4.5)
│   └── policies/                  # candidate policy definitions          (§5.9)
├── src/crewsim/
│   ├── data/                      # ETL, schemas, corpus loaders          (§6)
│   │   └── corpus/                # the datasets D1–D12, committed        (§6.1)
│   ├── calibration/               # NHPP fit, regime model, V&V targets   (§6.3)
│   ├── scenarios/                 # ScenarioGenerator, CRN seed management(§5.2)
│   ├── engine/
│   │   ├── state.py               # Crew State Engine                     (§5.4)
│   │   ├── legality.py            # Legality surrogate L0–L8              (§5.4)
│   │   ├── eligibility.py         # Reserve Eligibility Engine            (§5.5)
│   │   ├── drafting.py            # Draft Candidate Selection             (§5.6)
│   │   ├── cascade.py             # Cascade Evaluation Engine             (§5.7)
│   │   ├── costs.py               # Cost Engine / event ledger            (§5.8)
│   │   └── des.py                 # SimPy processes & event dispatch      (§5.3)
│   ├── optimize/                  # Phase 2: policy search
│   ├── reporting/                 # KPI aggregation, HTML report
│   └── cli.py                     # crewsim run | compare | calibrate
└── tests/
```

**Dependency rule:** `engine/` must not import `simpy`. The DES core (`des.py`) orchestrates; every
other engine module is a pure function library over plain dataclasses. This is what lets you unit-test
the legality surrogate in microseconds without spinning up an `Environment`, and it is the difference
between a test suite that runs in 4 seconds and one that runs in 4 minutes.

---

## 4.3 Strict Engineering Standards (How to Write Code for This Project)

Because this tool dictates millions of dollars in airline strategy, the code must be bulletproof. A module of code is only considered "done" when it meets the following strict requirements:

### 1. The "Done" Checklist for Code
1. **Flawless Type-Checking:** The code must pass strict automatic quality checks (`mypy --strict`) with zero warnings. If the computer isn't 100% sure what type of data a variable holds, the code is rejected.
2. **Every Rule Gets Tested:** If there are 8 legal rules for pilots (L1 through L8), there must be 8 specific unit tests. Each test must prove that its specific rule works when it is the *only* thing stopping a pilot from flying.
3. **"Property-Based" Torture Testing:** Instead of just testing "Does it work if I give it the number 5?", the code must pass `hypothesis` tests. This is an automated torture test that throws thousands of random scenarios at the code to ensure core laws of physics never break. For example:
    *   **The L0 Law (No Cloning):** After thousands of random flight assignments, the test must prove that *no pilot is ever scheduled to be in two places at the exact same time*. (This is the single most important test in the entire system).
    *   **The L2 Law (Minimum Rest):** The test must prove that the code never accidentally deletes a pilot's legally required sleep period.
4. **No "Silent" Math:** If the code spends money, it must print out an explicit receipt (a ledger row). You are **never** allowed to just add `$500` to a running total behind the scenes. Every dollar must be traceable to a specific event.

### 2. The "No Magic Randomness" Standard
This simulation relies heavily on random chance (e.g., who gets sick today?). However, this randomness must be **100% reproducible**. If an engineer runs Scenario 47 on Tuesday, and a Duty Manager runs Scenario 47 on Thursday, they must get the *exact same random sick calls*.

*   **No Global Randomness:** Functions are not allowed to just call `random()`. They must be handed a specific, tracked random number generator.
*   **Banned Functions:** The standard Python `hash()` function is strictly banned. Python secretly changes how `hash()` works every time you restart your computer, which destroys our ability to reproduce results across different machines.
*   **The Solution:** Engineers must use the custom `stable_seed()` function below. It uses cryptographic hashing (`blake2b`) to guarantee that the random seed is identical whether you run it on a Macbook, a Windows PC, or a Linux cloud server.

```python
import hashlib

def stable_seed(*parts) -> int:
    """Deterministic 64-bit seed. Stable across processes, machines, Python versions."""
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")
```

---

## 4.4 Parameter registry — the single source of truth

> **Rule:** every number used anywhere in this specification or the codebase is defined here or in the
> YAML file named here. If you find a hard-coded constant elsewhere, that is a bug.

### 4.4.1 Scope & Horizon (`configs/base.yaml`)

This file defines the exact boundaries of the simulation.

| Key | MVP Value | Clear Explanation (Why this matters) |
|---|---|---|
| `base` | `YUL` | The airport we are simulating (Montréal–Trudeau). |
| `fleet` | `A321neoLR` | The aircraft type. As explained in §4.5, fleets cannot be mixed because pilots are legally restricted to one type. |
| `position` | `FO` | The seat we are simulating (First Officer). |
| `population.roster_size` | `[CONFIRM: Crew Planning]` (e.g., `120`) | **Total Headcount.** If the airline has 120 FOs and puts 10 on reserve, they only have 110 left to fly regular scheduled flights. The simulation must know the *total* pool, not just the reserves. |
| `demand.pairings_per_bid_period` | `[CONFIRM: Crew Planning]` (e.g., `480`) | **Total Workload.** Having 120 pilots means nothing if we don't know how much work they have to do. 120 pilots covering 480 trips behaves very differently than 120 pilots stretched over 600 trips. |
| `sensitivity.roster_size` | `[100, 120, 140]` | If we don't know the exact headcount yet, we tell the engine to test a range (100, 120, and 140) so engineering work isn't blocked waiting for a response from the business. |
| `warmup_days` | 7 | **The "Spool-Up" Week.** When the simulation starts at `t=0`, nobody is sick and everything is perfectly on time (which never happens in reality). We run the simulation for 7 days just to get it sufficiently "messy," and we throw out the data from these 7 days. |
| `measurement_days` | 28 | **The Actual Month.** This is the 28-day window where we actually count the costs and measure the results. |
| `cooldown_days` | 7 | **The "Domino Effect" Week.** If a pilot gets sick on Day 27 of the measurement month, the chaos of that sick call will ripple into the next month. We run the simulation for 7 extra days to capture those cascading costs. If we didn't, problems at the end of the month would look artificially cheap. |
| `horizon_days` | **42** | The absolute total time the simulation runs (7 warm-up + 28 measurement + 7 cool-down). |
| `mode` | `FULL` | Use `REDUCED` only for fast, inaccurate smoke tests. |

### 4.4.1b Paths (`configs/base.yaml → paths`)

The corpus ships with the code; run output does not. No location may be hard-coded.

| Key | Value | Why |
|---|---|---|
| `paths.corpus_dir` | `src/crewsim/data/corpus` | **Where the datasets live.** `src/crewsim/data/` holds the *loaders* and, under `corpus/`, the datasets they read — committed and shipped in the wheel, so a checkout or an install is runnable with no generation step and every gate is scored against the exact bytes the loaders were written against. The price is a ~97 MB repository. This does **not** weaken §4.4.1b: the value is still read from config, never hard-coded, so pointing the loaders at Air Transat's real extracts remains a one-line change. |
| `paths.params_dir` | `generated/params` | Calibration output — the versioned parameter store (§6.2). |
| `paths.reports_dir` | `generated/reports` | HTML reports (§9.3). |

### 4.4.2 Cost coefficients (`configs/costs_pilots.yaml`), all CAD

**Every value below is `[CONFIRM: Finance + Crew Planning]`.** They are placeholders chosen to be the
right order of magnitude so that worked examples are checkable. None is an Air Transat figure.

| Symbol | Key | Placeholder | Meaning | Real source |
|---|---|---|---|---|
| κ^SC | `reserve_day_cost.short_call` | 250 /day | Short-call reserve guarantee, per reserve per day | ALPA agreement, reserve guarantee clause |
| κ^LC | `reserve_day_cost.long_call` | 180 /day | Long-call reserve guarantee | ALPA agreement |
| q^res | `reserve_util_cost` | 150 | Marginal pay delta when a reserve is actually used | Pay rules |
| q^base | `base_draft_cost` | 500 | Draft premium, paid on every draft regardless of tier | ALPA premium clause |
| q^tier_1 | `tier_cost[1]` | 0 | Drafted from a day off | — |
| q^tier_2 | `tier_cost[2]` | 300 | Drafted off a future pairing | — |
| q^tier_3 | `tier_cost[3]` | 900 | Drafted out of ground training (+ reschedule cost) | Training dept. |
| q^tier_4 | `tier_cost[4]` | 2,500 | Drafted out of vacation | **`[CONFIRM: Finance]` — newly high priority.** Air Transat has no protected-block rule, so tier 4 is reachable rather than forbidden; combined with senior-first drafting it lands on the crew who hold the best vacation. This coefficient is now a live cost driver, not a corner case. |
| q^tier_5 | `tier_cost[5]` | 4,000 | Drafted out of a simulator slot (+ slot loss) | Training dept. Reachable for the same reason as tier 4. |
| — | `train_reschedule_cost` | 1,200 | Added on a tier-3 or tier-5 draft | Training dept. |
| q^pos | `deadhead_cost`, `hotel_cost` | 400, 220 | Positioning: deadhead seat, hotel night | Invoices (D10) |
| q^cnl | `cancel_cost` | 25,000 | Internal cost of cancelling one flight (aircraft, rebooking, goodwill) | Finance |
| q^comp | `pax_compensation` | see §4.4.3 | Statutory passenger compensation | APPR |
| q^dly | `delay_cost_per_min` | 55 /min | Cost per minute of delay on a covered flight | Finance / industry benchmark |
| V | `terminal_penalty` | `cancel_cost × 1.5` = 37,500 | Charged per open item still unresolved at horizon end | *Fixes **D10**: v2 set this by fiat. It is now a documented multiple of cancellation cost, and §9/V9 requires a sensitivity sweep proving the recommendation is stable in it.* |

### 4.4.3 Regulatory parameters

| Parameter | Value | Source |
|---|---|---|
| APPR compensation, large carrier, delay/cancellation **within carrier control** | 3–6 h late: $400 · 6–9 h: $700 · ≥9 h: $1,000 CAD per passenger | Canadian *Air Passenger Protection Regulations*. `[CONFIRM: Legal — verify current CTA schedule and large-carrier status]` |
| Crew scheduling regime | Canadian Aviation Regulations (CARs) Part VII, Subpart 700 — flight duty and rest limits | Transport Canada. The **legality surrogate** (§5.4) approximates these; it is not a compliance tool. |
| Privacy | Québec Law 25 | Crew identifiers are pseudonymised at ingestion (§6.2). |
| Pilot agreement | ALPA, five-year term, 1 May 2025 – 30 April 2030 | Drives κ, q^base and the tier costs. Note it does **not** impose a cap on drafts per crew, nor protect any schedule block from drafting. |
| Cabin crew agreement | CUPE — Local 4041 (Montréal), 4047 (Toronto), 4078 (Vancouver) | Phase 2. Separate `costs_cabin.yaml`; **do not** reuse pilot coefficients. |

### 4.4.4 The "Reality Check" Targets (Validation)

We need a way to prove the simulation isn't just a fantasy. We do this by comparing its behavior to real Air Transat history. These are **targets to hit**, not inputs you can just type into a config file:

| Reality Check | Target | Clear Explanation (Why this matters) |
|---|---|---|
| **The Usability Rule** (Reserve eligibility rate) | ≈30% | Just because you have 10 pilots on reserve doesn't mean you can use all of them! Due to legal rest limits and aircraft types, historically only about 30% of reserves are actually legal to take any given broken flight. **Example:** If our simulation says 80% of reserves are eligible to fly, our legal code is broken and we are "cheating". |
| **The Domino Effect Rule** (Downstream disruptions) | ≈20% | In the real world, when you draft a pilot to fix a flight today, about 20% of the time it breaks their schedule for later in the week (causing a domino effect). **Example:** If our simulation fixes every sick call perfectly without causing any domino effects, the AI is artificially smart and the results are invalid. |
| **The History Matching Rule** (Draft reconstruction) | ≥80% | **Example:** If we feed the simulation the exact sick calls from last January, it should be able to reconstruct at least 80% of the exact drafts that Air Transat had to do in real life. If it can't reconstruct the past, we can't trust it to predict the future. |

> **CRITICAL RULE: No Cheating on the Tests.** 
> You cannot endlessly tweak the simulation rules until they magically hit the 30% and 20% targets on the *same data* you trained it on (that's cheating). You must train the simulation on 2024 data, and then *test* it on unseen 2025 data to prove the math is actually correct.

---

## 4.5 Two Unique Air Transat Rules That Change the Code

These aren't just minor details—they fundamentally change how the software must be built.

### 1. Different Aircraft Types are Completely Separate Problems

Air Transat flies two very different types of aircraft: the narrow-body A321 and the wide-body A330. In aviation, a pilot is only legally licensed (type-rated) to fly one specific type of aircraft at a time. 

If an A321 flight breaks down, you **cannot** call an A330 pilot sitting at home to fly it. It is strictly illegal, no matter how desperate the airline is.

**What this means for the code:** 
When we scale the AI optimizer to handle multiple fleets in Phase 2, we *must not* throw all the pilots into one giant pool. The AI will waste hours trying to find solutions that are illegal. Instead, we must build the system to solve two completely separate puzzles side-by-side: one for the A321 pilots, and one for the A330 pilots. 

The same logic applies to Flight Attendants (Cabin Crew). They belong to a different union (CUPE instead of ALPA), so they have completely different pay rules and must be treated as a separate puzzle with their own separate `costs_cabin.yaml` file.

### 2. Seasons Change the Math (Summer vs. Winter)

Air Transat is a leisure airline. This means their operations look completely different depending on the time of year:
*   **Summer:** Mostly flying across the Atlantic to Europe. Characterized by long delays and duty-time overruns.
*   **Winter:** Mostly flying south to the Caribbean and Mexico. Characterized by full flights with no nearby alternate airports, making cancellations incredibly expensive.
*   **Shoulder:** The transitional months in between (May, October, November). The airline is switching its network over, demand is lower, and aircraft are often in the hangar for heavy maintenance.

**What this means for the code:**
You cannot calculate one "average" backup strategy for the whole year. If you do, your strategy will have too few backups for January and too many for May. 

The software must explicitly treat seasons as a core feature. We must feed the simulation different historical physics models depending on the season:
```yaml
# configs/seasons.yaml
seasons:
  winter_sun:      {months: [12, 1, 2, 3, 4],  regime_model: regimes_winter.json}
  summer_atlantic: {months: [6, 7, 8, 9],      regime_model: regimes_summer.json}
  shoulder:        {months: [5, 10, 11],       regime_model: regimes_shoulder.json}
```
The final output of the tool is never "You need 10 reserves." It must always be a seasonal list: "You need 12 reserves in January, but only 6 reserves in May."

